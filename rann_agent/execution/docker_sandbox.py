"""
Docker-based Sandbox Runtime for RANN Agent

Provides production-grade container isolation for:
- File operations
- Command execution
- Tool integrations
- Agent workflows

SECURITY: This module creates isolated Docker containers for each project.
The container is the security boundary - never trust host execution.
"""

import asyncio
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import structlog

import docker
import docker.errors
from rann_agent.execution import (
    ExecutionBackend,
    ExecutionJob,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
    ResourcePolicy,
)

logger = structlog.get_logger(__name__)


class SandboxStatus(Enum):
    """Sandbox lifecycle states."""

    CREATE_PENDING = "create_pending"
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    DESTROY_PENDING = "destroy_pending"
    DESTROYED = "destroyed"


@dataclass
class Sandbox:
    """Represents a Docker sandbox instance."""

    project_id: str
    sandbox_id: str
    container_id: str | None = None
    status: SandboxStatus = SandboxStatus.CREATE_PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    last_activity: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "sandbox_id": self.sandbox_id,
            "container_id": self.container_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


@dataclass
class DockerSandboxConfig:
    """Configuration for Docker sandbox runtime."""

    image: str = os.environ.get("SANDBOX_IMAGE", "python:3.11-slim")
    memory_limit: str = os.environ.get("SANDBOX_MEMORY_LIMIT", "1g")
    cpu_limit: str = os.environ.get("SANDBOX_CPU_LIMIT", "1.0")
    pids_limit: int = int(os.environ.get("SANDBOX_PIDS_LIMIT", "256"))
    timeout: int = int(os.environ.get("SANDBOX_TIMEOUT", "120"))
    max_output_bytes: int = int(os.environ.get("SANDBOX_MAX_OUTPUT_BYTES", "1048576"))
    network_mode: str = os.environ.get("SANDBOX_NETWORK_MODE", "none")
    workspace_root: Path = Path(
        os.environ.get("SANDBOX_WORKSPACE_ROOT", "/var/lib/rann/workspaces")
    )

    def to_docker_config(self, workspace_path: Path) -> dict:
        """Convert to Docker run configuration."""
        return {
            "image": self.image,
            "mem_limit": self.memory_limit,
            "nano_cpus": int(float(self.cpu_limit) * 1e9),
            "pids_limit": self.pids_limit,
            "network_mode": self.network_mode if self.network_mode != "none" else "none",
            "detach": True,
            "stdin_open": True,
            "tty": True,
            "working_dir": "/workspace",
            "user": "1000:1000",
            "read_only": True,
            "security_opt": ["no-new-privileges"],
            "cap_drop": ["ALL"],
            "environment": {
                "HOME": "/workspace",
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "TERM": "dumb",
            },
            "volumes": {
                str(workspace_path): {"bind": "/workspace", "mode": "rw"},
            },
        }


