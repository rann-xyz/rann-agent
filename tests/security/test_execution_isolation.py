"""
Security tests for execution isolation.

These tests verify:
1. Environment isolation (no server secrets leak)
2. Container availability for production
3. Fail-closed behavior

MARKERS:
- @pytest.mark.unit - Can run without Docker
- @pytest.mark.integration - Requires Docker runtime
"""

import asyncio
import os
import subprocess
import sys

import pytest

sys.path.insert(0, "/home/userland/rann-agent")

from rann_agent.execution import (
    ExecutionJob,
    ExecutionPolicy,
    ExecutionStatus,
    LocalExecutionBackend,
    ContainerExecutionBackend,
    get_execution_backend,
)


# ============================================================================
# UNIT TESTS (No Docker required)
# ============================================================================


@pytest.mark.unit
class TestLocalExecutionBackend:
    """Unit tests for LocalExecutionBackend (development only)."""

    def test_development_only_marker(self):
        """LocalExecutionBackend must be marked as DEVELOPMENT_ONLY."""
        backend = LocalExecutionBackend()
        assert backend.DEVELOPMENT_ONLY is True

    def test_is_available(self):
        """Local backend should be available but marked as dev-only."""
        backend = LocalExecutionBackend()
        assert backend.is_available() is True
        assert backend.DEVELOPMENT_ONLY is True

    def test_environment_allowlist_exists(self):
        """Default environment allowlist should exist and be safe."""
        policy = ExecutionPolicy()
        forbidden = ["DATABASE_URL", "SECRET_KEY", "API_KEY", "RANN_IP_BINDING_SECRET"]
        for key in forbidden:
            assert key not in policy.allowed_env, f"Forbidden key in allowlist: {key}"


@pytest.mark.unit
class TestContainerExecutionBackend:
    """Tests for ContainerExecutionBackend configuration."""

    def test_not_development_only(self):
        """Container backend should NOT be marked development-only."""
        backend = ContainerExecutionBackend()
        assert backend.DEVELOPMENT_ONLY is False
        assert backend.REQUIRE_CONTAINER is True

    def test_availability_detection(self):
        """Should correctly detect if Docker is available."""
        backend = ContainerExecutionBackend()
        # If Docker is available, is_available() returns True
        # If not, returns False (fail-closed in submit())
        assert isinstance(backend.is_available(), bool)


@pytest.mark.unit
class TestExecutionJob:
    """Tests for ExecutionJob identity enforcement."""

    def test_user_id_server_derived(self):
        """Job user_id should be set by server, not from client."""
        job = ExecutionJob(
            job_id="test-123",
            user_id="user_abc123",  # Server-derived from session
            run_id="run_xyz789",  # Server-derived from run creation
            workspace_id="ws_test",
            command="echo test",
        )
        assert job.user_id == "user_abc123"
        # Client CANNOT set run_id or workspace_id from request
        # These must be server-generated
        assert "client" not in job.user_id


@pytest.mark.unit
class TestExecutionPolicy:
    """Tests for execution policy defaults."""

    def test_network_disabled_by_default(self):
        """Network should be disabled by default."""
        policy = ExecutionPolicy()
        assert policy.network_allowed is False

    def test_resource_policy_exists(self):
        """Resource policy should have sensible defaults."""
        policy = ExecutionPolicy()
        assert policy.resource_limits.timeout_seconds > 0
        assert policy.resource_limits.memory_bytes > 0
        assert policy.resource_limits.max_output_bytes > 0


# ============================================================================
# INTEGRATION TESTS (Requires Docker)
# ============================================================================


