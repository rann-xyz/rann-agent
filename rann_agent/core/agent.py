"""
Core Agent Implementation
"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator
from pathlib import Path
import structlog

from rann_agent.core.config import Config
from rann_agent.core.llm_provider import LLMProvider
from rann_agent.core.context import Context
from rann_agent.tools.registry import ToolRegistry
from rann_agent.orchestration.coordinator import Coordinator
from rann_agent.memory.manager import MemoryManager

logger = structlog.get_logger()


class Agent:
    """
    Main Agent class - orchestrates LLM, tools, memory, and self-healing
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[str]] = None,
        memory: bool = True,
    ):
        """
        Initialize the agent
        
        Args:
            config: Configuration object (loads from config.yaml if None)
            provider: LLM provider override (anthropic|openai|ollama)
            model: Model name override
            tools: List of tool names to enable
            memory: Enable persistent memory
        """
        self.config = config or Config.load()
        
        # Override config with params
        if provider:
            self.config.agent.llm.provider = provider
        if model:
            self.config.agent.llm.model = model
        if tools:
            self.config.tools.enabled = tools
            
        # Initialize components
        self.llm = LLMProvider(self.config)
        self.tools = ToolRegistry(self.config)
        self.memory = MemoryManager(self.config) if memory else None
        self.coordinator = Coordinator(self.config, self) if self.config.agent.orchestration.enabled else None
        
        # Session state
        self.context = Context()
        self.session_id = None
        
        logger.info(
            "agent_initialized",
            provider=self.llm.provider,
            model=self.llm.model,
            tools=len(self.tools.get_enabled()),
        )
    
    async def execute(
        self,
        goal: str,
        context: Optional[str] = None,
        max_turns: int = 50,
    ) -> Dict[str, Any]:
        """
        Execute a task (async)
        
        Args:
            goal: What to accomplish
            context: Additional context
            max_turns: Maximum conversation turns
            
        Returns:
            Execution result with output, tool calls, metadata
        """
        logger.info("execute_start", goal=goal[:100])
        
        # Initialize session
        self.session_id = self._generate_session_id()
        self.context.add_user_message(goal, context)
        
        # Load memory
        if self.memory:
            memory_context = await self.memory.get_relevant_context(goal)
            if memory_context:
                self.context.add_system_message(f"Relevant memory:\n{memory_context}")
        
        turn = 0
        final_result = None
        
        try:
            while turn < max_turns:
                turn += 1
                logger.debug("turn_start", turn=turn)
                
                # Get LLM response
                response = await self._execute_turn()
                
                # Check if done
                if response.get("done"):
                    final_result = response
                    break
                    
                # Check for errors and apply self-healing
                if response.get("error") and self.config.agent.self_healing.enabled:
                    logger.warning("error_detected", error=response["error"])
                    healed = await self._self_heal(response["error"])
                    if healed:
                        continue
                    else:
                        raise Exception(f"Failed to heal error: {response['error']}")
            
            # Save to memory
            if self.memory and final_result:
                await self.memory.save_session(
                    session_id=self.session_id,
                    goal=goal,
                    result=final_result,
                    turns=turn,
                )
            
            logger.info("execute_complete", turns=turn, session_id=self.session_id)
            return final_result or {"error": "Max turns reached", "output": None}
            
        except Exception as e:
            logger.error("execute_failed", error=str(e), session_id=self.session_id)
            raise
    
    async def execute_sync(self, goal: str, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for execute()"""
        return await self.execute(goal, **kwargs)
    
    async def stream(
        self,
        goal: str,
        context: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream execution with real-time token output
        
        Args:
            goal: What to accomplish
            context: Additional context
            
        Yields:
            Token strings as they're generated
        """
        logger.info("stream_start", goal=goal[:100])
        
        self.session_id = self._generate_session_id()
        self.context.add_user_message(goal, context)
        
        async for token in self.llm.stream(self.context.get_messages()):
            yield token
    
    async def _execute_turn(self) -> Dict[str, Any]:
        """Execute one conversation turn"""
        messages = self.context.get_messages()
        
        # Call LLM with retry logic
        response = await self.llm.complete_with_retry(messages)
        
        # Parse tool calls
        tool_calls = self._extract_tool_calls(response)
        
        # Execute tools (parallel if possible)
        if tool_calls:
            tool_results = await self._execute_tools(tool_calls)
            self.context.add_tool_results(tool_results)
            return {"done": False, "tool_results": tool_results}
        
        # No more tool calls, we're done
        self.context.add_assistant_message(response.get("content", ""))
        return {
            "done": True,
            "output": response.get("content"),
            "metadata": {
                "tokens": response.get("usage"),
                "model": self.llm.model,
            }
        }
    
    async def _execute_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute tool calls (parallel when possible)"""
        if self.config.advanced.parallel_tools:
            # Execute in parallel
            tasks = [
                self.tools.execute(call["name"], call["parameters"])
                for call in tool_calls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            formatted_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    formatted_results.append({
                        "tool": tool_calls[i]["name"],
                        "success": False,
                        "error": str(result),
                    })
                else:
                    formatted_results.append(result)
            return formatted_results
        else:
            # Execute sequentially
            results = []
            for call in tool_calls:
                result = await self.tools.execute(call["name"], call["parameters"])
                results.append(result)
            return results
    
    async def _self_heal(self, error: str) -> bool:
        """
        Self-healing error recovery
        
        Returns:
            True if healed, False if failed
        """
        logger.info("self_heal_start", error=error[:200])
        
        for attempt in range(self.config.agent.self_healing.max_retries):
            logger.debug("heal_attempt", attempt=attempt + 1)
            
            # Analyze error
            analysis = await self._analyze_error(error)
            
            # Search for similar past resolutions
            if self.memory:
                similar = await self.memory.search_similar_errors(error)
                if similar:
                    logger.info("found_similar_resolution", count=len(similar))
                    # Try the most successful past fix
                    fix = similar[0]["fix"]
                    success = await self._apply_fix(fix)
                    if success:
                        return True
            
            # Generate new fix strategies
            fixes = await self._generate_fixes(error, analysis)
            
            # Try each fix
            for fix in fixes:
                logger.debug("trying_fix", strategy=fix.get("strategy"))
                success = await self._apply_fix(fix)
                if success:
                    # Learn from this success
                    if self.memory and self.config.agent.self_healing.learn_from_errors:
                        await self.memory.save_error_resolution(error, fix)
                    return True
        
        logger.warning("self_heal_failed", error=error[:200])
        return False
    
    async def _analyze_error(self, error: str) -> Dict[str, Any]:
        """Analyze error with LLM"""
        prompt = f"""Analyze this error and provide:
1. Error type/category
2. Root cause
3. Suggested fix strategies

Error:
{error}

Respond in JSON format."""
        
        response = await self.llm.complete([{"role": "user", "content": prompt}])
        # Parse JSON from response
        return {"analysis": response.get("content")}
    
    async def _generate_fixes(self, error: str, analysis: Dict) -> List[Dict]:
        """Generate potential fixes using LLM"""
        prompt = f"""Given this error and analysis, generate 3 fix strategies:

Error: {error}
Analysis: {analysis}

For each fix, provide:
- strategy: brief name
- action: what to do
- command: executable command if applicable

Respond in JSON format as array."""
        
        response = await self.llm.complete([{"role": "user", "content": prompt}])
        # Parse and return fixes
        return [{"strategy": "retry", "action": "simple retry"}]  # Simplified
    
    async def _apply_fix(self, fix: Dict) -> bool:
        """Apply a fix and verify"""
        try:
            if "command" in fix:
                result = await self.tools.execute("terminal", {"command": fix["command"]})
                return result.get("success", False)
            return False
        except Exception as e:
            logger.error("fix_failed", error=str(e))
            return False
    
    def _extract_tool_calls(self, response: Dict) -> List[Dict]:
        """Extract tool calls from LLM response"""
        # Parse tool calls from response
        # This depends on the LLM response format
        if "tool_calls" in response:
            return response["tool_calls"]
        return []
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        from datetime import datetime
        import uuid
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{timestamp}_{short_uuid}"
    
    def spawn_coordinator(self) -> "Coordinator":
        """Spawn a coordinator for multi-agent orchestration"""
        if not self.coordinator:
            self.coordinator = Coordinator(self.config, self)
        return self.coordinator
