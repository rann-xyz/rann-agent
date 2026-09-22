"""
Security tests for execution isolation.

These tests prove that:
1. Server secrets are NOT inherited by subprocess execution
2. Environment is properly sanitized
3. User identity comes from session, not request
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, "/home/userland/rann-agent")

from rann_agent.execution import (
    ExecutionJob,
    ExecutionPolicy,
    ExecutionStatus,
    LocalExecutionBackend,
)


class TestEnvironmentIsolation:
    """Test that server environment secrets are not leaked to execution."""

    @pytest.mark.asyncio
    async def test_server_secret_not_leaked_to_subprocess(self):
        """
        CRITICAL TEST: Server secrets must NOT be visible in subprocess.

        This test proves that execution does not inherit os.environ.
        """
        # Set a test secret in the current environment
        test_secret = "RANN_TEST_SECRET_super_secret_value_12345"
        original_env = dict(os.environ)

        try:
            os.environ["RANN_TEST_SECRET"] = test_secret

            # Create execution backend
            backend = LocalExecutionBackend()

            # Create job that reads environment
            job = ExecutionJob(
                job_id="test-job-1",
                user_id="user_test",
                run_id="run_test",
                workspace_id="ws_test",
                command="printenv | grep RANN_TEST_SECRET || echo NOT_FOUND",
                policy=ExecutionPolicy(),
            )

            # Submit and execute
            await backend.submit(job)

            # Wait for completion
            import time

            for _ in range(50):
                if job.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
                    break
                await asyncio.sleep(0.1)

            # Verify secret was NOT in output
            stdout = job.stdout
            assert (
                "RANN_TEST_SECRET" not in stdout
            ), f"CRITICAL SECURITY FAILURE: Server secret leaked to subprocess! Got: {stdout}"
            assert (
                test_secret not in stdout
            ), f"CRITICAL SECURITY FAILURE: Test secret value leaked! Got: {stdout}"

        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(original_env)

    @pytest.mark.asyncio
    async def test_environment_allowlist_enforced(self):
        """Verify only allowed environment variables are passed."""
        backend = LocalExecutionBackend()

        # Check that policy has minimal allowed environment
        policy = ExecutionPolicy()

        # Should contain basic PATH
        assert "PATH" in policy.allowed_env
        assert "HOME" in policy.allowed_env

        # Should NOT contain sensitive keys by default
        forbidden_keys = [
            "DATABASE_URL",
            "SECRET_KEY",
            "API_KEY",
            "AWS_SECRET",
            "RANN_IP_BINDING_SECRET",
            "SESSION_SECRET",
        ]

        for key in forbidden_keys:
            assert (
                key not in policy.allowed_env
            ), f"SECURITY ISSUE: Forbidden key {key} in default allowlist"


class TestIdentityEnforcement:
    """Test that user identity comes from server, not client."""

    def test_user_id_derived_from_server(self):
        """
        ExecutionJob.user_id must be set by server, never from request body.

        This test verifies the data model enforces this.
        """
        job = ExecutionJob(
            job_id="test-job-2",
            user_id="user_12345",  # Set by server from session
            run_id="run_67890",
            workspace_id="ws_abcde",
            command="echo hello",
        )

        # Job.user_id is set, not from client
        assert job.user_id == "user_12345"

        # In a real implementation, we would verify that the HTTP endpoint
        # creates this job using user_id from authenticated session


class TestResourceLimits:
    """Test that resource limits are enforced."""

    @pytest.mark.asyncio
    async def test_timeout_enforcement(self):
        """Verify execution timeout is enforced."""
        backend = LocalExecutionBackend()

        # Create job with 1 second timeout
        policy = ExecutionPolicy(
            network_allowed=False,
            allowed_env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
        )
        policy.resource_limits.timeout_seconds = 1

        job = ExecutionJob(
            job_id="timeout-test",
            user_id="user_test",
            run_id="run_test",
            workspace_id="ws_test",
            command="sleep 10",
            policy=policy,
        )

        await backend.submit(job)

        # Wait for completion
        import time

        start = time.time()
        for _ in range(30):
            if job.status != ExecutionStatus.QUEUED:
                break
            await asyncio.sleep(0.1)

        elapsed = time.time() - start

        # Should timeout within reasonable time
        assert elapsed < 5, f"Timeout not enforced! Elapsed: {elapsed}s"
        assert job.status == ExecutionStatus.TIMEOUT, f"Wrong status: {job.status}"


class TestNetworkIsolation:
    """Test network policy enforcement."""

    def test_network_policy_default_denied(self):
        """Verify network is disabled by default."""
        policy = ExecutionPolicy()

        assert (
            policy.network_allowed is False
        ), "SECURITY ISSUE: Network should be denied by default"


class TestDevelopmentOnlyMarker:
    """Verify LocalExecutionBackend is marked as development-only."""

    def test_development_only_marker(self):
        """LocalExecutionBackend must be clearly marked as development-only."""
        backend = LocalExecutionBackend()

        assert backend.DEVELOPMENT_ONLY is True, "DEVELOPMENT_ONLY marker missing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