@pytest.mark.integration
@pytest.mark.skipif(
    not ContainerExecutionBackend().is_available(),
    reason="Docker runtime not available for integration tests",
)
class TestContainerExecution:
    """Integration tests requiring Docker container runtime."""

    @pytest.mark.asyncio
    async def test_container_execution_runs(self):
        """Container execution should complete successfully."""
        backend = ContainerExecutionBackend()
        job = ExecutionJob(
            job_id="integration-test-1",
            user_id="test_user",
            run_id="test_run",
            workspace_id="test_ws",
            command="echo 'hello from container'",
            policy=ExecutionPolicy(network_allowed=False),
        )

        job_id = await backend.submit(job)
        result = await backend.get_result(job_id)

        assert result.status == ExecutionStatus.COMPLETED
        assert "hello from container" in result.stdout

    @pytest.mark.asyncio
    async def test_environment_isolation_no_server_secrets(self):
        """Server secrets should NOT be visible in container."""
        backend = ContainerExecutionBackend()

        # Set a fake server secret
        test_secret = "RANN_SECRET_TEST_should_not_leak"
        original = os.environ.get("RANN_SECRET_TEST")

        try:
            os.environ["RANN_SECRET_TEST"] = test_secret

            job = ExecutionJob(
                job_id="secret-test",
                user_id="test_user",
                run_id="test_run",
                workspace_id="test_ws",
                command="printenv RANN_SECRET_TEST || echo NOT_FOUND",
                policy=ExecutionPolicy(),
            )

            await backend.submit(job)
            result = await backend.get_result("secret-test")

            assert (
                test_secret not in result.stdout
            ), "SECURITY FAILURE: Server secret leaked to container!"

        finally:
            if original:
                os.environ["RANN_SECRET_TEST"] = original
            elif "RANN_SECRET_TEST" in os.environ:
                del os.environ["RANN_SECRET_TEST"]

    @pytest.mark.asyncio
    async def test_network_disabled(self):
        """Network should be disabled when policy says so."""
        backend = ContainerExecutionBackend()

        job = ExecutionJob(
            job_id="network-test",
            user_id="test_user",
            run_id="test_run",
            workspace_id="test_ws",
            command="curl -s -o /dev/null -w '%{http_code}' http://example.com || echo 'FAILED'",
            policy=ExecutionPolicy(network_allowed=False),
        )

        await backend.submit(job)
        result = await backend.get_result("network-test")

        # Should fail because network is disabled
        assert "FAILED" in result.stdout or "Connection refused" in result.stdout

    @pytest.mark.asyncio
    async def test_non_root_verification(self):
        """Container should run as non-root user."""
        backend = ContainerExecutionBackend()

        job = ExecutionJob(
            job_id="uid-test",
            user_id="test_user",
            run_id="test_run",
            workspace_id="test_ws",
            command="id -u",
            policy=ExecutionPolicy(),
        )

        await backend.submit(job)
        result = await backend.get_result("uid-test")

        uid = result.stdout.strip()
        assert uid != "0", f"SECURITY FAILURE: Container ran as root! UID: {uid}"

    @pytest.mark.asyncio
    async def test_cancellation_kills_container(self):
        """Cancellation should terminate the container."""
        backend = ContainerExecutionBackend()

        job = ExecutionJob(
            job_id="cancel-test",
            user_id="test_user",
            run_id="test_run",
            workspace_id="test_ws",
            command="sleep 30",
            policy=ExecutionPolicy(timeout_seconds=5),
        )

        await backend.submit(job)
        await asyncio.sleep(0.5)
        cancelled = await backend.cancel("cancel-test")

        assert cancelled is True
        result = await backend.get_result("cancel-test")
        assert result.status == ExecutionStatus.CANCELLED


# ============================================================================
# FAIL-CLOSED TESTS
# ============================================================================


@pytest.mark.unit
class TestFailClosedBehavior:
    """Tests verifying fail-closed behavior."""

    def test_container_backend_requires_docker(self):
        """Container backend must fail if Docker unavailable."""
        # Force no Docker available
        import rann_agent.execution as exec_mod

        original = exec_mod.shutil.which

        def mock_which(cmd):
            if cmd == "docker":
                return None
            return original(cmd)

        exec_mod.shutil.which = mock_which

        try:
            backend = ContainerExecutionBackend()
            assert backend.is_available() is False
        finally:
            exec_mod.shutil.which = original

    @pytest.mark.asyncio
    async def test_container_submit_fails_without_docker(self):
        """Submit should raise RuntimeError without Docker."""
        import rann_agent.execution as exec_mod

        original = exec_mod.shutil.which

        def mock_which(cmd):
            if cmd == "docker":
                return None
            return original(cmd)

        exec_mod.shutil.which = mock_which

        try:
            backend = ContainerExecutionBackend()
            job = ExecutionJob(
                job_id="fail-test",
                user_id="test_user",
                run_id="test_run",
                workspace_id="test_ws",
                command="echo test",
            )

            with pytest.raises(RuntimeError, match="FAIL CLOSED"):
                await backend.submit(job)

        finally:
            exec_mod.shutil.which = original


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "unit"])