class DockerSandboxProvider:
    """
    Production-grade Docker sandbox provider.

    Creates isolated Docker containers for each project/workspace.
    All execution happens inside the container - the container IS the sandbox.
    """

    def __init__(self, config: DockerSandboxConfig | None = None):
        self.config = config or DockerSandboxConfig()
        self._client: docker.DockerClient | None = None
        self._sandboxes: dict[str, Sandbox] = {}
        self._workspace_root = self._ensure_workspace_root()

    def _ensure_workspace_root(self) -> Path:
        """Ensure workspace root directory exists."""
        root = self.config.workspace_root
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _get_client(self) -> docker.DockerClient:
        """Get or create Docker client."""
        if self._client is None:
            self._client = docker.from_env()
            # Verify Docker is available
            self._client.ping()
        return self._client

    def _get_workspace_path(self, project_id: str) -> Path:
        """Get the workspace path for a project."""
        workspace = self._workspace_root / project_id
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    async def create(self, project_id: str) -> Sandbox:
        """Create a new sandbox for a project."""
        logger.info("creating_sandbox", project_id=project_id)

        if project_id in self._sandboxes:
            return self._sandboxes[project_id]

        sandbox = Sandbox(
            project_id=project_id,
            sandbox_id=f"sb_{uuid.uuid4().hex[:12]}",
        )
        self._sandboxes[project_id] = sandbox

        # Create workspace directory
        workspace_path = self._get_workspace_path(project_id)

        # Create container
        try:
            config = self.config.to_docker_config(workspace_path)
            container_name = f"rann_{project_id[:8]}_{uuid.uuid4().hex[:8]}"

            client = self._get_client()
            container = client.containers.run(**config, name=container_name)

            sandbox.container_id = container.id
            sandbox.status = SandboxStatus.CREATED
            sandbox.updated_at = datetime.now(timezone.utc)

            logger.info(
                "sandbox_container_created", project_id=project_id, container_id=container.id[:12]
            )

        except docker.errors.APIError as e:
            logger.error("sandbox_create_failed", project_id=project_id, error=str(e))
            sandbox.status = SandboxStatus.CRASHED
            raise RuntimeError(f"Failed to create sandbox: {e}")

        return sandbox

    async def start(self, project_id: str) -> Sandbox:
        """Start a sandbox container."""
        sandbox = self._sandboxes.get(project_id)
        if not sandbox:
            raise ValueError(f"Sandbox not found for project {project_id}")

        logger.info("starting_sandbox", project_id=project_id)

        try:
            client = self._get_client()
            container = client.containers.get(sandbox.container_id)

            container.start()
            sandbox.status = SandboxStatus.RUNNING
            sandbox.started_at = datetime.now(timezone.utc)
            sandbox.last_activity = sandbox.started_at
            sandbox.updated_at = datetime.now(timezone.utc)

            logger.info("sandbox_started", project_id=project_id)
        except docker.errors.APIError as e:
            sandbox.status = SandboxStatus.CRASHED
            logger.error("sandbox_start_failed", project_id=project_id, error=str(e))
            raise RuntimeError(f"Failed to start sandbox: {e}")

        return sandbox

    async def stop(self, project_id: str) -> Sandbox:
        """Stop a sandbox container."""
        sandbox = self._sandboxes.get(project_id)
        if not sandbox:
            raise ValueError(f"Sandbox not found for project {project_id}")

        logger.info("stopping_sandbox", project_id=project_id)
        sandbox.status = SandboxStatus.STOPPING

        try:
            client = self._get_client()
            container = client.containers.get(sandbox.container_id)

            container.stop(timeout=10)
            sandbox.status = SandboxStatus.STOPPED
            sandbox.updated_at = datetime.now(timezone.utc)

            logger.info("sandbox_stopped", project_id=project_id)
        except docker.errors.NotFound:
            sandbox.status = SandboxStatus.CRASHED
            logger.warning("sandbox_not_found", project_id=project_id)
        except docker.errors.APIError as e:
            logger.error("sandbox_stop_failed", project_id=project_id, error=str(e))

        return sandbox

    async def restart(self, project_id: str) -> Sandbox:
        """Restart a sandbox container."""
        await self.stop(project_id)
        return await self.start(project_id)

    async def destroy(self, project_id: str) -> Sandbox:
        """Destroy a sandbox container and workspace."""
        sandbox = self._sandboxes.get(project_id)
        if not sandbox:
            return Sandbox(project_id=project_id, sandbox_id=f"sb_{uuid.uuid4().hex[:12]}")

        logger.info("destroying_sandbox", project_id=project_id)
        sandbox.status = SandboxStatus.DESTROY_PENDING

        try:
            client = self._get_client()
            container = client.containers.get(sandbox.container_id)
            container.kill()
            container.remove(force=True)
        except docker.errors.NotFound:
            pass  # Container already gone
        except docker.errors.APIError as e:
            logger.warning("sandbox_destroy_warning", project_id=project_id, error=str(e))

        # Clean up workspace
        workspace_path = self._get_workspace_path(project_id)
        if workspace_path.exists():
            shutil.rmtree(workspace_path, ignore_errors=True)

        sandbox.status = SandboxStatus.DESTROYED
        sandbox.updated_at = datetime.now(timezone.utc)

        if project_id in self._sandboxes:
            del self._sandboxes[project_id]

        logger.info("sandbox_destroyed", project_id=project_id)
        return sandbox

    async def execute(
        self, project_id: str, command: str, timeout: int | None = None
    ) -> ExecutionResult:
        """Execute a command in the sandbox."""
        sandbox = self._sandboxes.get(project_id)
        if not sandbox or sandbox.status != SandboxStatus.RUNNING:
            raise ValueError(f"Sandbox not running for project {project_id}")

        logger.info("executing_in_sandbox", project_id=project_id, command=command[:100])

        client = self._get_client()
        container = client.containers.get(sandbox.container_id)

        start_time = datetime.now(timezone.utc)
        timeout = timeout or self.config.timeout

        try:
            result = container.exec_run(
                command,
                timeout=timeout,
                workdir="/workspace",
                environment={"PWD": "/workspace"},
            )

            stdout = result.output.decode()[: self.config.max_output_bytes] if result.output else ""
            stderr = result.stderr.decode()[: self.config.max_output_bytes] if result.stderr else ""

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return ExecutionResult(
                success=result.exit_code == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=result.exit_code,
                duration_seconds=duration,
                status=(
                    ExecutionStatus.COMPLETED if result.exit_code == 0 else ExecutionStatus.FAILED
                ),
                job_id=f"exec_{uuid.uuid4().hex[:8]}",
            )

        except docker.errors.APIError as e:
            logger.error("sandbox_execute_failed", project_id=project_id, error=str(e))
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                duration_seconds=0,
                status=ExecutionStatus.FAILED,
                job_id=f"exec_{uuid.uuid4().hex[:8]}",
            )

    async def stream_execute(
        self,
        project_id: str,
        command: str,
        timeout: int | None = None,
        on_output: callable | None = None,
    ) -> ExecutionResult:
        """Stream command execution output."""
        sandbox = self._sandboxes.get(project_id)
        if not sandbox or sandbox.status != SandboxStatus.RUNNING:
            raise ValueError(f"Sandbox not running for project {project_id}")

        client = self._get_client()
        container = client.containers.get(sandbox.container_id)

        start_time = datetime.now(timezone.utc)
        timeout = timeout or self.config.timeout

        stdout_chunks = []
        stderr_chunks = []

        try:
            for chunk in container.exec_run(
                command,
                stdout=True,
                stderr=True,
                stream=True,
                timeout=timeout,
                workdir="/workspace",
            ):
                if chunk:
                    if isinstance(chunk, bytes):
                        if b"\n" in chunk or len(stdout_chunks) == 0:
                            stdout_chunks.append(chunk.decode("utf-8", errors="replace"))
                    if on_output:
                        await on_output(chunk)

            stdout = "".join(stdout_chunks)[: self.config.max_output_bytes]
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return ExecutionResult(
                success=True,
                stdout=stdout,
                stderr="".join(stderr_chunks),
                exit_code=0,
                duration_seconds=duration,
                status=ExecutionStatus.COMPLETED,
                job_id=f"exec_{uuid.uuid4().hex[:8]}",
            )

        except Exception as e:
            logger.error("sandbox_stream_execute_failed", project_id=project_id, error=str(e))
            return ExecutionResult(
                success=False,
                stdout="".join(stdout_chunks),
                stderr=str(e),
                exit_code=1,
                duration_seconds=0,
                status=ExecutionStatus.FAILED,
                job_id=f"exec_{uuid.uuid4().hex[:8]}",
            )

    async def get_status(self, project_id: str) -> SandboxStatus:
        """Get sandbox status."""
        sandbox = self._sandboxes.get(project_id)
        if not sandbox:
            raise ValueError(f"Sandbox not found for project {project_id}")

        if sandbox.container_id:
            try:
                client = self._get_client()
                container = client.containers.get(sandbox.container_id)
                status = container.status
                sandbox.last_activity = datetime.now(timezone.utc)
                return status
            except docker.errors.NotFound:
                return SandboxStatus.CRASHED

        return sandbox.status

    async def write_file(self, project_id: str, path: str, content: str) -> bool:
        """Write a file in the sandbox workspace."""
        workspace = self._get_workspace_path(project_id)
        file_path = workspace / path

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            f.write(content)

        return True

    async def read_file(self, project_id: str, path: str) -> str:
        """Read a file from the sandbox workspace."""
        workspace = self._get_workspace_path(project_id)
        file_path = workspace / path

        with open(file_path, "r") as f:
            return f.read()

    async def list_files(self, project_id: str, path: str = "") -> list[str]:
        """List files in the sandbox workspace."""
        workspace = self._get_workspace_path(project_id)
        target = workspace / path if path else workspace

        if not target.exists():
            return []

        return [f.name for f in target.iterdir()]


# Global sandbox manager instance
_sandbox_manager: DockerSandboxProvider | None = None


def get_sandbox_manager(config: DockerSandboxConfig | None = None) -> DockerSandboxProvider:
    """Get or create the global sandbox manager."""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = DockerSandboxProvider(config)
    return _sandbox_manager


def reset_sandbox_manager():
    """Reset the sandbox manager (useful for testing)."""
    global _sandbox_manager
    if _sandbox_manager:
        # Clean up running containers
        for sandbox in _sandbox_manager._sandboxes.values():
            if sandbox.container_id:
                try:
                    client = _sandbox_manager._get_client()
                    container = client.containers.get(sandbox.container_id)
                    container.kill()
                    container.remove(force=True)
                except Exception:
                    pass
    _sandbox_manager = None
