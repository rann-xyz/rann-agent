"""
Agent Event System

Structured events as required by MASTER PROMPT Section 8.
Every event contains: run_id, task_id, timestamp, component, status, metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict
import json
import structlog

logger = structlog.get_logger()


class EventType(Enum):
    """All possible event types"""
    RUN_CREATED = "run_created"
    RUN_STARTED = "run_started"
    CONTEXT_BUILT = "context_built"
    PLAN_CREATED = "plan_created"
    TASK_STARTED = "task_started"
    MODEL_REQUESTED = "model_requested"
    MODEL_RESPONDED = "model_responded"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    OBSERVATION_CREATED = "observation_created"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    RECOVERY_STARTED = "recovery_started"
    ROLLBACK_STARTED = "rollback_started"
    CHECKPOINT_CREATED = "checkpoint_created"
    MEMORY_RETRIEVED = "memory_retrieved"
    MEMORY_STORED = "memory_stored"
    SKILL_UPDATED = "skill_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    RUN_COMPLETED = "run_completed"
    STATE_CHANGED = "state_changed"
    ERROR_OCCURRED = "error_occurred"
    BUDGET_UPDATED = "budget_updated"


class EventStatus(Enum):
    """Event status values"""
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


@dataclass
class Event:
    """
    Base event class.
    
    All events contain:
    - run_id: Unique run identifier
    - task_id: Optional task identifier  
    - timestamp: When event occurred
    - component: Which component generated the event
    - status: Event status
    - metadata: Additional event-specific data
    """
    event_type: EventType
    run_id: str
    task_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    component: str = "agent"
    status: EventStatus = EventStatus.STARTED
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "event_type": self.event_type.value,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "status": self.status.value,
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Deserialize from dictionary"""
        return cls(
            event_type=EventType(data["event_type"]),
            run_id=data["run_id"],
            task_id=data.get("task_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            component=data.get("component", "agent"),
            status=EventStatus(data.get("status", "started")),
            metadata=data.get("metadata", {}),
        )


class EventEmitter:
    """
    Emits structured events to logger and optional event store.
    
    All agent components should use this to emit events
    instead of direct logging.
    """
    
    def __init__(self, run_id: str, store_events: bool = True):
        self.run_id = run_id
        self.store_events = store_events
        self._events: list[Event] = []
        self._event_counts: Dict[EventType, int] = {}
        self._log = structlog.get_logger().bind(component="event_emitter")
        
        self._log.info("event_emitter_init", run_id=run_id)
    
    def emit(self, event: Event) -> None:
        """
        Emit an event.
        
        - Logs the event
        - Stores in memory if store_events=True
        - Counts by type
        """
        # Ensure run_id matches
        event.run_id = self.run_id
        
        # Count
        self._event_counts[event.event_type] = self._event_counts.get(event.event_type, 0) + 1
        
        # Store
        if self.store_events:
            self._events.append(event)
        
        # Log
        log_data = {
            "event_type": event.event_type.value,
            "run_id": event.run_id,
            "task_id": event.task_id,
            "status": event.status.value,
            "component": event.component,
            **event.metadata
        }
        
        if event.status == EventStatus.FAILURE:
            self._log.error("agent_event", **log_data)
        elif event.status == EventStatus.SUCCESS:
            self._log.info("agent_event", **log_data)
        else:
            self._log.debug("agent_event", **log_data)
    
    def create_event(
        self,
        event_type: EventType,
        component: str = "agent",
        task_id: Optional[str] = None,
        status: EventStatus = EventStatus.STARTED,
        **metadata
    ) -> Event:
        """Create and emit an event in one call"""
        event = Event(
            event_type=event_type,
            run_id=self.run_id,
            task_id=task_id,
            component=component,
            status=status,
            metadata=metadata
        )
        self.emit(event)
        return event
    
    def get_events(
        self,
        event_type: Optional[EventType] = None,
        component: Optional[str] = None,
        status: Optional[EventStatus] = None
    ) -> list[Event]:
        """Get filtered events"""
        result = self._events
        
        if event_type:
            result = [e for e in result if e.event_type == event_type]
        if component:
            result = [e for e in result if e.component == component]
        if status:
            result = [e for e in result if e.status == status]
        
        return result
    
    def get_trace(self) -> list[Dict[str, Any]]:
        """Get full event trace for observability"""
        return [e.to_dict() for e in self._events]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get event summary statistics"""
        return {
            "run_id": self.run_id,
            "total_events": len(self._events),
            "event_counts": {k.value: v for k, v in self._event_counts.items()},
            "status_counts": {
                "success": len(self.get_events(status=EventStatus.SUCCESS)),
                "failure": len(self.get_events(status=EventStatus.FAILURE)),
                "started": len(self.get_events(status=EventStatus.STARTED)),
                "skipped": len(self.get_events(status=EventStatus.SKIPPED)),
            }
        }


# Convenience functions for common events
def emit_run_created(emitter: EventEmitter, goal: str, **metadata) -> Event:
    return emitter.create_event(EventType.RUN_CREATED, goal=goal, **metadata)

def emit_run_started(emitter: EventEmitter, **metadata) -> Event:
    return emitter.create_event(EventType.RUN_STARTED, status=EventStatus.SUCCESS, **metadata)

def emit_model_requested(emitter: EventEmitter, model: str, **metadata) -> Event:
    return emitter.create_event(EventType.MODEL_REQUESTED, component="llm", model=model, **metadata)

def emit_model_responded(emitter: EventEmitter, model: str, tokens: int, **metadata) -> Event:
    return emitter.create_event(
        EventType.MODEL_RESPONDED, 
        component="llm", 
        status=EventStatus.SUCCESS,
        model=model, 
        tokens=tokens,
        **metadata
    )

def emit_tool_started(emitter: EventEmitter, tool: str, **metadata) -> Event:
    return emitter.create_event(EventType.TOOL_STARTED, component="tools", tool=tool, **metadata)

def emit_tool_completed(emitter: EventEmitter, tool: str, duration_ms: float, **metadata) -> Event:
    return emitter.create_event(
        EventType.TOOL_COMPLETED,
        component="tools",
        status=EventStatus.SUCCESS,
        tool=tool,
        duration_ms=duration_ms,
        **metadata
    )

def emit_tool_failed(emitter: EventEmitter, tool: str, error: str, **metadata) -> Event:
    return emitter.create_event(
        EventType.TOOL_FAILED,
        component="tools",
        status=EventStatus.FAILURE,
        tool=tool,
        error=error,
        **metadata
    )

def emit_verification_passed(emitter: EventEmitter, **metadata) -> Event:
    return emitter.create_event(EventType.VERIFICATION_PASSED, status=EventStatus.SUCCESS, **metadata)

def emit_verification_failed(emitter: EventEmitter, reason: str, **metadata) -> Event:
    return emitter.create_event(
        EventType.VERIFICATION_FAILED,
        status=EventStatus.FAILURE,
        reason=reason,
        **metadata
    )

def emit_run_completed(emitter: EventEmitter, output: str, turns: int, **metadata) -> Event:
    return emitter.create_event(
        EventType.RUN_COMPLETED,
        status=EventStatus.SUCCESS,
        output_length=len(output),
        turns=turns,
        **metadata
    )

def emit_error(emitter: EventEmitter, error: str, component: str = "agent", **metadata) -> Event:
    return emitter.create_event(
        EventType.ERROR_OCCURRED,
        component=component,
        status=EventStatus.FAILURE,
        error=error,
        **metadata
    )