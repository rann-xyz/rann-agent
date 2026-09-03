"""
Agent Lifecycle Manager

Manages the complete agent lifecycle from creation to completion.
Coordinates state machine, events, budget, and checkpoints.
"""

from typing import Optional, Dict, Any, Callable
from contextlib import asynccontextmanager
import structlog

from rann_agent.core.state import AgentState, AgentStateMachine, InvalidStateTransitionError
from rann_agent.core.events import EventEmitter, EventType, EventStatus
from rann_agent.core.budget import BudgetEngine, Budget, BudgetTracker
from rann_agent.core.exceptions import (
    StateMachineError, BudgetExceededError, VerificationError, RecoveryError
)

logger = structlog.get_logger()


class AgentLifecycle:
    """
    Manages the complete agent lifecycle.
    
    Coordinates:
    - State machine transitions
    - Event emission
    - Budget tracking
    - Checkpoint management
    - Recovery orchestration
    """
    
    def __init__(
        self,
        run_id: str,
        goal: str,
        budget: Optional[Budget] = None,
        store_events: bool = True
    ):
        self.run_id = run_id
        self.goal = goal
        
        # Core systems
        self.state_machine = AgentStateMachine(run_id)
        self.events = EventEmitter(run_id, store_events=store_events)
        self.budget_engine = BudgetEngine(budget)
        
        # Checkpoint state
        self._checkpoint_data: Dict[str, Any] = {}
        self._last_checkpoint_time: Optional[float] = None
        
        # Callbacks
        self._on_state_change: Optional[Callable] = None
        self._on_budget_warning: Optional[Callable] = None
        self._on_recovery: Optional[Callable] = None
        
        logger.info("lifecycle_init", run_id=run_id, goal=goal[:100])
    
    @asynccontextmanager
    async def run(self):
        """
        Context manager for a complete run.
        
        Usage:
            async with lifecycle.run():
                await lifecycle.execute_task(...)
        """
        try:
            self.events.emit(self.events.create_event(
                EventType.RUN_CREATED,
                goal=self.goal,
                budget=self.budget_engine.budget.__dict__
            ))
            
            self.state_machine.transition(AgentState.INITIALIZING, reason="run_started")
            self.budget_engine.start_run()
            
            self.events.emit(self.events.create_event(
                EventType.RUN_STARTED,
                status=EventStatus.SUCCESS
            ))
            
            yield self
            
            # Normal completion
            self.state_machine.transition(AgentState.COMPLETED, reason="run_completed")
            self.events.emit(self.events.create_event(
                EventType.RUN_COMPLETED,
                status=EventStatus.SUCCESS,
                turns=self.budget_engine.tracker.turns
            ))
            
        except Exception as e:
            logger.error("lifecycle_error", run_id=self.run_id, error=str(e))
            self.state_machine.transition(AgentState.FAILED, reason=str(e))
            self.events.emit(self.events.create_event(
                EventType.ERROR_OCCURRED,
                status=EventStatus.FAILURE,
                error=str(e)
            ))
            raise
    
    def set_state_change_callback(self, callback: Callable) -> None:
        """Set callback for state changes"""
        self._on_state_change = callback
    
    def set_budget_warning_callback(self, callback: Callable) -> None:
        """Set callback for budget warnings"""
        self._on_budget_warning = callback
    
    def set_recovery_callback(self, callback: Callable) -> None:
        """Set callback for recovery events"""
        self._on_recovery = callback
    
    # === State Management ===
    
    def transition_to(self, state: AgentState, reason: Optional[str] = None, **metadata) -> None:
        """Transition to a new state"""
        try:
            self.state_machine.transition(state, reason, **metadata)
            self.events.emit(self.events.create_event(
                EventType.STATE_CHANGED,
                from_state=self.state_machine._history[-2].to_state.value if len(self.state_machine._history) > 1 else None,
                to_state=state.value,
                reason=reason,
                **metadata
            ))
            
            if self._on_state_change:
                self._on_state_change(state, reason, metadata)
                
        except InvalidStateTransitionError as e:
            raise StateMachineError(f"Invalid transition: {e}")
    
    # === Budget Management ===
    
    def check_budget(self) -> None:
        """Check budget and raise if exceeded"""
        if self.budget_engine.tracker.is_exhausted():
            status = self.budget_engine.tracker.get_limit_status()
            raise BudgetExceededError(
                "Budget exhausted",
                details=status
            )
    
    def check_budget_warnings(self) -> None:
        """Check for budget warnings and trigger callback"""
        warnings = self.budget_engine.tracker.check_warnings()
        if warnings and self._on_budget_warning:
            self._on_budget_warning(warnings)
    
    def record_model_call(self, input_tokens: int, output_tokens: int, cost_usd: float = 0) -> None:
        """Record a model call"""
        self.budget_engine.record_model_call(input_tokens, output_tokens, cost_usd)
        self.check_budget_warnings()
    
    def record_tool_call(self) -> None:
        """Record a tool call"""
        self.budget_engine.record_tool_call()
        self.check_budget_warnings()
    
    def record_turn(self) -> None:
        """Record a turn"""
        self.budget_engine.record_turn()
        self.check_budget_warnings()
    
    # === Checkpoint Management ===
    
    def checkpoint(self, data: Dict[str, Any], reason: str = "manual") -> None:
        """Create a checkpoint"""
        self.state_machine.transition(AgentState.CHECKPOINTING, reason=reason)
        
        self._checkpoint_data = {
            "state": self.state_machine.state.value,
            "goal": self.goal,
            "budget": self.budget_engine.get_status(),
            "events": self.events.get_trace(),
            "data": data
        }
        
        self.events.emit(self.events.create_event(
            EventType.CHECKPOINT_CREATED,
            status=EventStatus.SUCCESS,
            reason=reason
        ))
        
        # Return to previous state
        if len(self.state_machine.history) >= 2:
            # Go back to the state before checkpointing
            prev_state = self.state_machine.history[-2].to_state
            self.state_machine.transition(prev_state, reason="checkpoint_complete")
        
        logger.info("checkpoint_created", run_id=self.run_id, reason=reason)
    
    def get_checkpoint_data(self) -> Dict[str, Any]:
        """Get current checkpoint data"""
        return self._checkpoint_data.copy()
    
    def can_resume_from_checkpoint(self) -> bool:
        """Check if we can resume from checkpoint"""
        return bool(self._checkpoint_data) and self.state_machine.state == AgentState.CREATED
    
    # === Recovery ===
    
    async def attempt_recovery(self, error: Exception, recovery_strategies: list) -> bool:
        """
        Attempt to recover from an error.
        
        Args:
            error: The error that occurred
            recovery_strategies: List of recovery strategy functions
            
        Returns:
            True if recovery succeeded
        """
        self.events.emit(self.events.create_event(
            EventType.RECOVERY_STARTED,
            status=EventStatus.STARTED,
            error=str(error),
            strategy_count=len(recovery_strategies)
        ))
        
        for strategy in recovery_strategies:
            try:
                logger.info("attempting_recovery", strategy=strategy.__name__)
                
                success = await strategy(self, error)
                
                if success:
                    self.events.emit(self.events.create_event(
                        EventType.RECOVERY_STARTED,
                        status=EventStatus.SUCCESS,
                        strategy=strategy.__name__
                    ))
                    
                    if self._on_recovery:
                        self._on_recovery(strategy.__name__, success)
                    
                    return True
                    
            except Exception as recovery_error:
                logger.warning(
                    "recovery_attempt_failed",
                    strategy=strategy.__name__,
                    error=str(recovery_error)
                )
        
        return False
    
    # === Status ===
    
    def get_status(self) -> Dict[str, Any]:
        """Get complete lifecycle status"""
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "state": self.state_machine.state.value,
            "is_terminal": self.state_machine.is_terminal,
            "is_running": self.state_machine.is_running,
            "budget": self.budget_engine.get_status(),
            "events": self.events.get_summary(),
            "checkpoint_available": bool(self._checkpoint_data)
        }
    
    def get_trace(self) -> list[Dict[str, Any]]:
        """Get full event trace"""
        return self.events.get_trace()
    
    def get_state_history(self) -> list[Dict[str, Any]]:
        """Get state transition history"""
        return [
            {
                "from": t.from_state.value,
                "to": t.to_state.value,
                "timestamp": t.timestamp.isoformat(),
                "reason": t.reason,
                "metadata": t.metadata
            }
            for t in self.state_machine.history
        ]