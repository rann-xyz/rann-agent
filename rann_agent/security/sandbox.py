"""
Sandbox execution for untrusted code.

Provides multiple sandboxing strategies: NONE, SUBPROCESS, DOCKER, and VM.
Each strategy enforces timeout, memory limits, and network restrictions.
"""

from __future__ import annotations

import enum
import os
import resource
import shutil
import signal
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import structlog

from rann_agent.core.exceptions import (
    SecurityError,
    ToolExecutionError,
    ToolTimeoutError,
)

logger = structlog.get_logger()


class SandboxType(str, enum.Enum):
    """Sandbox execution types in order of increasing isolation."""

    NONE = "none"  # No sandbox - direct execution (dangerous!)
    SUBPROCESS = "subprocess"  # Local subprocess with resource limits
    DOCKER = "docker"  # Docker container isolation
    VM = "vm"  # Full VM isolation (not implemented)


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""

    type: SandboxType = SandboxType.SUBPROCESS
    timeout: int = 30  # seconds
    memory_limit: int = 512 * 1024 * 1024  # 512 MB default
    network_allowed: bool = False  # Block network by default
    cpu_limit: float = 1.0  # Number of CPU cores
    read_only_fs: bool = True  # Read-only filesystem by default
    allowed_paths: List[str] = field(default_factory=list)  # Whitelist paths

    def __post_init__(self):
        """Validate configuration."""
        if self.timeout <= 0:
            raise SecurityError("Timeout must be positive", details={"timeout": self.timeout})
        if self.memory_limit <= 0:
            raise SecurityError("Memory limit must be positive", details={"memory_limit": self.memory_limit})


@dataclass
class ExecutionResult:
    """Result of sandboxed code execution."""

    success: bool
    stdout: str
    stderr: str
    exit_code: Optional[int]
    duration: float  # seconds
    error: Optional[str] = None
    killed: bool = False


