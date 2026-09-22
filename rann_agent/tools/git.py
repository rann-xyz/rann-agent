"""
Git operations tool - routes through ExecutionBackend for security

SECURITY: All git commands route through ExecutionBackend, not direct shell execution.
"""

import uuid
from typing import Any

import structlog

from rann_agent.tools.registry import Tool, ToolResult
from rann_agent.execution import ExecutionJob, ExecutionPolicy, get_execution_backend

logger = structlog.get_logger()

# Allowed git actions - whitelist for security
ALLOWED_ACTIONS = {"status", "add", "commit", "push", "pull", "diff", "log", "branch"}


class GitTool(Tool):
    """Git operations - routes through ExecutionBackend"""

    name = "git"
    description = "Git version control operations through ExecutionBackend"
    parameters = {
        "action": {
            "type": "string",
            "required": True,
            "enum": list(ALLOWED_ACTIONS),
        },
        "files": {"type": "array", "items": {"type": "string"}, "default": []},
        "message": {"type": "string", "default": ""},
        "branch": {"type": "string", "default": None},
        "workdir": {"type": "string", "default": "."},
    }

    def __init__(self, config):
        self.config = config

    def _build_safe_command(
        self, action: str, files: list, message: str, branch: str | None
    ) -> list[str] | None:
        """Build command as argv list (no shell interpolation).

        SECURITY: No shell=True. Returns structured argv list.
        """

        if action == "status":
            return ["git", "status", "--short"]

        elif action == "add":
            if not files:
                return None
            return ["git", "add"] + files

        elif action == "commit":
            if not message:
                return None
            return ["git", "commit", "-m", message]

        elif action == "push":
            cmd = ["git", "push"]
            if branch:
                cmd.append(branch)
            return cmd

        elif action == "pull":
            return ["git", "pull"]

        elif action == "diff":
            cmd = ["git", "diff"]
            if files:
                cmd.extend(files)
            return cmd

        elif action == "log":
            return ["git", "log", "--oneline", "-10"]

        elif action == "branch":
            if branch:
                return ["git", "checkout", "-b", branch]
            return ["git", "branch"]

        return None

    async def execute(
        self,
        action: str,
        files: list | None = None,
        message: str = "",
        branch: str | None = None,
        workdir: str = ".",
        **kwargs,
    ) -> dict[str, Any]:
        """Execute git command through ExecutionBackend

        SECURITY: No bare shell=True. Command routes through ExecutionBackend.
        """

        import uuid

        if action not in ALLOWED_ACTIONS:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Unknown git action: {action}. Allowed: {ALLOWED_ACTIONS}",
            ).to_dict()

        # Build command as argv list (no shell interpolation)
        cmd_list = self._build_safe_command(action, files or [], message, branch)
        if cmd_list is None:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Action '{action}' requires parameters (files for add, message for commit)",
            ).to_dict()

        # Route through ExecutionBackend
        run_id = f"git_{uuid.uuid4().hex[:12]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        policy = ExecutionPolicy()
        policy.resource_limits.timeout_seconds = 60

        job = ExecutionJob(
            job_id=job_id,
            user_id=kwargs.get("user_id", "system"),
            run_id=run_id,
            command=" ".join(cmd_list),  # Backend executes with proper isolation
            policy=policy,
        )

        try:
            backend = get_execution_backend()
            await backend.submit(job)
            result = await backend.get_result(job_id)

            return ToolResult(
                tool=self.name,
                success=result.success,
                output=result.stdout,
                error=result.stderr if not result.success else None,
                metadata={"action": action, "exit_code": result.exit_code},
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
            logger.error("git_error", action=action, error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()