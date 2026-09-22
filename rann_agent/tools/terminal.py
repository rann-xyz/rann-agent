"""
Terminal Execution Tool - Routes ALL execution through ExecutionBackend

SECURITY: This tool NO LONGER executes commands directly.
All execution routes through the ExecutionBackend abstraction.
"""

import asyncio
import uuid
from pathlib import Path
from typing import Any

import structlog

from rann_agent.tools.registry import Tool, ToolResult
from rann_agent.core.security import WorkspaceGuard
from rann_agent.execution import (
    ExecutionJob,
    ExecutionPolicy,
    ExecutionStatus,
    get_execution_backend,
)
from rann_agent.auth.session import get_current_user_id

logger = structlog.get_logger()


class TerminalTool(Tool):
    """Execute shell commands through isolated execution backend."""

    name = "terminal"
    description = "Execute shell commands (bash) within workspace - routes through ExecutionBackend"
    parameters = {
        "command": {"type": "string", "required": True},
        "timeout": {"type": "integer", "default": 60},
        "background": {"type": "boolean", "default": False},
    }

    DEFAULT_WORKSPACE = Path.cwd()

    def __init__(self, config, session_id: str | None = None):
        self.config = config
        self.workspace_root = self.DEFAULT_WORKSPACE.resolve()
        self.guard = WorkspaceGuard(self.workspace_root)
        self.session_id = session_id  # Server-derived session ID

    async def execute(
        self,
        command: str,
        timeout: int | None = None,
        background: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute shell command through ExecutionBackend.

        SECURITY: Never executes directly in API process.
        Always routes through backend for isolation.
        """

        # Get server-derived user_id from session (NOT from client)
        user_id = await get_current_user_id(self.session_id)
        if not user_id:
            return ToolResult(
                tool=self.name,
                success=False,
                error="Authentication required - no active session",
            ).to_dict()

        # Validate workspace boundary
        try:
            validated_path = self.guard.validate_path(str(self.workspace_root))
        except ValueError as e:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Invalid workspace: {e}",
            ).to_dict()

        # Generate server-side run_id
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        workspace_id = f"ws_{uuid.uuid4().hex[:8]}"

        # Create execution job with server-derived identity
        policy = ExecutionPolicy()
        policy.resource_limits.timeout_seconds = timeout or 60

        job = ExecutionJob(
            job_id=job_id,
            user_id=user_id,  # SERVER-DERIVED from session
            run_id=run_id,    # SERVER-GENERATED
            workspace_id=workspace_id,
            command=command,  # Still needs validation but routed through backend
            policy=policy,
        )

        try:
            # Get execution backend - will fail closed if container unavailable
            backend = get_execution_backend()

            # Submit to backend (not direct execution!)
            await backend.submit(job)

            # Wait for completion
            result = await backend.get_result(job_id)

            return ToolResult(
                tool=self.name,
                success=result.success,
                output=result.stdout,
                error=result.stderr if not result.success else None,
                metadata={
                    "job_id": job_id,
                    "status": result.status.value,
                    "exit_code": result.exit_code,
                    "duration": result.duration_seconds,
                },
            ).to_dict()

        except RuntimeError as e:
            # Fail closed - backend unavailable
            if "unavailable" in str(e).lower():
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Execution backend unavailable: {e}",
                ).to_dict()
            raise
        except Exception as e:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Execution failed: {e}",
            ).to_dict()

    def _is_safe_command(self, command: str) -> tuple[bool, str]:
        """Validate command is safe to execute.

        Note: Final safety check happens in ContainerExecutionBackend.
        """
        # Block obviously dangerous patterns
        dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd"]
        for pattern in dangerous:
            if pattern in command:
                return False, f"Blocked dangerous pattern: {pattern}"
        return True, "ok"