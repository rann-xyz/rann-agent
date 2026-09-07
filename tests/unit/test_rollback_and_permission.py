"""
Tests for RollbackEngine and ToolPermissionLayer.

Covers:
- RollbackEngine: snapshot/restore files, rollback procedures,
  step execution, command reversal, directory cleanup
- ToolPermissionLayer: allowlist/denylist, risk-based gating,
  prohibited_actions, approval workflow, audit logging
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from rann_agent.core.rollback_engine import (
    RollbackEngine,
    RollbackProcedure,
    RollbackStatus,
    RollbackStep,
    RollbackType,
)
from rann_agent.core.tool_permission import (
    PermissionDecision,
    PolicyCheckResult,
    ToolCategory,
    ToolDefinition,
    ToolPermissionLayer,
)

# =============================================================================
# RollbackEngine Tests
# =============================================================================


class TestFileSnapshot:
    """Snapshot and restore file operations"""

    def test_snapshot_new_file(self, tmp_path):
        """Snapshot of non-existent file stores None content"""
        engine = RollbackEngine(run_id="test_snapshot_new")
        new_file = tmp_path / "nonexistent.py"
        snapshot = engine.snapshot_file(str(new_file))

        assert snapshot.content is None
        assert snapshot.path == str(new_file.resolve())

    def test_snapshot_existing_file(self, tmp_path):
        """Snapshot of existing file stores content"""
        engine = RollbackEngine(run_id="test_snapshot_existing")
        test_file = tmp_path / "existing.py"
        test_file.write_text("original content")

        snapshot = engine.snapshot_file(str(test_file))

        assert snapshot.content == "original content"
        assert snapshot.checksum is not None

    def test_snapshot_multiple_files(self, tmp_path):
        """Snapshot multiple files at once"""
        engine = RollbackEngine(run_id="test_snapshot_multi")
        files = []
        for i in range(3):
            f = tmp_path / f"file_{i}.py"
            f.write_text(f"content {i}")
            files.append(str(f))

        snapshots = engine.snapshot_files(files)

        assert len(snapshots) == 3
        assert all(s.content is not None for s in snapshots)


class TestRollbackProcedure:
    """Rollback procedure management"""

    def test_begin_procedure(self):
        """begin_procedure creates a new procedure"""
        engine = RollbackEngine(run_id="test_begin")
        proc = engine.begin_procedure(task_id="task_123")

        assert proc.run_id == "test_begin"
        assert proc.task_id == "task_123"
        assert proc.status == RollbackStatus.PENDING
        assert proc.total_steps == 0

    def test_record_file_modification(self):
        """record_file_modification adds a step to current procedure"""
        engine = RollbackEngine(run_id="test_record")
        engine.begin_procedure()

        step = engine.record_file_modification("/tmp/test.py")

        assert step.rollback_type == RollbackType.FILE_SNAPSHOT
        assert step.snapshot is not None
        assert engine._current_procedure.total_steps == 1

    def test_record_command_execution(self):
        """record_command_execution stores reverse command"""
        engine = RollbackEngine(run_id="test_cmd")
        engine.begin_procedure()

        step = engine.record_command_execution("git checkout main", reverse_command="git checkout dev")

        assert step.rollback_type == RollbackType.COMMAND_REVERSE
        assert step.target == "git checkout main"
        assert step.reverse_command == "git checkout dev"

    def test_record_directory_cleanup(self):
        """record_directory_cleanup adds cleanup step"""
        engine = RollbackEngine(run_id="test_dir")
        engine.begin_procedure()

        step = engine.record_directory_cleanup("/tmp/generated_dir")

        assert step.rollback_type == RollbackType.DIRECTORY_CLEANUP
        assert "/tmp/generated_dir" in step.target


class TestRollbackExecution:
    """Actual rollback execution"""

    def test_rollback_file_restore(self, tmp_path):
        """Rollback restores file to original content"""
        engine = RollbackEngine(run_id="test_rb_file")
        test_file = tmp_path / "to_restore.txt"
        test_file.write_text("ORIGINAL")

        # Snapshot BEFORE modification (correct usage)
        engine.begin_procedure()
        engine.record_file_modification(str(test_file))

        # Now modify
        test_file.write_text("MODIFIED")
        proc = engine._current_procedure

        result = self._run_sync(engine.execute_rollback(proc))

        assert result.status == RollbackStatus.COMPLETED
        assert test_file.read_text() == "ORIGINAL"

    def test_rollback_file_delete_restore(self, tmp_path):
        """Rollback can recreate a deleted file"""
        engine = RollbackEngine(run_id="test_rb_del")
        test_file = tmp_path / "deleted.txt"
        original_content = "THIS FILE WAS DELETED"
        test_file.write_text(original_content)

        engine.begin_procedure()
        engine.record_file_deletion(str(test_file), original_content)
        proc = engine._current_procedure
        test_file.unlink()

        result = self._run_sync(engine.execute_rollback(proc))

        assert result.status == RollbackStatus.COMPLETED
        assert test_file.read_text() == original_content

    def test_rollback_directory_cleanup(self, tmp_path):
        """Rollback removes created directory"""
        engine = RollbackEngine(run_id="test_rb_dir")
        created_dir = tmp_path / "to_be_removed"
        created_dir.mkdir()
        (created_dir / "file.txt").write_text("hello")

        engine.begin_procedure()
        engine.record_directory_cleanup(str(created_dir))
        proc = engine._current_procedure

        result = self._run_sync(engine.execute_rollback(proc))

        assert result.status == RollbackStatus.COMPLETED
        assert not created_dir.exists()

    def test_rollback_nonexistent_file(self, tmp_path):
        """Rollback handles file that doesn't exist gracefully"""
        engine = RollbackEngine(run_id="test_rb_missing")
        engine.begin_procedure()
        engine.record_file_modification(str(tmp_path / "does_not_exist.txt"))
        proc = engine._current_procedure

        result = self._run_sync(engine.execute_rollback(proc))

        assert result.status == RollbackStatus.COMPLETED

    def test_rollback_multiple_steps_all_complete(self, tmp_path):
        """Multiple rollback steps all complete"""
        engine = RollbackEngine(run_id="test_rb_multi")
        f1 = tmp_path / "f1.txt"
        f2 = tmp_path / "f2.txt"
        f1.write_text("file1")
        f2.write_text("file2")

        engine.begin_procedure()
        engine.record_file_modification(str(f1))
        engine.record_file_modification(str(f2))

        f1.write_text("mod1")
        f2.write_text("mod2")
        proc = engine._current_procedure

        result = self._run_sync(engine.execute_rollback(proc))

        assert result.status == RollbackStatus.COMPLETED
        assert f1.read_text() == "file1"
        assert f2.read_text() == "file2"
        assert result.completed_steps == 2

    @staticmethod
    def _run_sync(coro):
        """Run an async coroutine synchronously for testing."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return asyncio.run(coro)

    def test_procedure_serialization(self):
        """RollbackProcedure serializes and deserializes correctly"""
        proc = RollbackProcedure(procedure_id="test_proc", run_id="run_1", task_id="task_1")
        step = RollbackStep(
            step_id="rb_1",
            rollback_type=RollbackType.FILE_SNAPSHOT,
            target="/tmp/test.txt",
        )
        proc.add_step(step)

        data = proc.to_dict()
        restored = RollbackProcedure.from_dict(data)

        assert restored.procedure_id == "test_proc"
        assert restored.run_id == "run_1"
        assert len(restored.steps) == 1
        assert restored.steps[0].rollback_type == RollbackType.FILE_SNAPSHOT


# =============================================================================
# ToolPermissionLayer Tests
# =============================================================================


class TestToolDefinition:
    """Tool definition matching"""

    def test_tool_matches_by_name(self):
        """Tool definition matches exact name"""
        tool = ToolDefinition(name="terminal", category=ToolCategory.SYSTEM, patterns=[])
        assert tool.matches("terminal")
        assert not tool.matches("read_file")

    def test_tool_matches_by_pattern(self):
        """Tool definition matches regex patterns"""
        tool = ToolDefinition(name="shell", category=ToolCategory.SYSTEM, patterns=[r"bash", r"shell"])
        assert tool.matches("bash_executor")
        assert tool.matches("shell_command")
        assert not tool.matches("read_file")


class TestPermissionCheck:
    """Permission check logic"""

    def test_denylist_blocks_tool(self):
        """Tool on denylist is always denied"""
        layer = ToolPermissionLayer(denylist=["terminal", "patch"])
        result = layer.check_permission("terminal", {"command": "ls"})

        assert result.decision == PermissionDecision.DENIED
        assert "denylist" in result.reason.lower()

    def test_allowlist_allows_tool(self):
        """Tool on allowlist is allowed"""
        layer = ToolPermissionLayer(allowlist=["read_file", "write_file"])
        result = layer.check_permission("read_file", {})

        assert result.decision == PermissionDecision.ALLOWED

    def test_allowlist_blocks_unlisted(self):
        """Tool not on allowlist is denied"""
        layer = ToolPermissionLayer(allowlist=["read_file"])
        result = layer.check_permission("write_file", {})

        assert result.decision == PermissionDecision.DENIED

    def test_prohibited_actions_exact_match(self):
        """prohibited_actions blocks matching tools"""
        layer = ToolPermissionLayer()
        result = layer.check_permission(
            "delete_file",
            {"path": "/important"},
            prohibited_actions=["delete_file", "rm -rf"],
        )

        assert result.decision == PermissionDecision.DENIED
        assert "prohibited" in result.reason.lower()

    def test_prohibited_actions_arg_match(self):
        """prohibited_actions checks arguments too"""
        layer = ToolPermissionLayer()
        result = layer.check_permission(
            "terminal",
            {"command": "rm -rf /important"},
            prohibited_actions=["rm -rf"],
        )

        assert result.decision == PermissionDecision.DENIED

    def test_risk_based_approval_required(self):
        """High-risk tools require approval"""
        layer = ToolPermissionLayer(require_approval_above="low")
        result = layer.check_permission("terminal", {"command": "ls"})

        assert result.decision == PermissionDecision.APPROVAL_REQUIRED
        assert result.requires_approval

    def test_low_risk_auto_allowed(self):
        """Low-risk tools are auto-allowed"""
        layer = ToolPermissionLayer(require_approval_above="medium")
        result = layer.check_permission("read_file", {"path": "/tmp/test.py"})

        assert result.decision == PermissionDecision.ALLOWED


class TestApprovalWorkflow:
    """Approval workflow"""

    def test_record_approval(self):
        """record_approval marks call as allowed"""
        layer = ToolPermissionLayer(require_approval_above="low")
        result = layer.check_permission("terminal", {"command": "ls"})

        assert result.decision == PermissionDecision.APPROVAL_REQUIRED
        assert len(layer.get_pending_approvals()) == 1

        call_id = layer._audit_log[-1].call_id
        approved = layer.record_approval(call_id, approved_by="user@test.com")

        assert approved
        assert layer.is_approved(call_id)

    def test_record_denial(self):
        """record_denial marks call as denied"""
        layer = ToolPermissionLayer(require_approval_above="low")
        layer.check_permission("terminal", {"command": "ls"})

        call_id = layer._audit_log[-1].call_id
        denied = layer.record_denial(call_id, denied_by="admin", reason="Too risky")

        assert denied
        assert not layer.is_approved(call_id)

    def test_approval_not_found(self):
        """Approval for unknown call_id returns False"""
        layer = ToolPermissionLayer()
        result = layer.record_approval("nonexistent_call_id")

        assert result is False


class TestAuditLog:
    """Audit log functionality"""

    def test_audit_log_records_all_calls(self):
        """All tool calls are logged"""
        layer = ToolPermissionLayer()
        layer.check_permission("read_file", {})
        layer.check_permission("write_file", {})
        layer.check_permission("terminal", {}, prohibited_actions=["rm"])

        log = layer.get_audit_log()
        assert len(log) == 3

    def test_audit_log_filter_by_tool(self):
        """Audit log can filter by tool name"""
        layer = ToolPermissionLayer()
        layer.check_permission("read_file", {})
        layer.check_permission("write_file", {})
        layer.check_permission("read_file", {})

        log = layer.get_audit_log(tool_name="read_file")
        assert len(log) == 2

    def test_audit_log_filter_by_status(self):
        """Audit log can filter by status"""
        layer = ToolPermissionLayer(denylist=["forbidden_tool"])
        layer.check_permission("read_file", {})  # allowed
        layer.check_permission("forbidden_tool", {})  # denied

        denied_log = layer.get_audit_log(status="denied")
        allowed_log = layer.get_audit_log(status="allowed")

        assert len(denied_log) == 1  # forbidden_tool was denied
        assert len(allowed_log) == 1  # read_file was allowed

    def test_policy_summary(self):
        """get_policy_summary returns correct stats"""
        layer = ToolPermissionLayer(denylist=["dangerous_tool"], require_approval_above="medium")
        layer.check_permission("read_file", {})
        layer.check_permission("terminal", {})  # pending approval

        summary = layer.get_policy_summary()

        assert summary["denied_calls"] == 0
        assert summary["pending_approvals"] == 1
        assert summary["total_calls"] == 2


class TestExecuteWithPermission:
    """execute_with_permission integration"""

    @pytest.mark.asyncio
    async def test_execute_allowed_tool(self):
        """execute_with_permission runs allowed tool"""
        layer = ToolPermissionLayer()
        executed = []

        async def my_executor(args):
            executed.append(args)
            return "result"

        check_result, exec_result = await layer.execute_with_permission(
            "read_file", {"path": "/tmp/test.py"}, my_executor
        )

        assert check_result.decision == PermissionDecision.ALLOWED
        assert exec_result == "result"
        assert executed == [{"path": "/tmp/test.py"}]

    @pytest.mark.asyncio
    async def test_execute_denied_tool(self):
        """execute_with_permission blocks denied tool"""
        layer = ToolPermissionLayer(denylist=["terminal"])
        executed = []

        async def my_executor(args):
            executed.append(args)

        check_result, exec_result = await layer.execute_with_permission(
            "terminal", {"command": "ls"}, my_executor
        )

        assert check_result.decision == PermissionDecision.DENIED
        assert exec_result is None
        assert executed == []


class TestToolCategories:
    """Tool category classification"""

    def test_tool_category_enum_values(self):
        """All expected tool categories exist"""
        categories = [c.value for c in ToolCategory]
        assert "read" in categories
        assert "write" in categories
        assert "destructive" in categories
        assert "deploy" in categories
        assert "network" in categories


class TestPolicyCheckResult:
    """PolicyCheckResult dataclass"""

    def test_policy_check_result_fields(self):
        """PolicyCheckResult has all expected fields"""
        result = PolicyCheckResult(
            decision=PermissionDecision.ALLOWED,
            tool_name="test_tool",
            reason="Test passed",
            requires_approval=False,
            approval_level=None,
            policy_matched="test_policy",
        )

        assert result.decision == PermissionDecision.ALLOWED
        assert result.tool_name == "test_tool"
        assert result.requires_approval is False
        assert result.policy_matched == "test_policy"


class TestCustomToolRegistration:
    """Custom tool registration"""

    def test_register_custom_tool(self):
        """Custom tools can be registered"""
        layer = ToolPermissionLayer()
        custom = ToolDefinition(
            name="my_deploy_tool",
            category=ToolCategory.DEPLOY,
            risk_level="critical",
            patterns=[r"deploy.*prod"],
        )
        layer.register_tool(custom)

        found = layer.get_tool_definition("my_deploy_tool")
        assert found is not None
        assert found.risk_level == "critical"
        assert found.category == ToolCategory.DEPLOY