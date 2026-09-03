"""
Tool Executor

Executes tools with proper isolation, timeout, and error handling.
As required by MASTER PROMPT Section 17.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class ExecutionResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0
    tool_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    sandbox_used: bool = False
    risk_level: str = "unknown"


class ToolExecutor:
    """
    Executes tools with isolation and safety checks.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._log = structlog.get_logger().bind(component="tool_executor")
        self._execution_history: list[ExecutionResult] = []
        self._rate_limiter: Dict[str, list] = {}
    
    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        tool_func: Callable,
        sandbox_type: str = "none",
        timeout_seconds: float = 60,
        risk_level: str = "low"
    ) -> ExecutionResult:
        """Execute a tool with proper handling"""
        start = datetime.now()
        
        # Check rate limit
        if not self._check_rate_limit(tool_name):
            return ExecutionResult(
                success=False,
                error="Rate limit exceeded",
                tool_name=tool_name,
                parameters=parameters,
                risk_level=risk_level
            )
        
        # Execute with timeout
        try:
            if asyncio.iscoroutinefunction(tool_func):
                result = await asyncio.wait_for(tool_func(**parameters), timeout=timeout_seconds)
            else:
                result = tool_func(**parameters)
            
            execution_time = (datetime.now() - start).total_seconds() * 1000
            
            exec_result = ExecutionResult(
                success=True,
                output=result,
                execution_time_ms=execution_time,
                tool_name=tool_name,
                parameters=self._sanitize_params(parameters),
                sandbox_used=sandbox_type != "none",
                risk_level=risk_level
            )
            
            self._execution_history.append(exec_result)
            self._record_execution(tool_name)
            
            return exec_result
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                error=f"Timeout after {timeout_seconds}s",
                execution_time_ms=timeout_seconds * 1000,
                tool_name=tool_name,
                parameters=self._sanitize_params(parameters),
                risk_level=risk_level
            )
        except Exception as e:
            execution_time = (datetime.now() - start).total_seconds() * 1000
            self._log.error("tool_execution_failed", tool=tool_name, error=str(e))
            
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                tool_name=tool_name,
                parameters=self._sanitize_params(parameters),
                risk_level=risk_level
            )
    
    def _check_rate_limit(self, tool_name: str, max_per_minute: int = 60) -> bool:
        now = datetime.now()
        if tool_name not in self._rate_limiter:
            self._rate_limiter[tool_name] = []
        
        # Clean old entries
        self._rate_limiter[tool_name] = [
            t for t in self._rate_limiter[tool_name]
            if (now - t).total_seconds() < 60
        ]
        
        if len(self._rate_limiter[tool_name]) >= max_per_minute:
            return False
        
        return True
    
    def _record_execution(self, tool_name: str) -> None:
        if tool_name not in self._rate_limiter:
            self._rate_limiter[tool_name] = []
        self._rate_limiter[tool_name].append(datetime.now())
    
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive values from parameters for logging"""
        sensitive_keys = {"password", "token", "api_key", "secret", "auth"}
        return {
            k: "***" if any(s in k.lower() for s in sensitive_keys) else v
            for k, v in params.items()
        }
    
    def get_history(self, limit: int = 100) -> list[ExecutionResult]:
        return self._execution_history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        if not self._execution_history:
            return {"total": 0}
        
        total = len(self._execution_history)
        successful = sum(1 for r in self._execution_history if r.success)
        failed = total - successful
        avg_time = sum(r.execution_time_ms for r in self._execution_history) / total
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "avg_execution_ms": avg_time,
            "by_tool": self._get_stats_by_tool()
        }
    
    def _get_stats_by_tool(self) -> Dict[str, Dict[str, Any]]:
        stats: Dict[str, Dict[str, Any]] = {}
        for r in self._execution_history:
            if r.tool_name not in stats:
                stats[r.tool_name] = {"total": 0, "success": 0, "fail": 0}
            stats[r.tool_name]["total"] += 1
            if r.success:
                stats[r.tool_name]["success"] += 1
            else:
                stats[r.tool_name]["fail"] += 1
        return stats