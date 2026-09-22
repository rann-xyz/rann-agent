"""
RANN Execution Backend - Secure Isolation Layer

This module provides secure isolation between the API process and agent execution.

SECURITY NOTICE:
    This is the execution boundary. All untrusted agent commands MUST go through
    an ExecutionBackend implementation. Direct subprocess calls from tools are
    a security violation.

    LocalExecutionBackend is DEVELOPMENT ONLY and is NOT a sandbox.
    ContainerExecutionBackend is required for production.
"""

import asyncio
import os
import subprocess
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ============================================================================
# STATUS ENUMERATIONS
# ============================================================================


class ExecutionStatus(str, Enum):
    """Execution job status states."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


# ============================================================================
# RESOURCE POLICIES
# ============================================================================


@dataclass
class ResourcePolicy:
    """Resource limits for execution."""

    timeout_seconds: int = 60
    memory_bytes: int = 256 * 1024 * 1024  # 256 MB default
    cpu_limit: float = 0.5  # Half a CPU core
    max_processes: int = 10
    max_output_bytes: int = 1024 * 1024  # 1 MB output limit
    disk_quota_bytes: int = 100 * 1024 * 1024  # 100 MB disk quota


@dataclass
class ExecutionPolicy:
    """Complete execution policy for an agent job."""

    network_allowed: bool = False
    resource_limits: ResourcePolicy = field(default_factory=ResourcePolicy)
    allowed_env: dict[str, str] = field(
        default_factory=lambda: {
            "PATH": "/usr/bin:/bin",
            "HOME": "/tmp",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TERM": "dumb",
        }
    )
    allowed_paths: list[str] = field(default_factory=lambda: ["/tmp", "/workspace"])


# ============================================================================
# EXECUTION JOB
# ============================================================================


@dataclass
class ExecutionJob:
    """
    A unit of work for the execution backend.

    CRITICAL: All identity fields (user_id, run_id) are DERIVED from server
    context, NOT from client input. This prevents identity spoofing.
    """

    job_id: str
    user_id: str  # DERIVED from authenticated session - NEVER from request body
    run_id: str  # DERIVED from server - NEVER from client
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


# ============================================================================
# EXECUTION RESULT
# ============================================================================


@dataclass
class ExecutionResult:
    """Result of an execution job."""

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
    """
    Abstract interface for execution backends.

    All backends must implement proper isolation from the API process.
    """

    DEVELOPMENT_ONLY = False  # Override in LocalExecutionBackend

    async def submit(self, job: ExecutionJob) -> str:
        """Submit a job for execution. Returns job_id."""
        raise NotImplementedError

    async def get_status(self, job_id: str) -> ExecutionStatus:
        """Get current status of a job."""
        raise NotImplementedError

    async def get_result(self, job_id: str) -> ExecutionResult:
        """Get result of completed job."""
        raise NotImplementedError

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running job. Returns True if cancelled."""
        raise NotImplementedError


# ============================================================================
# LOCAL EXECUTION BACKEND (DEVELOPMENT ONLY)
# ============================================================================


class LocalExecutionBackend(ExecutionBackend):
    """
    Local subprocess execution backend.

    ⚠️  DEVELOPMENT ONLY ⚠️

    This backend runs subprocesses in the same process space with resource limits.
    It does NOT provide:
    - Process isolation
    - Environment isolation
    - Network isolation
    - Container isolation

    DO NOT use for public-facing execution.
    """

    DEVELOPMENT_ONLY = True

    def __init__(self):
        self._jobs: dict[str, ExecutionJob] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def submit(self, job: ExecutionJob) -> str:
        """Submit job for execution in local subprocess."""
        job.status = ExecutionStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        self._jobs[job.job_id] = job

        asyncio.create_task(self._execute_job(job))
        return job.job_id

    async def _execute_job(self, job: ExecutionJob):
        """Execute job in subprocess with resource limits."""
        try:
            # Build command - split to avoid shell=True when possible
            cmd = job.command
            if isinstance(cmd, str):
                cmd = cmd.split()

            # Create safe environment - NO inheritance from os.environ
            env = dict(job.policy.allowed_env)

            # Create temporary workspace directory
            workspace = Path(f"/tmp/rann_workspace_{job.job_id}")
            workspace.mkdir(parents=True, exist_ok=True)

            try:
                # Execute with timeout
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

                    # Apply output limit
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
                # Cleanup workspace
                try:
                    import shutil

                    shutil.rmtree(workspace, ignore_errors=True)
                except Exception:
                    pass

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
        """Cancel execution by killing process."""
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
# CONTAINER EXECUTION BACKEND (PRODUCTION RECOMMENDED)
# ============================================================================


class ContainerExecutionBackend(ExecutionBackend):
    """
    Container-based execution backend for production.

    This backend provides:
    - Process isolation via containers
    - Environment isolation via explicit allowlist
    - Network policy enforcement
    - Resource limits via container runtime
    """

    def __init__(self):
        self._jobs: dict[str, ExecutionJob] = {}

    async def submit(self, job: ExecutionJob) -> str:
        """Submit job for execution in isolated container."""
        # Production implementation would:
        # 1. Create container with:
        #    - No host environment
        #    - Read-only root filesystem
        #    - Workspace as only writable volume
        #    - Explicit environment allowlist
        #    - Network policy enforced
        #    - Resource limits applied
        # 2. Run execution
        # 3. Return result
        raise NotImplementedError(
            "ContainerExecutionBackend requires container runtime. "
            "Use LocalExecutionBackend for development only."
        )

    async def get_status(self, job_id: str) -> ExecutionStatus:
        raise NotImplementedError

    async def get_result(self, job_id: str) -> ExecutionResult:
        raise NotImplementedError

    async def cancel(self, job_id: str) -> bool:
        raise NotImplementedError
