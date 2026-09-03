"""
Agent State Machine

Explicit state transitions as required by MASTER PROMPT Section 7.
Every state transition produces an event. Invalid transitions are rejected.
"""

from enum import Enum
from typing import Set, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import structlog

logger = structlog.get_logger()


class AgentState(Enum):
    """All possible agent states"""
    CREATED = "created"
    INITIALIZING = "initializing"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    VERIFYING = "verifying"
    REFLECTING = "reflecting"
    REPLANNING = "replanning"
    WAITING = "waiting"
    CHECKPOINTING = "checkpointing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Valid state transitions
VALID_TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
    AgentState.CREATED: {AgentState.INITIALIZING},
    AgentState.INITIALIZING: {AgentState.UNDERSTANDING, AgentState.FAILED},
    AgentState.UNDERSTANDING: {AgentState.PLANNING, AgentState.FAILED},
    AgentState.PLANNING: {AgentState.EXECUTING, AgentState.REPLANNING, AgentState.FAILED},
    AgentState.EXECUTING: {AgentState.OBSERVING, AgentState.VERIFYING, AgentState.REPLANNING, AgentState.FAILED},
    AgentState.OBSERVING: {AgentState.VERIFYING, AgentState.EXECUTING, AgentState.REPLANNING, AgentState.FAILED},
    AgentState.VERIFYING: {AgentState.COMPLETED, AgentState.REFLECTING, AgentState.REPLANNING, AgentState.FAILED},
    AgentState.REFLECTING: {AgentState.PLANNING, AgentState.REPLANNING, AgentState.FAILED},
    AgentState.REPLANNING: {AgentState.PLANNING, AgentState.EXECUTING, AgentState.FAILED},
    AgentState.WAITING: {AgentState.EXECUTING, AgentState.FAILED},
    AgentState.CHECKPOINTING: {AgentState.WAITING, AgentState.COMPLETED, AgentState.FAILED},
    AgentState.COMPLETED: set(),  # Terminal state
    AgentState.FAILED: {AgentState.CREATED},  # Can restart
    AgentState.CANCELLED: {AgentState.CREATED},  # Can restart
}


@dataclass
class StateTransitionRecord:
    """Record of a state transition"""
    from_state: AgentState
    to_state: AgentState
    timestamp: datetime
    reason: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    def __init__(self, current: AgentState, target: AgentState):
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid state transition: {current.value} -> {target.value}. "
            f"Valid transitions from {current.value}: {[s.value for s in VALID_TRANSITIONS.get(current, set())]}"
        )


class AgentStateMachine:
    """
    Explicit state machine for agent lifecycle.
    
    Tracks current state, allows only valid transitions,
    and emits events for every transition.
    """
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._state = AgentState.CREATED
        self._history: list[StateTransitionRecord] = []
        self._state_since = datetime.now()
        
        logger.info(
            "state_machine_init",
            run_id=run_id,
            initial_state=self._state.value
        )
    
    @property
    def state(self) -> AgentState:
        """Current state"""
        return self._state
    
    @property
    def is_terminal(self) -> bool:
        """True if in a terminal state"""
        return self._state in {AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED}
    
    @property
    def is_running(self) -> bool:
        """True if actively processing"""
        return self._state not in {
            AgentState.CREATED, AgentState.COMPLETED, 
            AgentState.FAILED, AgentState.CANCELLED
        }
    
    @property
    def history(self) -> list[StateTransitionRecord]:
        """Full transition history"""
        return self._history.copy()
    
    @property
    def duration_seconds(self) -> float:
        """Time spent in current state"""
        return (datetime.now() - self._state_since).total_seconds()
    
    def can_transition(self, target: AgentState) -> bool:
        """Check if transition is valid"""
        return target in VALID_TRANSITIONS.get(self._state, set())
    
    def transition(self, target: AgentState, reason: Optional[str] = None, **metadata) -> StateTransitionRecord:
        """
        Transition to new state.
        
        Raises:
            InvalidStateTransitionError: If transition is not valid
            
        Returns:
            StateTransitionRecord of the transition
        """
        if not self.can_transition(target):
            raise InvalidStateTransitionError(self._state, target)
        
        record = StateTransitionRecord(
            from_state=self._state,
            to_state=target,
            timestamp=datetime.now(),
            reason=reason,
            metadata=metadata
        )
        
        old_state = self._state
        self._state = target
        self._history.append(record)
        self._state_since = datetime.now()
        
        logger.info(
            "state_transition",
            run_id=self.run_id,
            from_state=old_state.value,
            to_state=target.value,
            reason=reason,
            **metadata
        )
        
        return record
    
    def must_transition(self, target: AgentState, reason: Optional[str] = None, **metadata) -> StateTransitionRecord:
        """
        Transition with assertion - wrapper that logs if invalid.
        Use this when transition SHOULD be valid but we want defensive handling.
        """
        try:
            return self.transition(target, reason, **metadata)
        except InvalidStateTransitionError as e:
            logger.error(
                "invalid_state_transition_attempt",
                run_id=self.run_id,
                current=e.current.value,
                attempted=e.target.value,
                reason=reason
            )
            raise
    
    def restart(self) -> StateTransitionRecord:
        """Restart from CREATED state"""
        if self._state not in {AgentState.FAILED, AgentState.CANCELLED}:
            raise InvalidStateTransitionError(
                self._state,
                AgentState.CREATED
            )
        return self.transition(AgentState.CREATED, reason="restart")
    
    def get_state_summary(self) -> Dict:
        """Get summary of current state for debugging"""
        return {
            "run_id": self.run_id,
            "current_state": self._state.value,
            "is_terminal": self.is_terminal,
            "is_running": self.is_running,
            "duration_seconds": self.duration_seconds,
            "transition_count": len(self._history),
            "last_transition": {
                "from": self._history[-1].from_state.value if self._history else None,
                "to": self._history[-1].to_state.value if self._history else None,
                "timestamp": self._history[-1].timestamp.isoformat() if self._history else None,
            } if self._history else None
        }