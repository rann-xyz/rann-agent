"""
Testing and QA tools
"""

from typing import Dict, Any
import structlog
from pathlib import Path

from rann_agent.tools.registry import Tool, ToolResult

logger = structlog.get_logger()


class TestRunnerTool(Tool):
    """Run tests with various frameworks"""
    
    name = "test_runner"
    description = "Run tests (pytest, jest, go test, cargo test)"
    parameters = {
        "framework": {"type": "string", "required": True},  # pytest | jest | go | cargo | unittest
        "path": {"type": "string", "default": "."},
        "options": {"type": "array", "default": []},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, framework: str, path: str = ".", options: list = None, **kwargs) -> Dict[str, Any]:
        """Run tests"""
        
        import subprocess
        
        options = options or []
        
        try:
            if framework == "pytest":
                cmd = ["pytest", path, "-v", "--tb=short"]
                cmd.extend(options)
            
            elif framework == "jest":
                cmd = ["jest", path, "--verbose"]
                cmd.extend(options)
            
            elif framework == "go":
                cmd = ["go", "test", "-v", path]
                cmd.extend(options)
            
            elif framework == "cargo":
                cmd = ["cargo", "test", "--", "--nocapture"]
                cmd.extend(options)
            
            elif framework == "unittest":
                cmd = ["python", "-m", "unittest", "discover", path]
                cmd.extend(options)
            
            else:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Unknown framework: {framework}"
                ).to_dict()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            output = result.stdout or result.stderr
            
            return ToolResult(
                tool=self.name,
                success=result.returncode == 0,
                output=output,
                metadata={
                    "framework": framework,
                    "exit_code": result.returncode,
                    "passed": result.returncode == 0
                }
            ).to_dict()
        
        except Exception as e:
            logger.error("test_runner_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()


class LinterTool(Tool):
    """Code linting and formatting"""
    
    name = "linter"
    description = "Lint and format code (ruff, black, eslint, gofmt)"
    parameters = {
        "tool": {"type": "string", "required": True},  # ruff | black | eslint | prettier | gofmt
        "path": {"type": "string", "required": True},
        "fix": {"type": "boolean", "default": False},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, tool: str, path: str, fix: bool = False, **kwargs) -> Dict[str, Any]:
        """Run linter"""
        
        import subprocess
        
        try:
            if tool == "ruff":
                cmd = ["ruff", "check", path]
                if fix:
                    cmd.append("--fix")
            
            elif tool == "black":
                cmd = ["black", path]
                if not fix:
                    cmd.append("--check")
            
            elif tool == "eslint":
                cmd = ["eslint", path]
                if fix:
                    cmd.append("--fix")
            
            elif tool == "prettier":
                cmd = ["prettier", path]
                if fix:
                    cmd.append("--write")
                else:
                    cmd.append("--check")
            
            elif tool == "gofmt":
                cmd = ["gofmt", "-l"]
                if fix:
                    cmd.append("-w")
                cmd.append(path)
            
            else:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Unknown linter: {tool}"
                ).to_dict()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            output = result.stdout or result.stderr
            
            return ToolResult(
                tool=self.name,
                success=result.returncode == 0,
                output=output,
                metadata={
                    "linter": tool,
                    "fixed": fix,
                    "exit_code": result.returncode
                }
            ).to_dict()
        
        except Exception as e:
            logger.error("linter_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()


class BenchmarkTool(Tool):
    """Performance benchmarking"""
    
    name = "benchmark"
    description = "Run performance benchmarks and profiling"
    parameters = {
        "type": {"type": "string", "required": True},  # python | go | node | http
        "target": {"type": "string", "required": True},
        "iterations": {"type": "integer", "default": 1000},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, type: str, target: str, iterations: int = 1000, **kwargs) -> Dict[str, Any]:
        """Run benchmark"""
        
        import subprocess
        
        try:
            if type == "python":
                cmd = f"python -m timeit -n {iterations} '{target}'"
            
            elif type == "go":
                cmd = f"go test -bench={target} -benchtime={iterations}x"
            
            elif type == "node":
                cmd = f"node --prof {target}"
            
            elif type == "http":
                # Use ab (Apache Bench) or wrk
                cmd = f"ab -n {iterations} -c 10 {target}"
            
            else:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Unknown benchmark type: {type}"
                ).to_dict()
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return ToolResult(
                tool=self.name,
                success=result.returncode == 0,
                output=result.stdout or result.stderr,
                metadata={"type": type, "iterations": iterations}
            ).to_dict()
        
        except Exception as e:
            logger.error("benchmark_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
