"""
Terminal execution tool
"""

import asyncio
import shlex
from typing import Dict, Any
import structlog

from rann_agent.tools.registry import Tool, ToolResult

logger = structlog.get_logger()


class TerminalTool(Tool):
    """Execute shell commands"""
    
    name = "terminal"
    description = "Execute shell commands (bash)"
    parameters = {
        "command": {"type": "string", "required": True},
        "timeout": {"type": "integer", "default": 300},
        "workdir": {"type": "string", "default": None},
        "background": {"type": "boolean", "default": False},
    }
    
    def __init__(self, config):
        self.config = config
        self.default_timeout = config.tools.terminal.get("default_timeout", 300)
        self.max_timeout = config.tools.terminal.get("max_timeout", 3600)
        self.allow_background = config.tools.terminal.get("allow_background", True)
    
    async def execute(self, command: str, timeout: int = None, workdir: str = None, background: bool = False, **kwargs) -> Dict[str, Any]:
        """Execute shell command"""
        
        # Validate timeout
        timeout = timeout or self.default_timeout
        if timeout > self.max_timeout:
            timeout = self.max_timeout
        
        # Safety check for dangerous commands
        if self._is_dangerous(command):
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Dangerous command requires confirmation: {command}"
            ).to_dict()
        
        try:
            logger.info("terminal_execute", command=command[:100], timeout=timeout)
            
            if background and self.allow_background:
                # Background execution
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=workdir,
                )
                return ToolResult(
                    tool=self.name,
                    success=True,
                    output=f"Background process started (PID: {process.pid})",
                    metadata={"pid": process.pid, "background": True}
                ).to_dict()
            
            else:
                # Foreground execution
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=workdir,
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=timeout
                    )
                    
                    output = stdout.decode() if stdout else ""
                    error = stderr.decode() if stderr else ""
                    
                    return ToolResult(
                        tool=self.name,
                        success=process.returncode == 0,
                        output=output if process.returncode == 0 else error,
                        error=error if process.returncode != 0 else None,
                        metadata={"exit_code": process.returncode}
                    ).to_dict()
                    
                except asyncio.TimeoutError:
                    process.kill()
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error=f"Command timed out after {timeout}s"
                    ).to_dict()
        
        except Exception as e:
            logger.error("terminal_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
    
    def _is_dangerous(self, command: str) -> bool:
        """Check if command is dangerous"""
        dangerous_patterns = self.config.tools.terminal.get(
            "dangerous_commands_require_confirmation",
            ["rm -rf", "dd if=", "mkfs", "> /dev/sd"]
        )
        return any(pattern in command for pattern in dangerous_patterns)
