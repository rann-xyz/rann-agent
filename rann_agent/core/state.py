"""
Agent State Machine

Implements V3 Section 5 state machine with persistent state support.
Supports resume after restart through disk persistence.
"""

from enum import Enum
from typing import Set, Dict, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import structlog
from pathlib import Path

logger = structlog.get_logger()

# State persistence directory
STATE_DIR = Path.home() / ".rann_agent" / "state"


class AgentState(Enum):
    """All possible agent states as per V3 Section 5"""
    # Active states
    QUEUED = "queued"
    ANALYZING = "analyzing"
    CONTEXT_READY = "context_ready"
    PLANNING = "planning"
    WAITING_POLICY = "waiting_policy"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    ACCEPTANCE_CHECK = "acceptance_check"
    LEARNING = "learning"
    COMPLETED = "completed"
    # Terminal states
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"
    ROLLED_BACK = "rolled_back"


# Terminal states that cannot transition further
TERMINAL_STATES: Set[AgentState] = {
    AgentState.COMPLETED,
    AgentState.FAILED,
    AgentState.CANCELLED,
    AgentState.TIMED_OUT,
    AgentState.BLOCKED,
    AgentState.ROLLED_BACK,
}

# Valid state transitions per V3 Section 5
VALID_TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
    AgentState.QUEUED: {AgentState.ANALYZING},
    AgentState.ANALYZING: {AgentState.CONTEXT_READY, AgentState.BLOCKED, AgentState.FAILED},
    AgentState.CONTEXT_READY: {AgentState.PLANNING, AgentState.BLOCKED, AgentState.FAILED},
    AgentState.PLANNING: {AgentState.WAITING_POLICY, AgentState.EXECUTING, AgentState.FAILED},
    AgentState.WAITING_POLICY: {AgentState.EXECUTING, AgentState.BLOCKED, AgentState.FAILED},
    AgentState.EXECUTING: {AgentState.VERIFYING, AgentState.RECOVERING, AgentState.FAILED, AgentState.TIMED_OUT},
    AgentState.VERIFYING: {AgentState.ACCEPTANCE_CHECK, AgentState.RECOVERING, AgentState.EXECUTING, AgentState.FAILED},
    AgentState.RECOVERING: {AgentState.EXECUTING, AgentState.ANALYZING, AgentState.FAILED, AgentState.ROLLED_BACK},
    AgentState.ACCEPTANCE_CHECK: {AgentState.COMPLETED, AgentState.LEARNING, AgentState.EXECUTING, AgentState.FAILED},
    AgentState.LEARNING: {AgentState.PLANNING, AgentState.COMPLETED, AgentState.FAILED},
    # Terminal states - no valid transitions out
    AgentState.COMPLETED: set(),
    AgentState.FAILED: set(),
    AgentState.CANCELLED: set(),
    AgentState.TIMED_OUT: set(),
    AgentState.BLOCKED: set(),
    AgentState.ROLLED_BACK: set(),
}


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    def __init__(self, current: AgentState, target: AgentState):
        self.current = current
        self.target = target
        valid = VALID_TRANSITIONS.get(current, set())
        valid_str = ", ".join(s.value for s in valid) if valid else "none"
        super().__init__(
            f"Invalid state transition: {current.value} -> {target.value}. "
            f"Valid transitions from {current.value}: {valid_str}"
        )


# Backward compatibility alias
InvalidStateTransitionError = StateTransitionError


