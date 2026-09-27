"""
Tests for Docker Sandbox Runtime

Tests cover:
- Sandbox lifecycle (create, start, stop, destroy)
- Command execution
- File operations
- Path security
- Ownership verification
"""

import os
import tempfile
from pathlib import Path

import pytest

from rann_agent.execution.docker_sandbox import (
    DockerSandboxConfig,
    DockerSandboxProvider,
    SandboxStatus,
)


@pytest.fixture
def config():
    """Create test configuration."""
    return DockerSandboxConfig(
        image="python:3.11-slim",
        memory_limit="256m",
        cpu_limit="0.5",
        timeout=30,
        max_output_bytes=10240,  # 10KB for tests
        workspace_root=Path(tempfile.mkdtemp()),
    )


@pytest.fixture
def provider(config):
    """Create sandbox provider with test config."""
    provider = DockerSandboxProvider(config)
    yield provider
    # Cleanup
    for project_id in list(provider._sandboxes.keys()):
        try:
            import asyncio

            asyncio.get_event_loop().run_until_complete(provider.destroy(project_id))
        except Exception:
            pass


class TestSandboxLifecycle:
    """Test sandbox creation and lifecycle."""

    @pytest.mark.skipif(
        os.environ.get("SANDBOX_SKIP_DOCKER_TESTS") == "true",
        reason="Docker tests disabled",
    )
    async def test_create_sandbox(self, provider):
        """Should create sandbox for a project."""
        sandbox = await provider.create("test-project-1")
        assert sandbox.project_id == "test-project-1"
        assert sandbox.status == SandboxStatus.CREATED

    @pytest.mark.skipif(
        os.environ.get("SANDBOX_SKIP_DOCKER_TESTS") == "true",
        reason="Docker tests disabled",
    )
    async def test_start_stop_sandbox(self, provider):
        """Should start and stop sandbox."""
        await provider.create("test-project-2")
        sandbox = await provider.start("test-project-2")
        assert sandbox.status == SandboxStatus.RUNNING

        sandbox = await provider.stop("test-project-2")
        assert sandbox.status == SandboxStatus.STOPPED

    @pytest.mark.skipif(
        os.environ.get("SANDBOX_SKIP_DOCKER_TESTS") == "true",
        reason="Docker tests disabled",
    )
    async def test_destroy_sandbox(self, provider):
        """Should destroy sandbox completely."""
        await provider.create("test-project-3")
        await provider.start("test-project-3")
        await provider.destroy("test-project-3")

        assert "test-project-3" not in provider._sandboxes


class TestSandboxExecution:
    """Test command execution in sandbox."""

    @pytest.mark.skipif(
        os.environ.get("SANDBOX_SKIP_DOCKER_TESTS") == "true",
        reason="Docker tests disabled",
    )
    async def test_execute_command(self, provider):
        """Should execute command in sandbox."""
        await provider.create("test-project-4")
        await provider.start("test-project-4")

        result = await provider.execute("test-project-4", "echo hello")
        assert result.success
        assert "hello" in result.stdout

    @pytest.mark.skipif(
        os.environ.get("SANDBOX_SKIP_DOCKER_TESTS") == "true",
        reason="Docker tests disabled",
    )
    async def test_execute_not_running(self, provider):
        """Should fail if sandbox not running."""
        await provider.create("test-project-5")

        with pytest.raises(ValueError, match="not running"):
            await provider.execute("test-project-5", "echo test")


class TestSandboxFileOperations:
    """Test file operations in sandbox."""

    @pytest.mark.skipif(
        os.environ.get("SANDBOX_SKIP_DOCKER_TESTS") == "true",
        reason="Docker tests disabled",
    )
    async def test_write_read_file(self, provider):
        """Should write and read file."""
        await provider.create("test-project-6")
        await provider.start("test-project-6")

        content = "Hello from sandbox!"
        await provider.write_file("test-project-6", "test.txt", content)

        read_content = await provider.read_file("test-project-6", "test.txt")
        assert read_content == content

    @pytest.mark.skipif(
        os.environ.get("SANDBOX_SKIP_DOCKER_TESTS") == "true",
        reason="Docker tests disabled",
    )
    async def test_list_files(self, provider):
        """Should list files in workspace."""
        await provider.create("test-project-7")
        await provider.start("test-project-7")

        await provider.write_file("test-project-7", "file1.txt", "content1")
        await provider.write_file("test-project-7", "file2.txt", "content2")

        files = await provider.list_files("test-project-7")
        assert "file1.txt" in files
        assert "file2.txt" in files


class TestSandboxSecurity:
    """Test sandbox security boundaries."""

    def test_workspace_path_generation(self, provider):
        """Workspace path should be deterministic and safe."""
        path = provider._get_workspace_path("test-project")
        assert str(path).endswith("test-project")
        assert ".." not in str(path)

    def test_path_traversal_blocked(self, provider):
        """Path traversal attempts should be blocked."""
        from rann_agent.core.security import WorkspaceSecurity

        workspace = Path(tempfile.mkdtemp())

        with pytest.raises(ValueError, match="traversal"):
            WorkspaceSecurity.safe_join(workspace, "../../../etc/passwd")

    def test_absolute_path_blocked(self, provider):
        """Absolute paths should be blocked."""
        from rann_agent.core.security import WorkspaceSecurity

        workspace = Path(tempfile.mkdtemp())

        with pytest.raises(ValueError, match="Absolute"):
            WorkspaceSecurity.safe_join(workspace, "/etc/passwd")
