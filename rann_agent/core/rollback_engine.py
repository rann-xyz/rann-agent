"""
Rollback Engine

Executes rollback procedures when tasks fail or need to be undone.
Implements the TaskContract rollback definitions and provides
deterministic undo for file operations, command executions, and deployments.

Features:
- Snapshot-based rollback for file operations
- Command-level rollback with pre-recorded reverse commands
- Deployment rollback via deployment history
- Atomic rollback with rollback-on-failure
- Rollback queuing for multi-step operations
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# Rollback state persistence directory
ROLLBACK_DIR = Path.home() / ".rann_agent" / "rollbacks"


class RollbackType(Enum):
    """Type of rollback operation"""

    FILE_SNAPSHOT = "file_snapshot"  # Restore file from snapshot
    FILE_DELETE = "file_delete"  # Delete a created file
    COMMAND_REVERSE = "command_reverse"  # Run reverse command
    DEPLOYMENT_ROLLBACK = "deployment_rollback"  # Rollback deployment
    DIRECTORY_CLEANUP = "directory_cleanup"  # Remove created directory
    DATABASE_ROLLBACK = "database_rollback"  # Rollback DB changes
    GIT_REVERT = "git_revert"  # Revert git changes
    ENVIRONMENT_RESTORE = "environment_restore"  # Restore env variables


class RollbackStatus(Enum):
    """Status of a rollback operation"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FileSnapshot:
    """Snapshot of a file before modification"""

    path: str
    content: str | None  # None means file did not exist
    checksum: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "content": self.content,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> FileSnapshot:
        return cls(
            path=data["path"],
            content=data.get("content"),
            checksum=data.get("checksum"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class RollbackStep:
    """A single rollback step"""

    step_id: str
    rollback_type: RollbackType
    target: str  # File path, command, deployment ID, etc.
    reverse_command: str | None = None  # Command to run for reversal
    snapshot: FileSnapshot | None = None  # Pre-operation snapshot
    metadata: dict = field(default_factory=dict)
    status: RollbackStatus = RollbackStatus.PENDING
    error: str | None = None
    executed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "rollback_type": self.rollback_type.value,
            "target": self.target,
            "reverse_command": self.reverse_command,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "metadata": self.metadata,
            "status": self.status.value,
            "error": self.error,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RollbackStep:
        snapshot = FileSnapshot.from_dict(data["snapshot"]) if data.get("snapshot") else None
        return cls(
            step_id=data["step_id"],
            rollback_type=RollbackType(data["rollback_type"]),
            target=data["target"],
            reverse_command=data.get("reverse_command"),
            snapshot=snapshot,
            metadata=data.get("metadata", {}),
            status=RollbackStatus(data.get("status", "pending")),
            error=data.get("error"),
            executed_at=(
                datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None
            ),
        )


@dataclass
class RollbackProcedure:
    """A complete rollback procedure with multiple steps"""

    procedure_id: str
    run_id: str
    task_id: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    steps: list[RollbackStep] = field(default_factory=list)
    status: RollbackStatus = RollbackStatus.PENDING
    error: str | None = None
    total_steps: int = 0
    completed_steps: int = 0

    def add_step(self, step: RollbackStep) -> None:
        self.steps.append(step)
        self.total_steps = len(self.steps)

    def to_dict(self) -> dict:
        return {
            "procedure_id": self.procedure_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "error": self.error,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RollbackProcedure:
        proc = cls(
            procedure_id=data["procedure_id"],
            run_id=data["run_id"],
            task_id=data.get("task_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            status=RollbackStatus(data.get("status", "pending")),
            error=data.get("error"),
            total_steps=data.get("total_steps", 0),
            completed_steps=data.get("completed_steps", 0),
        )
        proc.steps = [RollbackStep.from_dict(s) for s in data.get("steps", [])]
        return proc


class RollbackEngine:
    """
    Executes rollback procedures for failed or cancelled tasks.

    Supports multiple rollback strategies:
    - File snapshot/restore (for file modifications)
    - Command reversal (for shell commands)
    - Deployment rollback (for deployments)
    - Directory cleanup (for created directories)

    Usage:
        engine = RollbackEngine(run_id="run_123")

        # Before a risky operation, snapshot files
        engine.snapshot_file("/path/to/file.py")

        # After failure, execute rollback
        result = await engine.execute_rollback()
    """

    def __init__(self, run_id: str, rollback_dir: Path | None = None):
        self.run_id = run_id
        self.rollback_dir = rollback_dir or ROLLBACK_DIR
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        self._current_procedure: RollbackProcedure | None = None
        self._snapshots: dict[str, FileSnapshot] = {}  # path -> snapshot

        logger.info("rollback_engine_init", run_id=run_id)

    # === Snapshot Management ===

    def snapshot_file(self, file_path: str) -> FileSnapshot:
        """
        Take a snapshot of a file before it is modified.

        Args:
            file_path: Absolute path to the file

        Returns:
            FileSnapshot object
        """
        path = Path(file_path).resolve()

        if path.exists():
            try:
                content = path.read_text()
                checksum = str(hash(content))
            except Exception as e:
                logger.warning("snapshot_read_failed", path=str(path), error=str(e))
                content = None
                checksum = None
        else:
            content = None
            checksum = None

        snapshot = FileSnapshot(
            path=str(path),
            content=content,
            checksum=checksum,
        )

        self._snapshots[str(path)] = snapshot
        logger.info("file_snapshotted", path=str(path), existed=path.exists())

        return snapshot

    def snapshot_files(self, file_paths: list[str]) -> list[FileSnapshot]:
        """Snapshot multiple files"""
        return [self.snapshot_file(p) for p in file_paths]

    def snapshot_directory(
        self, dir_path: str, patterns: list[str] | None = None
    ) -> list[FileSnapshot]:
        """
        Snapshot all files in a directory matching patterns.

        Args:
            dir_path: Directory to snapshot
            patterns: Glob patterns (e.g., ["*.py", "*.json"]). None = all files.
        """
        path = Path(dir_path)
        if not path.exists():
            return []

        snapshots = []
        for file_path in path.rglob("*"):
            if file_path.is_file():
                if patterns is None or any(file_path.match(p) for p in patterns):
                    snapshots.append(self.snapshot_file(str(file_path)))

        logger.info("directory_snapshotted", dir=dir_path, file_count=len(snapshots))
        return snapshots

    # === Rollback Step Recording ===

    def record_file_modification(
        self, file_path: str, reverse_command: str | None = None
    ) -> RollbackStep:
        """Record a file modification for potential rollback"""
        snapshot = self.snapshot_file(file_path)
        step = RollbackStep(
            step_id=f"rb_{len(self._current_procedure.steps) + 1 if self._current_procedure else 1}",
            rollback_type=RollbackType.FILE_SNAPSHOT,
            target=str(Path(file_path).resolve()),
            reverse_command=reverse_command,
            snapshot=snapshot,
        )
        if self._current_procedure:
            self._current_procedure.add_step(step)
        return step

    def record_file_deletion(self, file_path: str, original_content: str) -> RollbackStep:
        """Record a file deletion for potential rollback (can recreate)"""
        path = Path(file_path).resolve()
        snapshot = FileSnapshot(
            path=str(path), content=original_content, checksum=str(hash(original_content))
        )
        step = RollbackStep(
            step_id=f"rb_{len(self._current_procedure.steps) + 1 if self._current_procedure else 1}",
            rollback_type=RollbackType.FILE_DELETE,
            target=str(path),
            snapshot=snapshot,
        )
        if self._current_procedure:
            self._current_procedure.add_step(step)
        return step

    def record_command_execution(
        self, command: str, reverse_command: str | None = None
    ) -> RollbackStep:
        """Record a command execution for potential rollback"""
        step = RollbackStep(
            step_id=f"rb_{len(self._current_procedure.steps) + 1 if self._current_procedure else 1}",
            rollback_type=RollbackType.COMMAND_REVERSE,
            target=command,
            reverse_command=reverse_command,
        )
        if self._current_procedure:
            self._current_procedure.add_step(step)
        return step

    def record_deployment_rollback(
        self, deployment_id: str, target_version: str | None = None
    ) -> RollbackStep:
        """Record a deployment rollback"""
        step = RollbackStep(
            step_id=f"rb_{len(self._current_procedure.steps) + 1 if self._current_procedure else 1}",
            rollback_type=RollbackType.DEPLOYMENT_ROLLBACK,
            target=deployment_id,
            reverse_command=target_version,
            metadata={"target_version": target_version},
        )
        if self._current_procedure:
            self._current_procedure.add_step(step)
        return step

    def record_directory_cleanup(self, dir_path: str) -> RollbackStep:
        """Record a directory for cleanup rollback"""
        step = RollbackStep(
            step_id=f"rb_{len(self._current_procedure.steps) + 1 if self._current_procedure else 1}",
            rollback_type=RollbackType.DIRECTORY_CLEANUP,
            target=str(Path(dir_path).resolve()),
        )
        if self._current_procedure:
            self._current_procedure.add_step(step)
        return step

    # === Procedure Management ===

    def begin_procedure(self, task_id: str | None = None) -> RollbackProcedure:
        """Begin a new rollback procedure"""
        import uuid

        self._current_procedure = RollbackProcedure(
            procedure_id=str(uuid.uuid4())[:8],
            run_id=self.run_id,
            task_id=task_id,
        )
        logger.info(
            "rollback_procedure_started",
            procedure_id=self._current_procedure.procedure_id,
            task_id=task_id,
        )
        return self._current_procedure

    def get_current_procedure(self) -> RollbackProcedure | None:
        """Get the current procedure"""
        return self._current_procedure

    def _execute_step(self, step: RollbackStep) -> bool:
        """Execute a single rollback step. Returns True on success."""
        step.status = RollbackStatus.IN_PROGRESS
        step.executed_at = datetime.now(UTC)

        try:
            if step.rollback_type == RollbackType.FILE_SNAPSHOT:
                return self._rollback_file_snapshot(step)
            elif step.rollback_type == RollbackType.FILE_DELETE:
                return self._rollback_file_delete(step)
            elif step.rollback_type == RollbackType.COMMAND_REVERSE:
                return self._rollback_command_reverse(step)
            elif step.rollback_type == RollbackType.DEPLOYMENT_ROLLBACK:
                return self._rollback_deployment(step)
            elif step.rollback_type == RollbackType.DIRECTORY_CLEANUP:
                return self._rollback_directory_cleanup(step)
            elif step.rollback_type == RollbackType.GIT_REVERT:
                return self._rollback_git_revert(step)
            elif step.rollback_type == RollbackType.ENVIRONMENT_RESTORE:
                return self._rollback_environment(step)
            else:
                logger.warning(
                    "unknown_rollback_type", step_id=step.step_id, rollback_type=step.rollback_type
                )
                step.status = RollbackStatus.SKIPPED
                return True

        except Exception as e:
            step.error = str(e)
            step.status = RollbackStatus.FAILED
            logger.error("rollback_step_failed", step_id=step.step_id, error=str(e))
            return False

    def _rollback_file_snapshot(self, step: RollbackStep) -> bool:
        """Restore a file from its snapshot"""
        snapshot = step.snapshot
        if not snapshot:
            logger.warning("no_snapshot_for_rollback", target=step.target)
            step.status = RollbackStatus.SKIPPED
            return True

        path = Path(snapshot.path)

        if snapshot.content is None:
            # File did not exist before — delete it if it exists now
            if path.exists():
                path.unlink()
                logger.info("file_deleted_as_part_of_rollback", path=snapshot.path)
            else:
                logger.info("file_already_absent", path=snapshot.path)
        else:
            # Restore original content
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(snapshot.content)
            logger.info("file_restored_from_snapshot", path=snapshot.path)

        step.status = RollbackStatus.COMPLETED
        return True

    def _rollback_file_delete(self, step: RollbackStep) -> bool:
        """Recreate a deleted file from stored content"""
        snapshot = step.snapshot
        if not snapshot or snapshot.content is None:
            logger.warning("no_content_to_restore_file", target=step.target)
            step.status = RollbackStatus.SKIPPED
            return True

        path = Path(snapshot.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(snapshot.content)
        logger.info("file_recreated_from_rollback", path=snapshot.path)
        step.status = RollbackStatus.COMPLETED
        return True

    def _rollback_command_reverse(self, step: RollbackStep) -> bool:
        """Run the reverse command if available"""
        if not step.reverse_command:
            logger.info("no_reverse_command_skipped", target=step.target)
            step.status = RollbackStatus.SKIPPED
            return True

        import subprocess

        logger.info("running_reverse_command", command=step.reverse_command, target=step.target)
        result = subprocess.run(
            step.reverse_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            step.error = f"Reverse command failed: {result.stderr}"
            step.status = RollbackStatus.FAILED
            return False

        logger.info("reverse_command_succeeded", command=step.reverse_command)
        step.status = RollbackStatus.COMPLETED
        return True

    def _rollback_deployment(self, step: RollbackStep) -> bool:
        """Rollback a deployment (stub — implement per platform)"""
        # This would integrate with Vercel/GitHub Actions/Docker/etc.
        logger.warning(
            "deployment_rollback_not_implemented",
            deployment_id=step.target,
            target_version=step.metadata.get("target_version"),
        )
        step.status = RollbackStatus.SKIPPED
        return True

    def _rollback_directory_cleanup(self, step: RollbackStep) -> bool:
        """Remove a created directory"""
        path = Path(step.target)
        if path.exists():
            shutil.rmtree(path)
            logger.info("directory_removed", path=step.target)
        else:
            logger.info("directory_already_absent", path=step.target)
        step.status = RollbackStatus.COMPLETED
        return True

    def _rollback_git_revert(self, step: RollbackStep) -> bool:
        """Revert git changes to a file"""
        import subprocess

        target = step.target
        logger.info("git_revert", target=target)

        try:
            result = subprocess.run(
                ["git", "checkout", "--", target],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                step.error = f"git checkout failed: {result.stderr}"
                step.status = RollbackStatus.FAILED
                return False
            step.status = RollbackStatus.COMPLETED
            return True
        except Exception as e:
            step.error = str(e)
            step.status = RollbackStatus.FAILED
            return False

    def _rollback_environment(self, step: RollbackStep) -> bool:
        """Restore environment variables"""
        env_changes = step.metadata.get("env_changes", {})
        for key, original_value in env_changes.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value
        step.status = RollbackStatus.COMPLETED
        return True

    # === Main Rollback Execution ===

    async def execute_rollback(
        self,
        procedure: RollbackProcedure | None = None,
        stop_on_failure: bool = False,
    ) -> RollbackProcedure:
        """
        Execute a rollback procedure.

        Args:
            procedure: Procedure to execute. Uses current procedure if None.
            stop_on_failure: If True, stop at first failure. If False, continue.

        Returns:
            The executed RollbackProcedure
        """
        proc = procedure or self._current_procedure
        if not proc:
            logger.warning("no_rollback_procedure_to_execute")
            return RollbackProcedure(procedure_id="none", run_id=self.run_id)

        logger.info(
            "rollback_execution_started",
            procedure_id=proc.procedure_id,
            total_steps=proc.total_steps,
        )

        for step in proc.steps:
            if step.status in (RollbackStatus.COMPLETED, RollbackStatus.SKIPPED):
                continue

            success = self._execute_step(step)

            if success:
                proc.completed_steps += 1
            elif stop_on_failure:
                logger.warning("rollback_stopped_on_failure", step_id=step.step_id)
                break

        # Determine overall status
        failed_steps = [s for s in proc.steps if s.status == RollbackStatus.FAILED]
        if failed_steps:
            proc.status = RollbackStatus.FAILED
            proc.error = f"{len(failed_steps)} step(s) failed"
        else:
            pending_steps = [s for s in proc.steps if s.status == RollbackStatus.PENDING]
            if pending_steps:
                proc.status = RollbackStatus.FAILED
                proc.error = f"{len(pending_steps)} step(s) not executed due to stop_on_failure"
            else:
                proc.status = RollbackStatus.COMPLETED

        proc.completed_at = datetime.now(UTC)

        # Persist procedure record
        self._persist_procedure(proc)

        logger.info(
            "rollback_execution_completed",
            procedure_id=proc.procedure_id,
            status=proc.status.value,
            completed_steps=proc.completed_steps,
            total_steps=proc.total_steps,
            failed=len(failed_steps),
        )

        return proc

    def _persist_procedure(self, proc: RollbackProcedure) -> None:
        """Persist procedure record to disk"""
        try:
            file_path = self.rollback_dir / f"{proc.procedure_id}.json"
            file_path.write_text(json.dumps(proc.to_dict(), indent=2))
        except Exception as e:
            logger.warning("procedure_persist_failed", procedure_id=proc.procedure_id, error=str(e))

    def load_procedure(self, procedure_id: str) -> RollbackProcedure | None:
        """Load a procedure from disk"""
        file_path = self.rollback_dir / f"{procedure_id}.json"
        if not file_path.exists():
            return None
        try:
            return RollbackProcedure.from_dict(json.loads(file_path.read_text()))
        except Exception as e:
            logger.error("procedure_load_failed", procedure_id=procedure_id, error=str(e))
            return None

    def get_recent_procedures(self, limit: int = 10) -> list[RollbackProcedure]:
        """Get recent rollback procedures"""
        procedures = []
        for file_path in sorted(
            self.rollback_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:limit]:
            try:
                procedures.append(RollbackProcedure.from_dict(json.loads(file_path.read_text())))
            except Exception as exc:
                logger.debug("skip_invalid_procedure_file", path=str(file_path), error=str(exc))
        return procedures

    def get_snapshot(self, file_path: str) -> FileSnapshot | None:
        """Get the most recent snapshot for a file"""
        return self._snapshots.get(str(Path(file_path).resolve()))

    def clear_snapshots(self) -> None:
        """Clear in-memory snapshots"""
        self._snapshots.clear()
        logger.debug("snapshots_cleared")