@dataclass
class StateTransitionRecord:
    """Record of a state transition"""
    from_state: AgentState
    to_state: AgentState
    timestamp: datetime
    reason: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "StateTransitionRecord":
        return cls(
            from_state=AgentState(data["from_state"]),
            to_state=AgentState(data["to_state"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reason=data.get("reason"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PersistedState:
    """State persisted to disk for resume capability"""
    run_id: str
    state: AgentState
    state_since: datetime
    history: List[Dict]
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "state": self.state.value,
            "state_since": self.state_since.isoformat(),
            "history": self.history,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PersistedState":
        return cls(
            run_id=data["run_id"],
            state=AgentState(data["state"]),
            state_since=datetime.fromisoformat(data["state_since"]),
            history=data.get("history", []),
            metadata=data.get("metadata", {}),
        )


class AgentStateMachine:
    """
    Explicit state machine for agent lifecycle with disk persistence.

    Supports resume after restart by persisting state to disk.
    Every state transition is validated and logged.
    """

    def __init__(self, run_id: str, initial_state: AgentState = AgentState.QUEUED):
        self.run_id = run_id
        self._state = initial_state
        self._history: List[StateTransitionRecord] = []
        self._state_since = datetime.now()
        self._state_file = STATE_DIR / f"{run_id}.json"
        
        # Ensure state directory exists
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            "state_machine_init",
            run_id=run_id,
            initial_state=self._state.value
        )

    @property
    def state(self) -> AgentState:
        """Current state"""
        return self._state

    def is_terminal(self) -> bool:
        """True if in a terminal state"""
        return self._state in TERMINAL_STATES

    @property
    def is_running(self) -> bool:
        """True if actively processing (non-terminal and not queued)"""
        return (
            self._state not in TERMINAL_STATES
            and self._state != AgentState.QUEUED
        )

    @property
    def history(self) -> List[StateTransitionRecord]:
        """Full transition history"""
        return self._history.copy()

    @property
    def duration_seconds(self) -> float:
        """Time spent in current state"""
        return (datetime.now() - self._state_since).total_seconds()

    def can_transition_to(self, target: AgentState) -> bool:
        """Check if transition to target state is valid"""
        return target in VALID_TRANSITIONS.get(self._state, set())

    def can_transition(self, target: AgentState) -> bool:
        """Alias for can_transition_to for backward compatibility"""
        return self.can_transition_to(target)

    def transition(
        self,
        target: AgentState,
        reason: Optional[str] = None,
        **metadata
    ) -> StateTransitionRecord:
        """
        Transition to new state.

        Raises:
            StateTransitionError: If transition is not valid

        Returns:
            StateTransitionRecord of the transition
        """
        if not self.can_transition_to(target):
            raise StateTransitionError(self._state, target)

        record = StateTransitionRecord(
            from_state=self._state,
            to_state=target,
            timestamp=datetime.now(),
            reason=reason,
            metadata=metadata,
        )

        old_state = self._state
        self._state = target
        self._history.append(record)
        self._state_since = datetime.now()

        # Persist state to disk
        self._persist()

        logger.info(
            "state_transition",
            run_id=self.run_id,
            from_state=old_state.value,
            to_state=target.value,
            reason=reason,
            **metadata
        )

        return record

    def must_transition(
        self,
        target: AgentState,
        reason: Optional[str] = None,
        **metadata
    ) -> StateTransitionRecord:
        """
        Transition with assertion - raises if invalid.
        Use when transition SHOULD be valid but we want defensive handling.
        """
        try:
            return self.transition(target, reason, **metadata)
        except StateTransitionError as e:
            logger.error(
                "invalid_state_transition_attempt",
                run_id=self.run_id,
                current=e.current.value,
                attempted=e.target.value,
                reason=reason
            )
            raise

    def _persist(self) -> None:
        """Persist current state to disk"""
        try:
            persisted = PersistedState(
                run_id=self.run_id,
                state=self._state,
                state_since=self._state_since,
                history=[r.to_dict() for r in self._history],
            )
            self._state_file.write_text(json.dumps(persisted.to_dict(), indent=2))
            logger.debug("state_persisted", run_id=self.run_id, path=str(self._state_file))
        except Exception as e:
            logger.warning("state_persist_failed", run_id=self.run_id, error=str(e))

    def load(self) -> bool:
        """
        Load state from disk if available.

        Returns:
            True if state was loaded, False if no persisted state found
        """
        if not self._state_file.exists():
            return False

        try:
            data = json.loads(self._state_file.read_text())
            persisted = PersistedState.from_dict(data)

            self._state = persisted.state
            self._state_since = persisted.state_since
            self._history = [
                StateTransitionRecord.from_dict(h) for h in persisted.history
            ]

            logger.info(
                "state_loaded",
                run_id=self.run_id,
                state=self._state.value,
                transition_count=len(self._history)
            )
            return True

        except Exception as e:
            logger.error(
                "state_load_failed",
                run_id=self.run_id,
                error=str(e)
            )
            return False

    def clear_persistence(self) -> None:
        """Remove persisted state file"""
        try:
            if self._state_file.exists():
                self._state_file.unlink()
                logger.info("state_persistence_cleared", run_id=self.run_id)
        except Exception as e:
            logger.warning("state_clear_failed", run_id=self.run_id, error=str(e))

    def get_state_summary(self) -> Dict:
        """Get summary of current state for debugging"""
        last = self._history[-1] if self._history else None
        return {
            "run_id": self.run_id,
            "current_state": self._state.value,
            "is_terminal": self.is_terminal(),
            "is_running": self.is_running,
            "duration_seconds": self.duration_seconds,
            "transition_count": len(self._history),
            "last_transition": {
                "from": last.from_state.value if last else None,
                "to": last.to_state.value if last else None,
                "timestamp": last.timestamp.isoformat() if last else None,
            } if last else None,
            "state_file": str(self._state_file),
        }

    def get_valid_transitions(self) -> Set[AgentState]:
        """Get set of valid transitions from current state"""
        return VALID_TRANSITIONS.get(self._state, set()).copy()