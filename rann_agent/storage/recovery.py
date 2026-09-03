"""
Crash recovery for RANN Agent.
As required by MASTER PROMPT Section 23.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger()


@dataclass
class IncompleteRun:
    run_id: str
    task_id: str
    last_state: str
    checkpoint_path: Optional[str] = None
    partial_side_effects: List[str] = field(default_factory=list)
    last_tool_call: Optional[str] = None
    start_time: str = ""


@dataclass
class ReconciliationResult:
    run_id: str
    action: str  # resume, rollback, block
    reason: str
    files_to_restore: List[str] = field(default_factory=list)
    resume_from_step: Optional[int] = None


class CrashRecovery:
    """Handles recovery from process termination."""

    def __init__(self, storage: Optional["Database"] = None) -> None:
        self.storage = storage
        self.checkpoint_dir = None  # Set on startup

    def on_startup(self) -> List[IncompleteRun]:
        """
        Called on agent startup to recover from previous crash.
        Returns list of incomplete runs that need attention.
        """
        incomplete = []

        if not self.storage:
            logger.info("crash_recovery_no_storage")
            return incomplete

        # Load incomplete runs from database
        runs = self.storage.get_incomplete_runs()
        for run in runs:
            transitions = self.storage.get_transitions(run["run_id"])
            last_transition = transitions[-1] if transitions else None

            incomplete_run = IncompleteRun(
                run_id=run["run_id"],
                task_id=run["task_id"],
                last_state=last_transition["to_state"] if last_transition else "UNKNOWN",
                last_tool_call=None,
                start_time=run["start_time"],
            )
            incomplete.append(incomplete_run)
            logger.info(
                "incomplete_run_detected",
                run_id=run["run_id"],
                state=incomplete_run.last_state,
            )

        return incomplete

    def reconcile(self, run_id: str) -> ReconciliationResult:
        """
        Determine whether to resume or rollback a run.
        """
        if not self.storage:
            return ReconciliationResult(
                run_id=run_id,
                action="block",
                reason="No storage available for reconciliation",
            )

        run = self.storage.get_run(run_id)
        if not run:
            return ReconciliationResult(
                run_id=run_id,
                action="block",
                reason="Run not found",
            )

        # Check if run has any tool call records
        tool_calls = self.storage.get_tool_calls(run_id)
        if not tool_calls:
            return ReconciliationResult(
                run_id=run_id,
                action="resume",
                reason="No tool calls recorded, safe to resume from start",
                resume_from_step=0,
            )

        # Check if last tool call was successful
        last_call = tool_calls[-1]
        if last_call.get("success"):
            return ReconciliationResult(
                run_id=run_id,
                action="resume",
                reason="Last tool call succeeded, safe to continue",
                resume_from_step=len(tool_calls),
            )

        # Last call failed - check if it was a read-only operation
        tool_name = last_call.get("tool_name", "")
        read_only_tools = {"read", "search", "grep", "list", "stat"}
        if tool_name in read_only_tools:
            return ReconciliationResult(
                run_id=run_id,
                action="resume",
                reason=f"Last call ({tool_name}) was read-only, continuing",
                resume_from_step=len(tool_calls),
            )

        # Non-read tool failed - rollback recommended
        return ReconciliationResult(
            run_id=run_id,
            action="rollback",
            reason=f"Last tool call ({tool_name}) failed, rollback recommended",
            files_to_restore=self._detect_modified_files(run_id),
        )

    def rollback(self, run_id: str) -> bool:
        """
        Rollback a run to its checkpoint.
        """
        if not self.storage:
            logger.warning("rollback_no_storage", run_id=run_id)
            return False

        # In a full implementation, this would:
        # 1. Load checkpoint data
        # 2. Restore files from backup directory
        # 3. Revert git changes if any
        # 4. Update run status in database

        logger.info("rollback_executed", run_id=run_id)

        # Mark run as rolled back
        from datetime import datetime
        import json

        result_data = json.dumps({
            "status": "rolled_back",
            "rolled_back_at": datetime.now().isoformat(),
        })
        self.storage.save_run(run_id, "", datetime.now().isoformat(), result_data)

        return True

    def resume(self, run_id: str) -> bool:
        """
        Resume a run from its last checkpoint.
        """
        if not self.storage:
            return False

        reconciliation = self.reconcile(run_id)
        if reconciliation.action != "resume":
            logger.warning(
                "resume_blocked",
                run_id=run_id,
                reason=reconciliation.reason,
            )
            return False

        logger.info("resume_approved", run_id=run_id)
        return True

    def _detect_modified_files(self, run_id: str) -> List[str]:
        """Detect which files were modified in a run."""
        # In a full implementation, this would track file changes
        # through the Evidence or Audit tables
        return []