"""
Code Execution Tool - Routes ALL code execution through ExecutionBackend

SECURITY: This tool NO LONGER executes code directly.
All execution routes through the ExecutionBackend abstraction.
"""

import asyncio
import uuid
import tempfile
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


class CodeExecTool(Tool):
    """Execute Python code through isolated execution backend."""

    name = "code_exec"
    description = "Execute Python code through sandboxed execution backend"
    parameters = {
        "code": {"type": "string", "required": True},
        "timeout": {"type": "integer", "default": 30},
        "language": {"type": "string", "default": "python"},
    }

    DEFAULT_WORKSPACE = Path.cwd()

    def __init__(self, config, session_id: str | None = None):
        self.config = config
        self.workspace_root = self.DEFAULT_WORKSPACE.resolve()
        self.guard = WorkspaceGuard(self.workspace_root)
        self.session_id = session_id

    async def execute(
        self,
        code: str,
        timeout: int | None = None,
        language: str = "python",
        **kwargs,
    ) -> dict[str, Any]:
        """Execute Python code through ExecutionBackend.

        SECURITY: Never executes directly in API process.
        Always routes through backend for isolation.
        """

        # Get server-derived user_id from session
        user_id = await get_current_user_id(self.session_id)
        if not user_id:
            return ToolResult(
                tool=self.name,
                success=False,
                error="Authentication required - no active session",
            ).to_dict()

        # Generate server-side identifiers
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        job_id = f"exec_{uuid.uuid4().hex[:12]}"
        workspace_id = f"ws_{uuid.uuid4().hex[:8]}"

        # Create execution policy
        policy = ExecutionPolicy()
        policy.resource_limits.timeout_seconds = timeout or 30

        # Create Python execution command
        if language == "python":
            # Create temp file with code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name

            command = ["python3", temp_path]
            cleanup = f"rm -f {temp_path}"
        else:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Language not supported: {language}",
            ).to_dict()

        # Create execution job
        job = ExecutionJob(
            job_id=job_id,
            user_id=user_id,
            run_id=run_id,
            workspace_id=workspace_id,
            command=" ".join(command),  # Will be executed in container
            policy=policy,
        )

        try:
            # Get execution backend
            backend = get_execution_backend()

            # Submit to backend
            await backend.submit(job)

            # Get result
            result = await backend.get_result(job_id)

            # Add cleanup to result
            output = result.stdout
            if cleanup:
                output += f"\n{cleanup}"

            return ToolResult(
                tool=self.name,
                success=result.success,
                output=output,
                error=result.stderr if not result.success else None,
                metadata={
                    "job_id": job_id,
                    "status": result.status.value,
                    "exit_code": result.exit_code,
                    "duration": result.duration_seconds,
                },
            ).to_dict()

        except RuntimeError as e:
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