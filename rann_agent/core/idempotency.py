"""
Idempotency tracking for RANN Agent.
As required by MASTER PROMPT Section 19.
"""

from enum import Enum
from typing import Any, Optional
import structlog

logger = structlog.get_logger()


class IdempotencyLevel(Enum):
    IDEMPOTENT = "idempotent"  # read, search, list
    PARTIALLY_IDEMPOTENT = "partially_idempotent"  # write (depends)
    NON_IDEMPOTENT = "non_idempotent"  # delete, migration, deployment


# Declare idempotency levels for standard operations
OPERATION_IDEMPOTENCY: dict[str, IdempotencyLevel] = {
    "read": IdempotencyLevel.IDEMPOTENT,
    "search": IdempotencyLevel.IDEMPOTENT,
    "grep": IdempotencyLevel.IDEMPOTENT,
    "list": IdempotencyLevel.IDEMPOTENT,
    "stat": IdempotencyLevel.IDEMPOTENT,
    "write": IdempotencyLevel.PARTIALLY_IDEMPOTENT,
    "edit": IdempotencyLevel.PARTIALLY_IDEMPOTENT,
    "patch": IdempotencyLevel.PARTIALLY_IDEMPOTENT,
    "mkdir": IdempotencyLevel.PARTIALLY_IDEMPOTENT,
    "test": IdempotencyLevel.IDEMPOTENT,
    "run": IdempotencyLevel.IDEMPOTENT,
    "delete": IdempotencyLevel.NON_IDEMPOTENT,
    "rm": IdempotencyLevel.NON_IDEMPOTENT,
    "migration": IdempotencyLevel.NON_IDEMPOTENT,
    "deploy": IdempotencyLevel.NON_IDEMPOTENT,
}


class OperationTracker:
    """Tracks operations to prevent duplicate execution."""

    def __init__(self, storage: Optional["Database"] = None) -> None:
        self.storage = storage
        self._seen: set[str] = set()

    def is_dup(self, operation_id: str) -> bool:
        """Check if an operation has already been executed."""
        if operation_id in self._seen:
            return True
        if self.storage and self.storage.is_duplicate_operation(operation_id):
            self._seen.add(operation_id)
            return True
        return False

    def record(self, operation_id: str, result: Any = None) -> None:
        """Record a completed operation."""
        self._seen.add(operation_id)
        if self.storage:
            import json
            result_json = json.dumps({"result": str(result)}) if result is not None else None
            self.storage.record_operation(operation_id, result_json)
        logger.debug("operation_recorded", operation_id=operation_id)

    def clear_old(self, older_than_hours: int = 24) -> int:
        """Clear old operation records."""
        self._seen.clear()
        if self.storage:
            return self.storage.clear_old_operations(older_than_hours)
        return 0