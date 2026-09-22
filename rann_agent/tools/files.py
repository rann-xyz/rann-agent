"""
File operation tools - PATCHED FOR WORKSPACE ISOLATION
"""

from pathlib import Path
from typing import Any

import structlog

from rann_agent.tools.registry import Tool, ToolResult
from rann_agent.core.security import WorkspaceGuard, WorkspaceSecurity

logger = structlog.get_logger()


class FileReadTool(Tool):
    """Read file contents within workspace boundary."""

    name = "file_read"
    description = "Read contents of a file within workspace"
    parameters = {
        "path": {"type": "string", "required": True},
        "offset": {"type": "integer", "default": 0},
        "limit": {"type": "integer", "default": 2000},
    }

    def __init__(self, config, workspace_root: Path | None = None):
        self.config = config
        self.max_size = config.tools.files.get("max_file_size", 10485760)
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.guard = WorkspaceGuard(self.workspace_root)

    async def execute(
        self, path: str, offset: int = 0, limit: int = 2000, **kwargs
    ) -> dict[str, Any]:
        """Read file with workspace boundary enforcement."""
        try:
            # Validate path stays within workspace
            file_path = self.guard.validate_path(path)

            # Check if exists and is a file
            if not file_path.exists():
                return ToolResult(
                    tool=self.name, success=False, error=f"File not found: {path}"
                ).to_dict()

            if not file_path.is_file():
                return ToolResult(
                    tool=self.name, success=False, error=f"Not a file: {path}"
                ).to_dict()

            # Check size
            if file_path.stat().st_size > self.max_size:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"File too large (max {self.max_size} bytes)",
                ).to_dict()

            # Read file
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            # Apply offset and limit
            total_lines = len(lines)
            selected_lines = lines[offset : offset + limit]

            # Format with line numbers
            content = "\n".join(
                f"{i + offset + 1}|{line.rstrip()}" for i, line in enumerate(selected_lines)
            )

            return ToolResult(
                tool=self.name,
                success=True,
                output=content,
                metadata={
                    "total_lines": total_lines,
                    "showing_lines": len(selected_lines),
                    "offset": offset,
                },
            ).to_dict()

        except ValueError as e:
            logger.warning("workspace_violation", path=path, error=str(e))
            return ToolResult(
                tool=self.name, success=False, error=f"Workspace violation: {path}"
            ).to_dict()
        except Exception as e:
            logger.error("file_read_error", path=path, error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()


class FileWriteTool(Tool):
    """Write file contents within workspace boundary."""

    name = "write_file"
    description = "Write content to a file within workspace"
    parameters = {
        "path": {"type": "string", "required": True},
        "content": {"type": "string", "required": True},
    }

    def __init__(self, config, workspace_root: Path | None = None):
        self.config = config
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.guard = WorkspaceGuard(self.workspace_root)

    async def execute(self, path: str, content: str, **kwargs) -> dict[str, Any]:
        """Write file with workspace boundary enforcement."""
        try:
            # Validate path stays within workspace
            file_path = self.guard.validate_path(path)

            # Create parent directories within workspace
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                tool=self.name,
                success=True,
                output=f"Written {len(content)} bytes",
                metadata={"bytes": len(content), "path": str(file_path.relative_to(self.workspace_root))},
            ).to_dict()

        except ValueError as e:
            logger.warning("workspace_violation", path=path, error=str(e))
            return ToolResult(
                tool=self.name, success=False, error=f"Workspace violation: {path}"
            ).to_dict()
        except Exception as e:
            logger.error("file_write_error", path=path, error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()


class FileDeleteTool(Tool):
    """Delete file within workspace boundary."""

    name = "file_delete"
    description = "Delete a file within workspace"
    parameters = {
        "path": {"type": "string", "required": True},
    }

    def __init__(self, config, workspace_root: Path | None = None):
        self.config = config
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.guard = WorkspaceGuard(self.workspace_root)

    async def execute(self, path: str, **kwargs) -> dict[str, Any]:
        """Delete file with workspace boundary enforcement."""
        try:
            # Validate path stays within workspace
            file_path = self.guard.validate_path(path)

            if not file_path.exists():
                return ToolResult(
                    tool=self.name, success=False, error=f"File not found: {path}"
                ).to_dict()

            file_path.unlink()

            return ToolResult(
                tool=self.name,
                success=True,
                output=f"Deleted: {path}",
            ).to_dict()

        except ValueError as e:
            logger.warning("workspace_violation", path=path, error=str(e))
            return ToolResult(
                tool=self.name, success=False, error=f"Workspace violation: {path}"
            ).to_dict()
        except Exception as e:
            logger.error("file_delete_error", path=path, error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()


class FileSearchTool(Tool):
    """Search files by pattern within workspace."""

    name = "file_search"
    description = "Search files by name or content pattern within workspace"
    parameters = {
        "pattern": {"type": "string", "required": True},
        "target": {"type": "string", "default": "content"},  # content | files
        "path": {"type": "string", "default": "."},
        "limit": {"type": "integer", "default": 50},
    }

    def __init__(self, config, workspace_root: Path | None = None):
        self.config = config
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.guard = WorkspaceGuard(self.workspace_root)

    async def execute(
        self,
        pattern: str,
        target: str = "content",
        path: str = ".",
        limit: int = 50,
        **kwargs,
    ) -> dict[str, Any]:
        """Search files with workspace boundary enforcement."""
        try:
            # Validate search path stays within workspace
            search_path = self.guard.validate_path(path)

            import subprocess

            # Use find/grep with validated path only
            if target == "files":
                cmd = ["find", str(search_path), "-name", f"*{pattern}*", "-type", "f"]
            else:
                # Escape pattern for grep safety
                import shlex
                safe_pattern = shlex.quote(pattern)
                cmd = ["grep", "-r", "-l", safe_pattern, str(search_path)]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            paths = result.stdout.strip().split("\n") if result.stdout.strip() else []

            return ToolResult(
                tool=self.name,
                success=True,
                output="\n".join(paths[:limit]),
                metadata={"pattern": pattern, "target": target, "count": len(paths[:limit])},
            ).to_dict()

        except ValueError as e:
            logger.warning("workspace_violation", path=path, error=str(e))
            return ToolResult(
                tool=self.name, success=False, error=f"Workspace violation: {path}"
            ).to_dict()
        except Exception as e:
            logger.error("file_search_error", error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()