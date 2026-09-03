"""
Event bus for RANN Agent.
As required by MASTER PROMPT Section 48.
"""

from dataclasses import dataclass, field
from typing import Dict, Callable, List, Any, Optional
from enum import Enum
from datetime import datetime
import structlog

logger = structlog.get_logger()


class EventType(Enum):
    # Task events
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    # Tool events
    TOOL_CALLED = "tool_called"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    # File events
    FILE_CHANGED = "file_changed"
    # Verification events
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    # Recovery events
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    # Learning events
    LEARNING_EPISODE_CREATED = "learning_episode_created"
    LESSON_EXTRACTED = "lesson_extracted"
    # Memory events
    MEMORY_STORED = "memory_stored"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_CONFLICT_DETECTED = "memory_conflict_detected"
    # Skill events
    SKILL_CANDIDATE_CREATED = "skill_candidate_created"
    SKILL_VALIDATED = "skill_validated"
    SKILL_PROMOTED = "skill_promoted"
    SKILL_REJECTED = "skill_rejected"
    SKILL_ROLLED_BACK = "skill_rolled_back"
    # Experiment events
    EXPERIMENT_STARTED = "experiment_started"
    EXPERIMENT_COMPLETED = "experiment_completed"
    # Regression
    REGRESSION_DETECTED = "regression_detected"
    ROLLBACK_COMPLETED = "rollback_completed"


@dataclass
class Event:
    event_type: EventType
    timestamp: str
    data: Dict[str, Any]
    trace_id: Optional[str] = None
    run_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class EventBus:
    """Pub/sub event bus for RANN Agent."""

    _instance: Optional["EventBus"] = None

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._handlers: Dict[EventType, List[Callable[[Event], None]]] = {
            et: [] for et in EventType
        }
        logger.info("event_bus_initialized")

    def subscribe(
        self, event_type: EventType, handler: Callable[[Event], None]
    ) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug("event_subscribed", event_type=event_type.value)

    def unsubscribe(
        self, event_type: EventType, handler: Callable[[Event], None]
    ) -> None:
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug("event_unsubscribed", event_type=event_type.value)

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "event_handler_error",
                    event_type=event.event_type.value,
                    handler=handler.__name__,
                    error=str(e),
                )

        logger.debug(
            "event_published",
            event_type=event.event_type.value,
            handler_count=len(handlers),
        )

    def emit(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """Convenience method to emit an event."""
        event = Event(
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            data=data or {},
            trace_id=trace_id,
            run_id=run_id,
        )
        self.publish(event)

    def clear_handlers(self, event_type: Optional[EventType] = None) -> None:
        """Clear handlers for a specific event type, or all if None."""
        if event_type:
            self._handlers[event_type] = []
        else:
            for et in EventType:
                self._handlers[et] = []

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None