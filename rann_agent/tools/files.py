"""
File operation tools
"""

from pathlib import Path
from typing import Dict, Any
import structlog

from rann_agent.tools.registry import Tool, ToolResult

logger = structlog.get_logger()


class FileReadTool(Tool):
    """Read file contents"""
    
    name = "read_file"
    description = "Read contents of a file"
    parameters = {
        "path": {"type": "string", "required": True},
        "offset": {"type": "integer", "default": 0},
        "limit": {"type": "integer", "default": 2000},
    }
    
    def __init__(self, config):
        self.config = config
        self.max_size = config.tools.files.get("max_file_size", 10485760)
    
    async def execute(self, path: str, offset: int = 0, limit: int = 2000, **kwargs) -> Dict[str, Any]:
        """Read file"""
        try:
            file_path = Path(path).expanduser().resolve()
            
            # Check if exists
            if not file_path.exists():
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"File not found: {path}"
                ).to_dict()
            
            # Check size
            if file_path.stat().st_size > self.max_size:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"File too large (max {self.max_size} bytes)"
                ).to_dict()
            
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Apply offset and limit
            total_lines = len(lines)
            selected_lines = lines[offset:offset + limit]
            
            # Format with line numbers
            content = "\n".join(
                f"{i + offset + 1}|{line.rstrip()}"
                for i, line in enumerate(selected_lines)
            )
            
            return ToolResult(
                tool=self.name,
                success=True,
                output=content,
                metadata={
                    "total_lines": total_lines,
                    "showing_lines": len(selected_lines),
                    "offset": offset,
                }
            ).to_dict()
            
        except Exception as e:
            logger.error("file_read_error", path=path, error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()


class FileWriteTool(Tool):
    """Write file contents"""
    
    name = "write_file"
    description = "Write content to a file"
    parameters = {
        "path": {"type": "string", "required": True},
        "content": {"type": "string", "required": True},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, path: str, content: str, **kwargs) -> Dict[str, Any]:
        """Write file"""
        try:
            file_path = Path(path).expanduser().resolve()
            
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return ToolResult(
                tool=self.name,
                success=True,
                output=f"Written {len(content)} bytes to {path}",
                metadata={"bytes": len(content), "path": str(file_path)}
            ).to_dict()
            
        except Exception as e:
            logger.error("file_write_error", path=path, error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()


class FileSearchTool(Tool):
    """Search files by pattern"""
    
    name = "search_files"
    description = "Search files by name or content pattern"
    parameters = {
        "pattern": {"type": "string", "required": True},
        "target": {"type": "string", "default": "content"},  # content | files
        "path": {"type": "string", "default": "."},
        "limit": {"type": "integer", "default": 50},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, pattern: str, target: str = "content", path: str = ".", limit: int = 50, **kwargs) -> Dict[str, Any]:
        """Search files"""
        try:
            import subprocess
            
            search_path = Path(path).expanduser().resolve()
            
            if target == "files":
                # Search filenames with find
                cmd = f"find {search_path} -name '*{pattern}*' -type f | head -n {limit}"
            else:
                # Search content with grep
                cmd = f"grep -r '{pattern}' {search_path} | head -n {limit}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return ToolResult(
                tool=self.name,
                success=True,
                output=result.stdout,
                metadata={"pattern": pattern, "target": target}
            ).to_dict()
            
        except Exception as e:
            logger.error("file_search_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
