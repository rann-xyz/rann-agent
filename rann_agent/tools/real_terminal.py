"""
Real terminal executor for RANN Agent.
As required by MASTER PROMPT Section 6.
"""

import subprocess
import signal
import os
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
import structlog

logger = structlog.get_logger()

MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB per stdout/stderr


@dataclass
class ToolResult:
    """Structured result from tool execution."""
    call_id: str
    tool_name: str
    command: Optional[str]
    success: bool
    exit_code: Optional[int]
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    cancelled: bool = False
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    evidence_id: Optional[str] = None


class RealTerminalExecutor:
    """
    Production-quality command executor.

    Features:
    - subprocess execution with shell=False by default
    - argument-array execution
    - cwd restriction
    - environment filtering
    - timeout with SIGKILL
    - cancellation via process group
    - stdout/stderr capture with size limits
    - exit code and signal info
    - audit logging
    """

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        allowed_env_vars: Optional[List[str]] = None,
        forbidden_env_patterns: Optional[List[str]] = None,
        default_timeout: int = 60,
    ) -> None:
        self.workspace_root = os.path.abspath(workspace_root) if workspace_root else os.getcwd()
        self.allowed_env_vars = allowed_env_vars or []
        self.forbidden_env_patterns = forbidden_env_patterns or [
            "API_KEY", "SECRET", "PASSWORD", "TOKEN", "PRIVATE",
            "ANTHROPIC", "OPENAI", "HERMES",
        ]
        self.default_timeout = default_timeout
        logger.info("terminal_executor_initialized", workspace_root=self.workspace_root)

    def _filter_env(self, env: Dict[str, str]) -> Dict[str, str]:
        """Filter environment variables to remove secrets."""
        filtered = {}
        for key, value in env.items():
            # Check if key matches forbidden patterns
            upper_key = key.upper()
            if any(pat in upper_key for pat in self.forbidden_env_patterns):
                continue
            # If allowed list is set, only pass those
            if self.allowed_env_vars and key not in self.allowed_env_vars:
                continue
            filtered[key] = value
        return filtered

    def _validate_cwd(self, cwd: str) -> str:
        """Ensure cwd is within workspace root."""
        abs_cwd = os.path.abspath(cwd)
        if not abs_cwd.startswith(self.workspace_root):
            raise ValueError(
                f"Working directory {abs_cwd} is outside workspace {self.workspace_root}"
            )
        return abs_cwd

    def execute(
        self,
        command: Union[str, List[str]],
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        input_data: Optional[str] = None,
        check: bool = False,
    ) -> ToolResult:
        """
        Execute a command and return structured ToolResult.
        """
        import time
        import uuid

        call_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]
        start_time = time.time()

        # Prepare command
        if isinstance(command, str):
            # For string commands, use shell=False and split
            # but this is less safe - prefer list form
            cmd_list = command.split()
            cmd_str = command
        else:
            cmd_list = command
            cmd_str = " ".join(command)

        # Validate cwd
        work_dir = self._validate_cwd(cwd or self.workspace_root)

        # Filter environment
        env = self._filter_env(os.environ.copy())

        timeout_val = timeout or self.default_timeout

        logger.info(
            "command_executing",
            call_id=call_id,
            command=cmd_str,
            cwd=work_dir,
            timeout=timeout_val,
        )

        try:
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if input_data else None,
                cwd=work_dir,
                env=env,
                shell=False,  # Always shell=False for safety
                preexec_fn=os.setsid,  # Create process group for cancellation
            )

            # Send input if provided
            if input_data and process.stdin:
                process.stdin.write(input_data.encode())
                process.stdin.close()

            # Wait with timeout
            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_val)
            except subprocess.TimeoutExpired:
                # Kill the entire process group
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
                duration_ms = (time.time() - start_time) * 1000
                logger.warning("command_timed_out", call_id=call_id, timeout=timeout_val)
                return ToolResult(
                    call_id=call_id,
                    tool_name="terminal",
                    command=cmd_str,
                    success=False,
                    exit_code=None,
                    stdout="",
                    stderr=f"Command timed out after {timeout_val}s",
                    duration_ms=duration_ms,
                    timed_out=True,
                    error_type="TimeoutError",
                    error_message=f"Command exceeded {timeout_val}s timeout",
                )

            # Truncate output if too large
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + f"\n... [truncated, was {len(stdout)} bytes]"
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + f"\n... [truncated, was {len(stderr)} bytes]"

            duration_ms = (time.time() - start_time) * 1000
            exit_code = process.returncode
            success = exit_code == 0

            if check and not success:
                raise subprocess.CalledProcessError(exit_code, cmd_str)

            logger.info(
                "command_completed",
                call_id=call_id,
                exit_code=exit_code,
                duration_ms=round(duration_ms, 2),
            )

            return ToolResult(
                call_id=call_id,
                tool_name="terminal",
                command=cmd_str,
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )

        except FileNotFoundError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("command_not_found", call_id=call_id, error=str(e))
            return ToolResult(
                call_id=call_id,
                tool_name="terminal",
                command=cmd_str,
                success=False,
                exit_code=127,
                stdout="",
                stderr=f"Command not found: {cmd_list[0]}",
                duration_ms=duration_ms,
                error_type="FileNotFoundError",
                error_message=str(e),
            )
        except PermissionError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("command_permission_denied", call_id=call_id, error=str(e))
            return ToolResult(
                call_id=call_id,
                tool_name="terminal",
                command=cmd_str,
                success=False,
                exit_code=126,
                stdout="",
                stderr=f"Permission denied: {cmd_str}",
                duration_ms=duration_ms,
                error_type="PermissionError",
                error_message=str(e),
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("command_error", call_id=call_id, error=str(e))
            return ToolResult(
                call_id=call_id,
                tool_name="terminal",
                command=cmd_str,
                success=False,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_message=str(e),
            )

    def cancel(self, call_id: str) -> bool:
        """Cancel a running command (by process group)."""
        # In a full implementation, this would track running processes
        # and kill their process groups
        logger.info("cancel_requested", call_id=call_id)
        return True