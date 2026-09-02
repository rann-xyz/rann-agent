"""
Code execution tool
"""

import asyncio
from pathlib import Path
from typing import Dict, Any
import structlog

from rann_agent.tools.registry import Tool, ToolResult

logger = structlog.get_logger()


class CodeExecutionTool(Tool):
    """Execute code in various languages"""
    
    name = "code_exec"
    description = "Execute Python, JavaScript, or shell code"
    parameters = {
        "code": {"type": "string", "required": True},
        "language": {"type": "string", "default": "python"},  # python | javascript | bash
        "timeout": {"type": "integer", "default": 300},
    }
    
    def __init__(self, config):
        self.config = config
        self.sandbox = config.tools.code_exec.get("sandbox", True)
        self.timeout = config.tools.code_exec.get("timeout", 300)
        self.allowed_languages = config.tools.code_exec.get(
            "allowed_languages",
            ["python", "javascript", "bash"]
        )
    
    async def execute(self, code: str, language: str = "python", timeout: int = None, **kwargs) -> Dict[str, Any]:
        """Execute code"""
        
        if language not in self.allowed_languages:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Language not allowed: {language}"
            ).to_dict()
        
        timeout = timeout or self.timeout
        
        try:
            logger.info("code_exec_start", language=language, lines=len(code.splitlines()))
            
            if language == "python":
                result = await self._execute_python(code, timeout)
            elif language == "javascript":
                result = await self._execute_javascript(code, timeout)
            elif language == "bash":
                result = await self._execute_bash(code, timeout)
            else:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Unsupported language: {language}"
                ).to_dict()
            
            return result
            
        except Exception as e:
            logger.error("code_exec_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
    
    async def _execute_python(self, code: str, timeout: int) -> Dict[str, Any]:
        """Execute Python code"""
        # Create temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            process = await asyncio.create_subprocess_exec(
                'python3', temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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
                    metadata={"language": "python", "exit_code": process.returncode}
                ).to_dict()
                
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Execution timed out after {timeout}s"
                ).to_dict()
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    async def _execute_javascript(self, code: str, timeout: int) -> Dict[str, Any]:
        """Execute JavaScript code with Node.js"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            process = await asyncio.create_subprocess_exec(
                'node', temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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
                    metadata={"language": "javascript", "exit_code": process.returncode}
                ).to_dict()
                
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Execution timed out after {timeout}s"
                ).to_dict()
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    async def _execute_bash(self, code: str, timeout: int) -> Dict[str, Any]:
        """Execute bash script"""
        process = await asyncio.create_subprocess_shell(
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
                metadata={"language": "bash", "exit_code": process.returncode}
            ).to_dict()
            
        except asyncio.TimeoutError:
            process.kill()
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Execution timed out after {timeout}s"
            ).to_dict()
