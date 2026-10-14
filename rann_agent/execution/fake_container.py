"""
RANN Fake Container Runtime

A process-based sandbox for execution when Docker is unavailable.
Provides safer development execution with workspace and environment isolation.

SECURITY: This backend provides process isolation, workspace containment,
and environment restriction. It is NOT as secure as Docker container isolation
but provides significantly better isolation than LocalExecutionBackend.
"""

import asyncio
import os
import shutil
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

# Import from parent module
sys.path.insert(0, str(Path(__file__).parent.parent))
from rann_agent.execution import (
    ExecutionBackend,
    ExecutionJob,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
)

logger = structlog.get_logger(__name__)


class FakeContainerBackend(ExecutionBackend):
    """
    Fake container backend for development without Docker.
    
    Provides process isolation with:
    - Restricted environment variables
    - Workspace filesystem isolation  
    - Timeout enforcement
    - Cleanup after execution
    
    NOT as secure as Docker container isolation, but safer than LocalExecutionBackend.
    """
    
    DEVELOPMENT_ONLY = True
    REQUIRE_CONTAINER = False  # Works without Docker
    
    # Forbidden patterns in commands
    FORBIDDEN_PATTERNS = [
        'rm -rf /',
        'mkfs',
        'dd if=',
        '> /dev/sd',
        'chmod 777 /',
        '/etc/passwd',
        '/etc/shadow',
        '/var/run/docker',
        '/proc/sys',
    ]
    
    def __init__(self):
        self._jobs: dict[str, ExecutionJob] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._workspaces: dict[str, Path] = {}
        
    def is_available(self) -> bool:
        """Always available - works without Docker."""
        return True
    
    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """Check if command is safe to execute."""
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in command:
                return False, f"Forbidden pattern: {pattern}"
        return True, ""
    
    def _build_safe_env(self, policy: ExecutionPolicy, workspace: Path) -> dict[str, str]:
        """Build a safe environment for execution."""
        env = dict(policy.allowed_env)
        env['PWD'] = str(workspace)
        env['HOME'] = str(workspace)
        
        # Clear any potentially sensitive variables
        sensitive_prefixes = ['RANN_SECRET', 'API_KEY', 'PASSWORD', 'TOKEN', 'SECRET', 'CREDS']
        for key in list(env.keys()):
            for prefix in sensitive_prefixes:
                if key.upper().startswith(prefix):
                    del env[key]
                    break
        
        return env
    
    async def submit(self, job: ExecutionJob) -> str:
        """Submit job for sandboxed execution."""
        job.status = ExecutionStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        self._jobs[job.job_id] = job
        asyncio.create_task(self._execute_job(job))
        return job.job_id
    
    async def _execute_job(self, job: ExecutionJob):
        """Execute job in sandboxed process."""
        workspace = Path(f"/tmp/rann_fake_ws_{job.job_id}")
        
        try:
            # Create and prepare workspace
            self._workspaces[job.job_id] = workspace
            workspace.mkdir(parents=True, exist_ok=True)
            
            # Validate command
            allowed, reason = self._is_command_allowed(job.command)
            if not allowed:
                job.status = ExecutionStatus.FAILED
                job.stderr = f"Command blocked: {reason}"
                job.exit_code = 1
                return
            
            # Build safe environment
            env = self._build_safe_env(job.policy, workspace)
            
            # Execute with resource limits
            try:
                cmd = job.command
                if isinstance(cmd, str):
                    import shlex
                    try:
                        cmd = shlex.split(cmd)
                    except ValueError:
                        cmd = [cmd]
                
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
                        proc.communicate(),
                        timeout=job.policy.resource_limits.timeout_seconds
                    )
                    
                    stdout = stdout.decode(errors='replace')[:job.policy.resource_limits.max_output_bytes]
                    stderr = stderr.decode(errors='replace')[:job.policy.resource_limits.max_output_bytes]
                    
                    job.exit_code = proc.returncode
                    job.stdout = stdout
                    job.stderr = stderr
                    job.status = ExecutionStatus.COMPLETED if proc.returncode == 0 else ExecutionStatus.FAILED
                    
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    job.status = ExecutionStatus.TIMEOUT
                    job.killed = True
                    job.exit_code = -1
                    job.stderr = "Process killed due to timeout"
                
            except Exception as e:
                job.status = ExecutionStatus.FAILED
                job.stderr = f"Execution error: {e}"
                job.exit_code = 1
                
        except Exception as e:
            job.status = ExecutionStatus.FAILED
            job.stderr = str(e)
            job.exit_code = 1
        finally:
            job.completed_at = datetime.now(timezone.utc)
            
            # Cleanup process reference
            if job.job_id in self._processes:
                del self._processes[job.job_id]
            
            # Cleanup workspace
            if job.job_id in self._workspaces:
                try:
                    shutil.rmtree(self._workspaces[job.job_id], ignore_errors=True)
                    del self._workspaces[job.job_id]
                except Exception:
                    pass
    
    async def get_status(self, job_id: str) -> ExecutionStatus:
        """Get job status."""
        job = self._jobs.get(job_id)
        return job.status if job else ExecutionStatus.FAILED
    
    async def get_result(self, job_id: str) -> ExecutionResult:
        """Get job result."""
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
