"""
Tests for FakeContainerBackend.

These tests verify:
1. Backend availability
2. Job submission and execution  
3. Environment isolation (no server secrets leak)
4. Timeout enforcement
5. Cancellation behavior
6. Output limits
7. Workspace cleanup

NOTE: These tests require Python 3.10+ and are run with asyncio.
The test file patches datetime.UTC for Python 3.10 compatibility.

MARKERS:
- @pytest.mark.unit - Can run without Docker
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Python 3.10 compatibility: datetime.UTC was added in Python 3.11
# Patch it before importing rann_agent modules
if not hasattr(datetime, 'UTC'):
    datetime.UTC = timezone.utc

# Add rann-agent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rann_agent.execution import (
    ExecutionJob,
    ExecutionPolicy,
    ExecutionStatus,
    FakeContainerBackend,
    get_execution_backend,
)


@pytest.fixture
def fake_backend():
    """Create a fresh FakeContainerBackend instance."""
    return FakeContainerBackend()


@pytest.fixture
def sample_job():
    """Create a sample execution job for testing."""
    return ExecutionJob(
        job_id="test-job-123",
        user_id="test_user",
        run_id="test_run_456",
        workspace_id="test_ws_789",
        policy=ExecutionPolicy(),
    )


@pytest.mark.unit
class TestFakeContainerBackendBasics:
    """Basic functionality tests for FakeContainerBackend."""

    def test_is_available(self, fake_backend):
        """FakeContainerBackend should always be available."""
        assert fake_backend.is_available() is True

    def test_development_only_marker(self, fake_backend):
        """Backend should be marked as development only."""
        assert fake_backend.DEVELOPMENT_ONLY is True
        assert fake_backend.REQUIRE_CONTAINER is False

    def test_backend_type(self):
        """get_execution_backend should return FakeContainerBackend by default."""
        original = os.environ.get("RANN_EXECUTION_BACKEND")
        try:
            if "RANN_EXECUTION_BACKEND" in os.environ:
                del os.environ["RANN_EXECUTION_BACKEND"]
            backend = get_execution_backend()
            assert isinstance(backend, FakeContainerBackend)
        finally:
            if original:
                os.environ["RANN_EXECUTION_BACKEND"] = original


@pytest.mark.unit
class TestFakeContainerBackendJobExecution:
    """Job execution tests for FakeContainerBackend."""

    @pytest.mark.asyncio
    async def test_submit_and_get_status(self, fake_backend):
        """Job should transition to RUNNING after submission."""
        job = ExecutionJob(
            job_id="test-status-job",
            user_id="test_user",
            run_id="test_run",
            workspace_id="test_ws",
            policy=ExecutionPolicy(),
            command="echo test",
        )
        job_id = await fake_backend.submit(job)
        assert job_id == job.job_id

        status = await fake_backend.get_status(job_id)
        assert status == ExecutionStatus.RUNNING

    @pytest.mark.asyncio
    async def test_job_completion(self, fake_backend):
        """Job should complete successfully with simple command."""
        job = ExecutionJob(
            job_id="completion-test",
            user_id="user1",
            run_id="run1",
            workspace_id="ws1",
            policy=ExecutionPolicy(),
            command="echo test output",
        )

        job_id = await fake_backend.submit(job)
        result = await fake_backend.get_result(job_id)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.success is True
        assert "test output" in result.stdout

    @pytest.mark.asyncio
    async def test_job_failure(self, fake_backend):
        """Job should fail gracefully on error."""
        job = ExecutionJob(
            job_id="failure-test",
            user_id="user1",
            run_id="run1",
            workspace_id="ws1",
            policy=ExecutionPolicy(),
            command="exit 1",
        )

        job_id = await fake_backend.submit(job)
        result = await fake_backend.get_result(job_id)

        assert result.status == ExecutionStatus.FAILED
        assert result.exit_code == 1

    @pytest.mark.asyncio
    async def test_nonexistent_job(self, fake_backend):
        """Nonexistent job should return failed status."""
        status = await fake_backend.get_status("nonexistent-job-xyz")
        assert status == ExecutionStatus.FAILED

        result = await fake_backend.get_result("nonexistent-job-xyz")
        assert result.success is False
        assert "not found" in result.stderr.lower()


@pytest.mark.unit
class TestFakeContainerBackendTimeout:
    """Timeout enforcement tests."""

    @pytest.mark.asyncio
    async def test_timeout_enforcement(self, fake_backend):
        """Long-running process should be killed on timeout."""
        job = ExecutionJob(
            job_id="timeout-test",
            user_id="user1",
            run_id="run1",
            workspace_id="ws1",
            policy=ExecutionPolicy(timeout_seconds=2),
            command="sleep 30",
        )

        job_id = await fake_backend.submit(job)
        result = await fake_backend.get_result(job_id)

        assert result.status == ExecutionStatus.TIMEOUT
        assert result.killed is True
        assert result.exit_code == -1


@pytest.mark.unit
class TestFakeContainerBackendCancellation:
    """Cancellation tests."""

    @pytest.mark.asyncio
    async def test_cancel_running_job(self, fake_backend):
        """Running job should be cancellable."""
        job = ExecutionJob(
            job_id="cancel-test",
            user_id="user1",
            run_id="run1",
            workspace_id="ws1",
            policy=ExecutionPolicy(timeout_seconds=60),
            command="sleep 30",
        )

        job_id = await fake_backend.submit(job)
        await asyncio.sleep(0.1)  # Let job start

        cancelled = await fake_backend.cancel(job_id)
        assert cancelled is True

        result = await fake_backend.get_result(job_id)
        assert result.status == ExecutionStatus.CANCELLED
        assert result.killed is True


@pytest.mark.unit
class TestFakeContainerBackendOutputLimits:
    """Output size limit tests."""

    @pytest.mark.asyncio
    async def test_output_truncation(self, fake_backend):
        """Output should be truncated to max_output_bytes."""
        job = ExecutionJob(
            job_id="output-test",
            user_id="user1",
            run_id="run1",
            workspace_id="ws1",
            policy=ExecutionPolicy(max_output_bytes=100),
            command="python3 -c \"print('x' * 1000)\"",
        )

        job_id = await fake_backend.submit(job)
        result = await fake_backend.get_result(job_id)

        # Output should be truncated
        assert len(result.stdout) <= 100


@pytest.mark.unit
class TestFakeContainerBackendEnvironmentIsolation:
    """Environment isolation tests."""

    @pytest.mark.asyncio
    async def test_no_server_secrets_in_env(self, fake_backend):
        """Server secrets should not be visible in job environment."""
        # Set a fake server secret
        test_secret = "RANN_SECRET_TEST_fake_value_12345"
        original = os.environ.get("RANN_SECRET_TEST")

        try:
            os.environ["RANN_SECRET_TEST"] = test_secret

            job = ExecutionJob(
                job_id="secret-leak-test",
                user_id="user1",
                run_id="run1",
                workspace_id="ws1",
                policy=ExecutionPolicy(),
                command="printenv RANN_SECRET_TEST || echo 'NOT_FOUND'",
            )

            job_id = await fake_backend.submit(job)
            result = await fake_backend.get_result(job_id)

            # Secret should NOT be in output
            assert test_secret not in result.stdout, (
                "SECURITY FAILURE: Server secret leaked to job environment!"
            )
            assert "NOT_FOUND" in result.stdout

        finally:
            if original is not None:
                os.environ["RANN_SECRET_TEST"] = original
            else:
                os.environ.pop("RANN_SECRET_TEST", None)

    @pytest.mark.asyncio
    async def test_allowed_env_only(self, fake_backend):
        """Only allowed environment variables should be present."""
        job = ExecutionJob(
            job_id="env-test",
            user_id="user1",
            run_id="run1",
            workspace_id="ws1",
            policy=ExecutionPolicy(),
            command="printenv | sort",
        )

        job_id = await fake_backend.submit(job)
        result = await fake_backend.get_result(job_id)

        # Should have PATH and HOME from allowed_env
        assert "PATH=" in result.stdout


@pytest.mark.unit
class TestFakeContainerBackendWorkspace:
    """Workspace isolation tests."""

    @pytest.mark.asyncio
    async def test_workspace_isolation(self, fake_backend):
        """Jobs should execute in isolated workspaces."""
        job = ExecutionJob(
            job_id="ws-isolation-test",
            user_id="user1",
            run_id="run1",
            workspace_id="ws-isolation",
            policy=ExecutionPolicy(),
            command="pwd",
        )

        job_id = await fake_backend.submit(job)
        result = await fake_backend.get_result(job_id)

        # Should be in workspace directory
        assert "rann_fake_ws_" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])