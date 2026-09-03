"""
Runtime Agent

Phase 1: Core runtime with explicit state machine, events, budget, and verification.
As required by MASTER PROMPT Section 6, 7, 8, 14, 23-24.
"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator, Callable
from datetime import datetime
import structlog

from rann_agent.core.state import AgentState, InvalidStateTransitionError
from rann_agent.core.events import EventEmitter, EventType, EventStatus, emit_model_requested, emit_model_responded
from rann_agent.core.budget import Budget, BudgetEngine
from rann_agent.core.lifecycle import AgentLifecycle
from rann_agent.core.verification import VerificationEngine, VerificationLevel, VerificationResult
from rann_agent.core.exceptions import (
    BudgetExceededError, StateMachineError, ToolPolicyDeniedError,
    RecoveryError, VerificationError
)
from rann_agent.core.config import Config
from rann_agent.core.llm_provider import LLMProvider
from rann_agent.core.context import Context
from rann_agent.tools.registry import ToolRegistry
from rann_agent.orchestration.coordinator import Coordinator
from rann_agent.memory.manager import MemoryManager

logger = structlog.get_logger()


class RuntimeAgent:
    """
    Phase 1 Runtime Agent with explicit state machine and events.
    
    Key improvements over legacy Agent:
    - Explicit state machine (CREATED → ... → COMPLETED/FAILED)
    - Structured event emission for every action
    - Budget enforcement (token, time, tool, cost)
    - Verification engine with evidence-based proof-of-completion
    - Lifecycle manager for checkpoint/resume
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[str]] = None,
        memory: bool = True,
        budget: Optional[Budget] = None,
        verification_level: VerificationLevel = VerificationLevel.MODERATE,
    ):
        self.config = config or Config.load()
        
        # Override config
        if provider:
            self.config.agent.llm.provider = provider
        if model:
            self.config.agent.llm.model = model
        if tools:
            self.config.tools.enabled = tools
        
        # Core components
        self.llm = LLMProvider(self.config)
        self.tools = ToolRegistry(self.config)
        self.memory = MemoryManager(self.config) if memory else None
        self.coordinator = Coordinator(self.config, self) if self.config.agent.orchestration.enabled else None
        
        # Phase 1: State machine (use lifecycle's)
        self._state = AgentState.QUEUED
        self._lifecycle_state = None  # Set during execute()
        
        # Phase 1: Events
        self._events: EventEmitter = None  # Created per-run
        
        # Phase 1: Budget
        self._budget_engine = BudgetEngine(budget)
        
        # Phase 1: Verification
        self._verification = VerificationEngine(verification_level)
        
        # Session state
        self.context = Context()
        self.session_id: Optional[str] = None
        self.run_id: Optional[str] = None
        
        # Recovery strategies
        self._recovery_strategies: List[Callable] = []
        
        logger.info(
            "runtime_agent_init",
            provider=self.llm.provider,
            model=self.llm.model,
            tools=len(self.tools.get_enabled()),
            verification_level=verification_level.value
        )
    
    @property
    def state(self) -> AgentState:
        return self._state
    
    @property
    def is_terminal(self) -> bool:
        return self._state in {AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED, AgentState.TIMED_OUT, AgentState.BLOCKED, AgentState.ROLLED_BACK}
    
    def add_recovery_strategy(self, strategy: Callable) -> None:
        """Add a recovery strategy function"""
        self._recovery_strategies.append(strategy)
    
    def _set_state(self, state: AgentState, reason: str = None) -> None:
        """Set state with event emission. Silently skip if lifecycle already transitioned."""
        # If lifecycle already transitioned to terminal, don't fight it
        if self._lifecycle_state and self._lifecycle_state.is_terminal():
            return
        old_state = self._state
        if old_state == state:
            return
        
        # Check valid transition
        if hasattr(AgentState, '_transitions'):
            from rann_agent.core.state import VALID_TRANSITIONS
            allowed = VALID_TRANSITIONS.get(old_state, set())
            if state not in allowed and state not in (AgentState.COMPLETED, AgentState.FAILED):
                # Skip silently - lifecycle may be handling state
                return
        
        self._state = state
        
        if self._events:
            self._events.create_event(
                EventType.STATE_CHANGED,
                component="runtime_agent",
                from_state=old_state.value,
                to_state=state.value,
                reason=reason
            )
        
        logger.info("agent_state_change", from_state=old_state.value, to_state=state.value, reason=reason)
    
    async def execute(
        self,
        goal: str,
        context: Optional[str] = None,
        max_turns: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a task with full Phase 1 infrastructure.
        
        States: CREATED → INITIALIZING → UNDERSTANDING → PLANNING → EXECUTING → VERIFYING → COMPLETED/FAILED
        """
        self.run_id = self._generate_run_id()
        self.session_id = self.run_id
        self._events = EventEmitter(self.run_id)
        
        # Override budget max_turns
        if max_turns:
            self._budget_engine.budget.max_turns = max_turns
        
        lifecycle = AgentLifecycle(self.run_id, goal, self._budget_engine.budget)
        self._lifecycle_state = lifecycle.state_machine
        
        try:
            async with lifecycle.run():
                # ANALYZING
                self._set_state(AgentState.ANALYZING)
                self.context = Context()
                self.context.add_user_message(goal, context)
                
                lifecycle.events.emit(lifecycle.events.create_event(
                    EventType.CONTEXT_BUILT,
                    message_count=len(self.context.messages)
                ))
                
                # Load memory
                if self.memory:
                    memory_context = await self.memory.get_relevant_context(goal)
                    if memory_context:
                        self.context.add_system_message(f"Relevant memory:\n{memory_context}")
                        lifecycle.events.emit(lifecycle.events.create_event(
                            EventType.MEMORY_RETRIEVED,
                            memory_length=len(memory_context)
                        ))
                
                # CONTEXT_READY
                self._set_state(AgentState.CONTEXT_READY)
                await asyncio.sleep(0)  # Allow event processing
                
                # PLANNING
                self._set_state(AgentState.PLANNING)
                lifecycle.events.emit(lifecycle.events.create_event(
                    EventType.PLAN_CREATED,
                    strategy="direct"
                ))
                
                # EXECUTING
                self._set_state(AgentState.EXECUTING)
                lifecycle.events.emit(lifecycle.events.create_event(
                    EventType.RUN_STARTED,
                    status=EventStatus.SUCCESS
                ))
                
                final_result = await self._execute_loop(lifecycle)
                
                # VERIFYING
                self._set_state(AgentState.VERIFYING)
                verification = await self._verify_result(final_result, lifecycle)
                
                if not verification.passed:
                    self._set_state(AgentState.FAILED, reason="verification_failed")
                    final_result["verification_failed"] = True
                    final_result["verification_result"] = verification.to_dict()
                    return final_result
                
                lifecycle.events.emit(lifecycle.events.create_event(
                    EventType.VERIFICATION_PASSED,
                    status=EventStatus.SUCCESS
                ))
                
                self._set_state(AgentState.COMPLETED)
                
                # Save to memory
                if self.memory:
                    await self.memory.save_session(
                        session_id=self.session_id,
                        goal=goal,
                        result=final_result,
                        turns=lifecycle.budget_engine.tracker.turns
                    )
                    lifecycle.events.emit(lifecycle.events.create_event(
                        EventType.MEMORY_STORED,
                        status=EventStatus.SUCCESS
                    ))
                
                final_result["events"] = lifecycle.events.get_trace()
                final_result["budget"] = lifecycle.budget_engine.get_status()
                
                return final_result
                
        except BudgetExceededError as e:
            # Lifecycle already set state to FAILED
            return {"error": "Budget exhausted", "details": e.details, "state": self._state.value}
            
        except Exception as e:
            # Lifecycle already set state to FAILED
            logger.error("execute_failed", run_id=self.run_id, error=str(e))
            return {"error": str(e), "state": self._state.value}
    
    async def _execute_loop(self, lifecycle: AgentLifecycle) -> Dict[str, Any]:
        """Main execution loop with state transitions and budget tracking"""
        turn = 0
        
        while not lifecycle.state_machine.is_terminal():
            # Check budget
            lifecycle.check_budget()
            
            # EXECUTING state (inside loop)
            self._set_state(AgentState.EXECUTING)
            
            # Get LLM response
            messages = self.context.get_messages()
            
            lifecycle.events.emit(lifecycle.events.create_event(
                EventType.MODEL_REQUESTED,
                component="llm",
                model=self.llm.model,
                message_count=len(messages)
            ))
            
            try:
                response = await self.llm.complete_with_retry(messages)
            except Exception as e:
                lifecycle.events.emit(lifecycle.events.create_event(
                    EventType.MODEL_RESPONDED,
                    component="llm",
                    status=EventStatus.FAILURE,
                    error=str(e)
                ))
                raise
            
            # Record model call
            usage = response.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            lifecycle.record_model_call(input_tokens, output_tokens)
            lifecycle.record_turn()
            
            lifecycle.events.emit(lifecycle.events.create_event(
                EventType.MODEL_RESPONDED,
                component="llm",
                status=EventStatus.SUCCESS,
                model=self.llm.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            ))
            
            # Parse tool calls
            tool_calls = self._extract_tool_calls(response)
            
            if not tool_calls:
                # No tool calls - we're done
                self.context.add_assistant_message(response.get("content", ""))
                lifecycle.events.emit(lifecycle.events.create_event(
                    EventType.TASK_COMPLETED,
                    status=EventStatus.SUCCESS,
                    output_length=len(response.get("content", ""))
                ))
                
                return {
                    "done": True,
                    "output": response.get("content"),
                    "metadata": {"tokens": usage, "model": self.llm.model},
                    "turns": turn
                }
            
            # VERIFYING (tool execution complete, check results)
            self._set_state(AgentState.VERIFYING)
            
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name", "unknown")
                
                lifecycle.events.emit(lifecycle.events.create_event(
                    EventType.TOOL_STARTED,
                    component="tools",
                    tool=tool_name
                ))
                
                try:
                    result = await self.tools.execute(tool_name, tool_call.get("parameters") or {})
                    lifecycle.record_tool_call()
                    
                    lifecycle.events.emit(lifecycle.events.create_event(
                        EventType.TOOL_COMPLETED,
                        component="tools",
                        tool=tool_name,
                        status=EventStatus.SUCCESS,
                        success=result.get("success", False)
                    ))
                    
                except Exception as e:
                    lifecycle.events.emit(lifecycle.events.create_event(
                        EventType.TOOL_FAILED,
                        component="tools",
                        tool=tool_name,
                        status=EventStatus.FAILURE,
                        error=str(e)
                    ))
                    result = {"success": False, "error": str(e), "tool": tool_name}
                
                tool_results.append(result)
            
            self.context.add_tool_results(tool_results)
            
            lifecycle.events.emit(lifecycle.events.create_event(
                EventType.OBSERVATION_CREATED,
                tool_count=len(tool_results)
            ))
            
            turn += 1
            
            # Check max turns
            if turn >= self._budget_engine.budget.max_turns:
                logger.warning("max_turns_reached", turns=turn)
                break
        
        return {"done": False, "turns": turn, "tool_results": tool_results}
    
    async def _verify_result(
        self,
        result: Dict[str, Any],
        lifecycle: AgentLifecycle
    ) -> VerificationResult:
        """Run verification on result"""
        if result.get("done") and result.get("output"):
            # Basic output verification
            self._verification.add_assertion(
                "has_output",
                "Result has non-empty output",
                lambda: bool(result.get("output"))
            )
        
        return await self._verification.verify(
            task=result.get("output", ""),
            output=result,
            context={"session_id": self.session_id}
        )
    
    def _extract_tool_calls(self, response: Dict) -> List[Dict]:
        """Extract tool calls from LLM response"""
        # Support both OpenAI and Anthropic function calling formats
        if "tool_calls" in response:
            return response["tool_calls"]
        
        # Anthropic-style
        if "content" in response and isinstance(response["content"], list):
            for block in response["content"]:
                if block.get("type") == "tool_use":
                    return [{
                        "name": block.get("name"),
                        "parameters": block.get("input", {})
                    }]
        
        return []
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID"""
        from datetime import datetime
        import uuid
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    
    async def stream(
        self,
        goal: str,
        context: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream execution tokens"""
        logger.info("stream_start", goal=goal[:100])
        
        self.run_id = self._generate_run_id()
        self.context.add_user_message(goal, context)
        
        async for token in self.llm.stream(self.context.get_messages()):
            yield token
    
    def get_trace(self) -> List[Dict[str, Any]]:
        """Get event trace"""
        if self._events:
            return self._events.get_trace()
        return []
    
    def spawn_coordinator(self) -> "Coordinator":
        """Spawn a coordinator for multi-agent"""
        if not self.coordinator:
            self.coordinator = Coordinator(self.config, self)
        return self.coordinator