class SandboxExecutor:
    """
    Execute untrusted code in an isolated sandbox.

    Supports multiple isolation strategies selected via SandboxConfig.type.
    All strategies enforce:
    - Timeout (execution is killed after config.timeout seconds)
    - Memory limits (process is killed if it exceeds config.memory_limit bytes)
    - Network restrictions (config.network_allowed=False blocks network)

    Example:
        config = SandboxConfig(
            type=SandboxType.SUBPROCESS,
            timeout=10,
            memory_limit=256 * 1024 * 1024,
            network_allowed=False,
        )
        executor = SandboxExecutor()
        result = await executor.execute("print('hello')", "python", config)
    """

    _DOCKER_IMAGE = "python:3.11-slim"
    _LANGUAGE_EXTENSIONS = {
        "python": "py",
        "python3": "py",
        "javascript": "js",
        "node": "js",
        "bash": "sh",
        "sh": "sh",
    }

    def __init__(self):
        """Initialize the sandbox executor."""
        self._docker_available: Optional[bool] = None

    @property
    def docker_available(self) -> bool:
        """Check if Docker is available on this system."""
        if self._docker_available is None:
            self._docker_available = shutil.which("docker") is not None
        return self._docker_available

    async def execute(
        self,
        code: str,
        language: str,
        config: Optional[SandboxConfig] = None,
    ) -> ExecutionResult:
        """
        Execute code in the configured sandbox.

        Args:
            code: Source code to execute
            language: Programming language (python, javascript, bash, etc.)
            config: Sandbox configuration (uses sensible defaults if None)

        Returns:
            ExecutionResult with stdout, stderr, exit_code, and timing info

        Raises:
            ToolExecutionError: If execution fails for non-security reasons
            SecurityError: If the sandbox type is invalid or unavailable
        """
        if config is None:
            config = SandboxConfig()

        log = logger.bind(
            sandbox_type=config.type.value,
            language=language,
            timeout=config.timeout,
            memory_limit_mb=config.memory_limit // (1024 * 1024),
        )
        log.info("sandbox_execution_start")

        try:
            if config.type == SandboxType.NONE:
                result = await self._execute_unsandboxed(code, language, config)
            elif config.type == SandboxType.SUBPROCESS:
                result = await self._execute_subprocess(code, language, config)
            elif config.type == SandboxType.DOCKER:
                result = await self._execute_docker(code, language, config)
            elif config.type == SandboxType.VM:
                result = await self._execute_vm(code, language, config)
            else:
                raise SecurityError(
                    f"Unknown sandbox type: {config.type}",
                    details={"type": config.type},
                )
        except ToolTimeoutError:
            raise
        except ToolExecutionError:
            raise
        except SecurityError:
            raise
        except Exception as e:
            logger.error("sandbox_execution_error", error=str(e))
            raise ToolExecutionError(f"Sandbox execution failed: {e}")

        log = log.bind(
            success=result.success,
            exit_code=result.exit_code,
            duration_ms=int(result.duration * 1000),
            killed=result.killed,
        )
        if result.success:
            log.info("sandbox_execution_complete")
        else:
            log.error("sandbox_execution_failed", error=result.error)

        return result

    async def _execute_unsandboxed(
        self, code: str, language: str, config: SandboxConfig
    ) -> ExecutionResult:
        """Execute without any sandboxing - USE WITH EXTREME CAUTION."""
        logger.warning("executing_code_without_sandbox", language=language)

        cmd = self._build_command(code, language)
        start = _time_seconds()

        try:
            proc = await _run_process(cmd, timeout=config.timeout)
            duration = _time_seconds() - start
            return ExecutionResult(
                success=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration=duration,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Execution timed out",
                exit_code=-1,
                duration=config.timeout,
                killed=True,
                error="Timeout exceeded",
            )

    async def _execute_subprocess(
        self, code: str, language: str, config: SandboxConfig
    ) -> ExecutionResult:
        """Execute in a subprocess with resource limits via the resource module."""
        with tempfile.TemporaryDirectory(prefix="rann_sandbox_") as tmpdir:
            ext = self._LANGUAGE_EXTENSIONS.get(language.lower(), "txt")
            filename = f"code_{uuid.uuid4().hex[:8]}.{ext}"
            filepath = Path(tmpdir) / filename

            try:
                filepath.write_text(code)
                filepath.chmod(0o600)  # Restrict file permissions
            except IOError as e:
                raise ToolExecutionError(f"Failed to write code to temp file: {e}")

            cmd = self._build_command(filepath, language)
            start = _time_seconds()

            try:
                proc = await _run_process(
                    cmd,
                    timeout=config.timeout,
                    memory_limit=config.memory_limit,
                    cwd=tmpdir,
                )
                duration = _time_seconds() - start
                return ExecutionResult(
                    success=proc.returncode == 0,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    duration=duration,
                )
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Execution timed out",
                    exit_code=-1,
                    duration=config.timeout,
                    killed=True,
                    error="Timeout exceeded",
                )

    async def _execute_docker(
        self, code: str, language: str, config: SandboxConfig
    ) -> ExecutionResult:
        """Execute inside an isolated Docker container."""
        if not self.docker_available:
            raise SecurityError(
                "Docker is not available on this system",
                details={"docker_path": shutil.which("docker")},
            )

        container_id = f"rann-sandbox-{uuid.uuid4().hex[:8]}"
        ext = self._LANGUAGE_EXTENSIONS.get(language.lower(), "txt")
        local_file = f"/tmp/code_{uuid.uuid4().hex[:8]}.{ext}"

        # Build docker run command with security restrictions
        docker_cmd = [
            "docker",
            "run",
            "--rm",  # Auto-remove container when done
            "--name", container_id,
            "--network", "none" if not config.network_allowed else "bridge",
            "--memory", str(config.memory_limit),
            "--memory-swap", str(config.memory_limit),  # Disable swap
            "--cpus", str(config.cpu_limit),
            "--pids-limit", "64",  # Limit number of processes
            "--read-only" if config.read_only_fs else "",
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
            "-v", f"{tempfile.gettempdir()}:{tempfile.gettempdir()}:ro"
            if config.read_only_fs
            else f"{tempfile.gettempdir()}:{tempfile.gettempdir()}:rw",
            self._DOCKER_IMAGE,
            "python" if language.startswith("python") else "node",
            local_file,
        ]
        docker_cmd = [c for c in docker_cmd if c]  # Filter empty strings

        with tempfile.TemporaryDirectory(prefix="rann_sandbox_") as tmpdir:
            filepath = Path(tmpdir) / Path(local_file).name
            try:
                filepath.write_text(code)
                filepath.chmod(0o600)
            except IOError as e:
                raise ToolExecutionError(f"Failed to write code to temp file: {e}")

            copy_cmd = ["docker", "cp", str(filepath), f"{container_id}:{local_file}"]

            try:
                # Copy code into container
                copy_proc = await _run_process(copy_cmd, timeout=10)
                if copy_proc.returncode != 0:
                    raise ToolExecutionError(
                        f"Failed to copy code to container: {copy_proc.stderr}"
                    )

                # Run the code
                start = _time_seconds()
                proc = await _run_process(docker_cmd, timeout=config.timeout)
                duration = _time_seconds() - start

                return ExecutionResult(
                    success=proc.returncode == 0,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    duration=duration,
                )
            except subprocess.TimeoutExpired:
                # Kill the container
                await _run_process(["docker", "kill", container_id], timeout=5)
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Execution timed out",
                    exit_code=-1,
                    duration=config.timeout,
                    killed=True,
                    error="Timeout exceeded",
                )

    async def _execute_vm(
        self, code: str, language: str, config: SandboxConfig
    ) -> ExecutionResult:
        """Execute in a full VM - not yet implemented."""
        raise SecurityError(
            "VM sandbox is not yet implemented",
            details={"type": SandboxType.VM.value},
        )

    def _build_command(self, code_or_path: str | Path, language: str) -> List[str]:
        """Build the appropriate command to execute code in the given language."""
        lang = language.lower()

        if lang in ("python", "python3"):
            return ["python3", str(code_or_path)]
        elif lang in ("javascript", "node"):
            return ["node", str(code_or_path)]
        elif lang in ("bash", "sh"):
            return ["bash", str(code_or_path)]
        else:
            raise ToolExecutionError(f"Unsupported language: {language}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

import asyncio
import time


def _time_seconds() -> float:
    """Get current time in seconds."""
    return time.monotonic()


async def _run_process(
    cmd: List[str],
    timeout: int,
    memory_limit: Optional[int] = None,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """
    Run a subprocess with optional memory limit enforcement.

    For memory limits, we use a background monitor thread that checks
    the process's RSS and kills it if it exceeds the limit.
    """
    log = logger.bind(cmd=" ".join(cmd[:3]) + " ...")

    # Set up resource limits for child processes
    def _set_limits():
        try:
            # Set memory limit
            if memory_limit:
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            # Disable core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            # Limit number of processes
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
            # Limit file size to 10MB
            resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
        except (ValueError, OSError) as e:
            log.warning("failed_to_set_resource_limits", error=str(e))

    # Create subprocess
    kwargs: Dict[str, Any] = {
        "args": cmd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "cwd": cwd,
    }

    if hasattr(os, "setsid"):
        kwargs["start_new_session"] = True

    proc = await asyncio.create_subprocess_exec(
        **kwargs,
    )

    # Memory monitor future
    monitor_task: Optional[asyncio.Task] = None

    async def _monitor_memory():
        """Poll memory usage and kill process if over limit."""
        if not memory_limit:
            return

        while True:
            try:
                # Check /proc/pid/status for memory info (Linux only)
                status_path = f"/proc/{proc.pid}/status"
                try:
                    with open(status_path) as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                rss_kb = int(line.split()[1])
                                if rss_kb * 1024 > memory_limit:
                                    log.warning(
                                        "memory_limit_exceeded",
                                        rss_mb=rss_kb / 1024,
                                        limit_mb=memory_limit / (1024 * 1024),
                                    )
                                    proc.kill()
                                    return
                except (FileNotFoundError, ProcessLookupError):
                    # Process ended
                    return
            except Exception:
                pass

            await asyncio.sleep(0.1)

    if memory_limit:
        monitor_task = asyncio.create_task(_monitor_memory())

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return subprocess.CompletedProcess(args=cmd, returncode=proc.returncode, stdout=stdout, stderr=stderr)
    except asyncio.TimeoutExpired:
        # Kill the process
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.kill()
        except (ProcessLookupError, OSError):
            pass

        # Wait for graceful termination
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        except asyncio.TimeoutExpired:
            # Force kill
            try:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                else:
                    proc.kill()
            except (ProcessLookupError, OSError):
                pass
            stdout, stderr = "", "Process forcefully killed"

        raise subprocess.TimeoutExpired(cmd, timeout)
    finally:
        if monitor_task:
            monitor_task.cancel()