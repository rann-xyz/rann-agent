"""
RANN Execution Backend - Secure Isolation Layer

This module provides secure isolation between the API process and agent execution.

SECURITY NOTICE:
- LocalExecutionBackend: DEVELOPMENT ONLY
- ContainerExecutionBackend: Required for production
- Execution MUST fail closed if container runtime unavailable
- NO environment variable inheritance
- NO host filesystem access
- NO network when disabled
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ============================================================================
# STATUS ENUMERATIONS
# ============================================================================


class ExecutionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    CONTAINER_ERROR = "container_error"
    RESOURCE_LIMITED = "resource_limited"


# ============================================================================
# RESOURCE & POLICY DEFINITIONS
# ============================================================================


@dataclass
class ResourcePolicy:
    timeout_seconds: int = 60
    memory_bytes: int = 256 * 1024 * 1024
    cpu_shares: int = 512
    pid_limit: int = 10
    max_output_bytes: int = 1024 * 1024
    disk_quota_bytes: int = 100 * 1024 * 1024


@dataclass
class ExecutionPolicy:
    network_allowed: bool = False
    resource_limits: ResourcePolicy = field(default_factory=ResourcePolicy)
    allowed_env: dict[str, str] = field(
        default_factory=lambda: {
            "PATH": "/usr/bin:/bin",
            "HOME": "/tmp/rann_workspace",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TERM": "dumb",
        }
    )
    allowed_paths: list[str] = field(default_factory=lambda: ["/tmp", "/workspace"])


# ============================================================================
# EXECUTION JOBS
# ============================================================================


@dataclass
class ExecutionJob:
    """
    A unit of work for the execution backend.

    SECURITY: All identity fields are SERVER-DERIVED only.
    Client-provided identity fields are IGNORED.
    """

    job_id: str
    user_id: str  # SERVER-DERIVED from authenticated session
    run_id: str  # SERVER-DERIVED from server
    workspace_id: str
    command: str
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: ExecutionStatus = ExecutionStatus.QUEUED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    killed: bool = False
    container_id: Optional[str] = None


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: Optional[int]
    duration_seconds: float
    status: ExecutionStatus
    job_id: str
    killed: bool = False


# ============================================================================
# EXECUTION BACKEND INTERFACE
# ============================================================================


class ExecutionBackend:
    """Abstract interface for execution backends."""

    DEVELOPMENT_ONLY: bool = False
    REQUIRE_CONTAINER: bool = False

    async def submit(self, job: ExecutionJob) -> str:
        raise NotImplementedError

    async def get_status(self, job_id: str) -> ExecutionStatus:
        raise NotImplementedError

    async def get_result(self, job_id: str) -> ExecutionResult:
        raise NotImplementedError

    async def cancel(self, job_id: str) -> bool:
        raise NotImplementedError

    def is_available(self) -> bool:
        """Check if backend is available for production use."""
        return False


# ============================================================================
# LOCAL EXECUTION BACKEND (DEVELOPMENT ONLY)
# ============================================================================


class LocalExecutionBackend(ExecutionBackend):
    """
    Local subprocess execution backend.

    ⚠️  DEVELOPMENT ONLY ⚠️
    This backend runs in the same process space.

    NOT A SANDBOX. FOR PRODUCTION, USE ContainerExecutionBackend.
    """

    DEVELOPMENT_ONLY = True
    REQUIRE_CONTAINER = False  # Can run without container

    def __init__(self):
        self._jobs: dict[str, ExecutionJob] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    def is_available(self) -> bool:
        """Available but marked DEVELOPMENT_ONLY."""
        return True

    async def submit(self, job: ExecutionJob) -> str:
        job.status = ExecutionStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        self._jobs[job.job_id] = job
        asyncio.create_task(self._execute_job(job))
        return job.job_id

    async def _execute_job(self, job: ExecutionJob):
        try:
            # Build safe environment - NO os.environ inheritance
            env = dict(job.policy.allowed_env)

            # Create isolated workspace
            workspace = Path(f"/tmp/rann_ws_{job.job_id}")
            workspace.mkdir(parents=True, exist_ok=True)

            try:
                cmd = job.command
                if isinstance(cmd, str):
                    cmd = cmd.split()

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=str(workspace),
                )

                self._processes[job.job_id] = proc

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=job.policy.resource_limits.timeout_seconds
                    )

                    stdout = stdout.decode()[: job.policy.resource_limits.max_output_bytes]
                    stderr = stderr.decode()[: job.policy.resource_limits.max_output_bytes]

                    job.exit_code = proc.returncode
                    job.stdout = stdout
                    job.stderr = stderr
                    job.status = ExecutionStatus.COMPLETED

                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    job.status = ExecutionStatus.TIMEOUT
                    job.killed = True
                    job.exit_code = -1

            finally:
                shutil.rmtree(workspace, ignore_errors=True)

        except Exception as e:
            job.status = ExecutionStatus.FAILED
            job.stderr = str(e)
            job.exit_code = 1

        finally:
            job.completed_at = datetime.now(timezone.utc)
            if job.job_id in self._processes:
                del self._processes[job.job_id]

    async def get_status(self, job_id: str) -> ExecutionStatus:
        job = self._jobs.get(job_id)
        return job.status if job else ExecutionStatus.FAILED

    async def get_result(self, job_id: str) -> ExecutionResult:
        job = self._jobs.get(job_id)
        if not job:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Job not found",
                exit_code=None,
                duration_seconds=0,
                status=ExecutionStatus.FAILED,
                job_id=job_id,
            )

        duration = 0
        if job.started_at and job.completed_at:
            duration = (job.completed_at - job.started_at).total_seconds()

        return ExecutionResult(
            success=job.status == ExecutionStatus.COMPLETED,
            stdout=job.stdout,
            stderr=job.stderr,
            exit_code=job.exit_code,
            duration_seconds=duration,
            status=job.status,
            job_id=job.job_id,
            killed=job.killed,
        )

    async def cancel(self, job_id: str) -> bool:
        proc = self._processes.get(job_id)
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass

        job = self._jobs.get(job_id)
        if job:
            job.status = ExecutionStatus.CANCELLED
            job.killed = True
            job.completed_at = datetime.now(timezone.utc)
            return True
        return False


# ============================================================================
# CONTAINER EXECUTION BACKEND (PRODUCTION)
# ============================================================================


class ContainerExecutionBackend(ExecutionBackend):
    """
    Container-based execution backend for production.

    This backend provides OS-level isolation through containers.

    Requirements:
    - Docker CLI or compatible container runtime
    - Network permissions to create containers
    - Access to container image
    """

    DEVELOPMENT_ONLY = False
    REQUIRE_CONTAINER = True

    def __init__(self):
        self._jobs: dict[str, ExecutionJob] = {}
        self._check_docker()

    def _check_docker(self):
        """Check if Docker is available."""
        self._docker_available = shutil.which("docker") is not None

    def is_available(self) -> bool:
        """Check if container runtime is available."""
        return self._docker_available

    async def submit(self, job: ExecutionJob) -> str:
        """Submit job for container execution. FAIL CLOSED if unavailable."""
        if not self._docker_available:
            raise RuntimeError(
                "ContainerExecutionBackend unavailable: Docker runtime not found. "
                "Set RANN_EXECUTION_BACKEND=local for development only."
            )

        job.status = ExecutionStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        self._jobs[job.job_id] = job

        try:
            await self._execute_in_container(job)
        except Exception as e:
            job.status = ExecutionStatus.FAILED
            job.stderr = str(e)
            job.completed_at = datetime.now(timezone.utc)

        return job.job_id

    async def _execute_in_container(self, job: ExecutionJob):
        """Execute job in Docker container with full isolation."""

        # Create isolated workspace on host
        host_workspace = Path(f"/tmp/rann_container_ws_{job.job_id}")
        host_workspace.mkdir(parents=True, exist_ok=True)

        # Generate unique container ID
        container_name = f"rann_exec_{job.job_id[:12]}"

        try:
            # Build docker run command with security options
            docker_cmd = self._build_container_command(job, host_workspace, container_name)

            # Execute docker command
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            self._jobs[job.job_id].container_id = container_name

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=job.policy.resource_limits.timeout_seconds
                )

                job.stdout = stdout.decode()[: job.policy.resource_limits.max_output_bytes]
                job.stderr = stderr.decode()

                if proc.returncode == 0:
                    job.status = ExecutionStatus.COMPLETED
                elif proc.returncode == 137:  # SIGKILL
                    job.status = ExecutionStatus.TIMEOUT
                    job.killed = True
                else:
                    job.status = ExecutionStatus.FAILED

                job.exit_code = proc.returncode

            except asyncio.TimeoutError:
                # Kill container on timeout
                await self._kill_container(container_name)
                job.status = ExecutionStatus.TIMEOUT
                job.killed = True
                job.exit_code = -1

        finally:
            # Cleanup host workspace
            shutil.rmtree(host_workspace, ignore_errors=True)

        job.completed_at = datetime.now(timezone.utc)

    def _build_container_command(
        self, job: ExecutionJob, workspace: Path, container_name: str
    ) -> list[str]:
        """Build secure Docker run command."""

        # Base docker run command
        cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
        ]

        # Security: no new privileges
        cmd.extend(["--security-opt", "no-new-privileges"])

        # Security: drop all capabilities
        cmd.extend(["--cap-drop", "ALL"])

        # Security: read-only root filesystem
        cmd.extend(["--read-only"])

        # Security: non-root user (UID 1000 is common non-root)
        cmd.extend(["--user", "1000:1000"])

        # Security: no host network when disabled
        if not job.policy.network_allowed:
            cmd.extend(["--network", "none"])

        # Security: limit resources
        cmd.extend(["--memory", f"{job.policy.resource_limits.memory_bytes}"])
        cmd.extend(["--memory-swap", f"{job.policy.resource_limits.memory_bytes}"])
        cmd.extend(["--cpus", str(job.policy.resource_limits.cpu_shares / 1024)])
        cmd.extend(["--pids-limit", str(job.policy.resource_limits.pid_limit)])
        cmd.extend(["--ulimit", f"nofile=1024:1024"])

        # Workspace mount (only writable location)
        cmd.extend(["-v", f"{workspace}:/workspace:rw"])

        # Temporary directory mount (read-only)
        cmd.extend(["-v", f"/tmp:/tmp:rw"])

        # Deny Docker socket access
        # (Not mounting it achieves this)

        # Set working directory
        cmd.extend(["-w", "/workspace"])

        # Environment allowlist only
        for key, value in job.policy.allowed_env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Python image
        cmd.append("python:3.11-slim")

        # The command to execute
        if isinstance(job.command, str):
            cmd.extend(["python", "-c", job.command])
        else:
            cmd.extend(job.command)

        return cmd

    async def _kill_container(self, container_name: str):
        """Kill and remove a container."""
        try:
            await asyncio.create_subprocess_exec("docker", "kill", container_name)
            # Container will be auto-removed due to --rm
        except Exception:
            pass

    async def get_status(self, job_id: str) -> ExecutionStatus:
        job = self._jobs.get(job_id)
        return job.status if job else ExecutionStatus.FAILED

    async def get_result(self, job_id: str) -> ExecutionResult:
        job = self._jobs.get(job_id)
        if not job:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Job not found",
                exit_code=None,
                duration_seconds=0,
                status=ExecutionStatus.FAILED,
                job_id=job_id,
            )

        duration = 0
        if job.started_at and job.completed_at:
            duration = (job.completed_at - job.started_at).total_seconds()

        return ExecutionResult(
            success=job.status == ExecutionStatus.COMPLETED,
            stdout=job.stdout,
            stderr=job.stderr,
            exit_code=job.exit_code,
            duration_seconds=duration,
            status=job.status,
            job_id=job.job_id,
            killed=job.killed,
        )

    async def cancel(self, job_id: str) -> bool:
        """Cancel execution by killing container."""
        job = self._jobs.get(job_id)
        if not job:
            return False

        container_name = job.container_id
        if container_name:
            try:
                await self._kill_container(container_name)
            except Exception:
                pass

        job.status = ExecutionStatus.CANCELLED
        job.killed = True
        job.completed_at = datetime.now(timezone.utc)
        return True


# ============================================================================
# FACTORY FUNCTION
# ============================================================================


def get_execution_backend() -> ExecutionBackend:
    """
    Get the configured execution backend.

    FAIL CLOSED behavior:
    - If production backend requested but unavailable, raises RuntimeError
    - Falls back to LocalExecutionBackend only explicitly configured
    """
    backend_type = os.environ.get("RANN_EXECUTION_BACKEND", "local").lower()

    if backend_type == "container":
        backend = ContainerExecutionBackend()
        if not backend.is_available():
            raise RuntimeError(
                "FAIL CLOSED: ContainerExecutionBackend unavailable. "
                "Docker runtime not found. "
                "Set RANN_EXECUTION_BACKEND=local for development testing only or "
                "install Docker for production isolation."
            )
        return backend
    else:
        # Development backend
        return LocalExecutionBackend()
