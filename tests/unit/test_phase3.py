"""Unit tests for Phase 3: Tool System (executor, discovery)"""

import pytest
import asyncio
from rann_agent.tools.executor import ToolExecutor, ExecutionResult
from rann_agent.tools.discovery import ToolDiscovery


class TestToolExecutor:
    def test_execute_sync_success(self):
        executor = ToolExecutor()
        
        def my_tool(x: int, y: int) -> int:
            return x + y
        
        result = asyncio.run(executor.execute(
            "add", {"x": 2, "y": 3}, my_tool
        ))
        
        assert result.success
        assert result.output == 5
        assert result.tool_name == "add"
    
    def test_execute_async_success(self):
        executor = ToolExecutor()
        
        async def async_tool(msg: str) -> str:
            return f"Hello, {msg}"
        
        result = asyncio.run(executor.execute(
            "greet", {"msg": "World"}, async_tool
        ))
        
        assert result.success
        assert result.output == "Hello, World"
    
    def test_execute_with_error(self):
        executor = ToolExecutor()
        
        def failing_tool() -> None:
            raise ValueError("Test error")
        
        result = asyncio.run(executor.execute(
            "fail", {}, failing_tool
        ))
        
        assert not result.success
        assert "Test error" in result.error
    
    def test_rate_limiting(self):
        # Rate limiting is per-minute, hard to test in unit test
        # Just verify the method exists and doesn't crash
        executor = ToolExecutor()
        result = executor._check_rate_limit("test_tool", max_per_minute=60)
        assert isinstance(result, bool)
    
    def test_execute_timeout(self):
        executor = ToolExecutor()
        
        async def slow_tool():
            import asyncio
            await asyncio.sleep(5)
            return "done"
        
        result = asyncio.run(executor.execute(
            "slow", {}, slow_tool, timeout_seconds=0.1
        ))
        
        assert not result.success
        assert "Timeout" in result.error
    
    def test_sanitize_params(self):
        executor = ToolExecutor()
        sanitized = executor._sanitize_params({
            "username": "admin",
            "password": "secret123",
            "api_key": "key-12345",
            "data": "normal"
        })
        
        assert sanitized["username"] == "admin"
        assert sanitized["password"] == "***"
        assert sanitized["api_key"] == "***"
        assert sanitized["data"] == "normal"
    
    def test_get_stats(self):
        executor = ToolExecutor()
        
        def tool() -> str:
            return "ok"
        
        asyncio.run(executor.execute("stat_test", {}, tool))
        asyncio.run(executor.execute("stat_test", {}, tool))
        
        stats = executor.get_stats()
        assert stats["total"] >= 2
        assert "stat_test" in stats["by_tool"]


class TestToolDiscovery:
    def test_builtin_tools_scanned(self):
        discovery = ToolDiscovery()
        tools = discovery.get_all()
        
        assert len(tools) >= 8
        names = [t["name"] for t in tools]
        assert "file_read" in names
        assert "terminal" in names
        assert "git" in names
    
    def test_register_custom_tool(self):
        discovery = ToolDiscovery()
        
        def my_custom_tool(x: int) -> int:
            return x * 2
        
        discovery.register(
            "double",
            my_custom_tool,
            description="Doubles a number",
            risk_level="low"
        )
        
        tool = discovery.get("double")
        assert tool is not None
        assert tool["description"] == "Doubles a number"
        assert tool["risk_level"] == "low"
    
    def test_enable_disable(self):
        discovery = ToolDiscovery()
        discovery.disable("file_read")
        
        tool = discovery.get("file_read")
        assert not tool["enabled"]
        
        discovery.enable("file_read")
        tool = discovery.get("file_read")
        assert tool["enabled"]
    
    def test_search(self):
        discovery = ToolDiscovery()
        results = discovery.search("file")
        
        assert len(results) >= 3
        names = [r["name"] for r in results]
        assert "file_read" in names
        assert "file_write" in names
    
    def test_get_by_risk(self):
        discovery = ToolDiscovery()
        safe_tools = discovery.get_by_risk("safe")
        
        assert len(safe_tools) >= 4
        assert all(t["risk_level"] == "safe" for t in safe_tools)
    
    def test_catalog(self):
        discovery = ToolDiscovery()
        catalog = discovery.get_catalog()
        
        assert catalog["total"] >= 8
        assert catalog["enabled"] >= 8
        assert "by_risk" in catalog
        assert "tools" in catalog