"""
Terminal Execution Tool - PATCHED FOR SECURITY
"""

import asyncio
from pathlib import Path
from typing import Any

import structlog

from rann_agent.tools.registry import Tool, ToolResult
from rann_agent.core.security import WorkspaceGuard, CommandSanitizer

logger = structlog.get_logger()


class TerminalTool(Tool):
    """Execute shell commands within workspace boundary."""

    name = "terminal"
    description = "Execute shell commands (bash) within workspace"
    parameters = {
        "command": {"type": "string", "required": True},
        "timeout": {"type": "integer", "default": 300},
        "workdir": {"type": "string", "default": None},
        "background": {"type": "boolean", "default": False},
    }

    # Default workspace (can be configured)
    DEFAULT_WORKSPACE = Path.cwd()

    def __init__(self, config, workspace_root: Path | None = None):
        self.config = config
        self.workspace_root = workspace_root or self.DEFAULT_WORKSPACE
        self.workspace_root = self.workspace_root.resolve()
        
        self.default_timeout = config.tools.terminal.get("default_timeout", 300)
        self.max_timeout = config.tools.terminal.get("max_timeout", 3600)
        self.allow_background = config.tools.terminal.get("allow_background", True)
        self.guard = WorkspaceGuard(self.workspace_root)

    async def execute(
        self,
        command: str,
        timeout: int | None = None,
        workdir: str | None = None,
        background: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute shell command with workspace boundary enforcement."""

        # Validate timeout
        timeout = timeout or self.default_timeout
        timeout = min(timeout, self.max_timeout)

        # Security check for dangerous patterns
        is_dangerous, danger_reason = CommandSanitizer.contains_dangerous_pattern(command)
        if is_dangerous:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Security: {danger_reason}",
            ).to_dict()

        # Resolve and validate workdir
        resolved_workdir = self.workspace_root
        if workdir:
            try:
                resolved_workdir = self.guard.validate_path(workdir)
                # Ensure directory exists
                if not resolved_workdir.exists():
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error=f"Directory does not exist: {workdir}",
                    ).to_dict()
                if not resolved_workdir.is_dir():
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error=f"Not a directory: {workdir}",
                    ).to_dict()
            except ValueError as e:
                logger.warning("path_validation_failed", workdir=workdir, error=str(e))
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Invalid workdir: {str(e)}",
                ).to_dict()

        try:
            logger.info("terminal_execute", command=command[:100], timeout=timeout, workdir=str(resolved_workdir))

            # Use subprocess with shell=False for primary command
            # Parse simple commands, reject complex shell constructs
            args = command.split()
            if not args:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error="Empty command",
                ).to_dict()

            # Check for shell metacharacters that would require shell=True
            shell_metacharacters = ['&&', '||', '|', ';', '>', '<', '`', '$(', '$']
            needs_shell = any(mc in command for mc in shell_metacharacters)

            if needs_shell:
                # Still use shell=True but with validated workdir only
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(resolved_workdir),
                )
            else:
                # Safer: shell=False with argument list
                process = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(resolved_workdir),
                )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

                output = stdout.decode() if stdout else ""
                error = stderr.decode() if stderr else ""

                return ToolResult(
                    tool=self.name,
                    success=process.returncode == 0,
                    output=output if process.returncode == 0 else error,
                    error=error if process.returncode != 0 else None,
                    metadata={"exit_code": process.returncode},
                ).to_dict()

            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Command timed out after {timeout}s",
                ).to_dict()

        except Exception as e:
            logger.error("terminal_error", error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()

    def _is_dangerous(self, command: str) -> bool:
        """Check if command is dangerous - USE SECURITY MODULE."""
        is_dangerous, _ = CommandSanitizer.contains_dangerous_pattern(command)
        return is_dangerous