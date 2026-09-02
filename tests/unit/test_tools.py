"""
Unit tests for Tool Registry
"""

import pytest
from unittest.mock import Mock, AsyncMock
from rann_agent.tools.registry import Tool, ToolResult, ToolRegistry
from rann_agent.core.config import Config


class MockTool(Tool):
    """Mock tool for testing"""
    name = "mock_tool"
    description = "A mock tool"
    parameters = {
        "input": {"type": "string", "required": True},
        "optional": {"type": "string", "default": "default_value"},
    }
    
    async def execute(self, input: str, optional: str = "default", **kwargs):
        return ToolResult(
            tool=self.name,
            success=True,
            output=f"Processed: {input}, {optional}",
        ).to_dict()


class FailingTool(Tool):
    """Tool that always fails"""
    name = "failing_tool"
    description = "Always fails"
    parameters = {}
    
    async def execute(self, **kwargs):
        raise Exception("Tool failed")


class TestToolResult:
    """Test ToolResult class"""
    
    def test_tool_result_success(self):
        """Test successful tool result"""
        result = ToolResult(
            tool="test",
            success=True,
            output="output data",
        )
        assert result.success is True
        assert result.output == "output data"
        assert result.error is None
    
    def test_tool_result_failure(self):
        """Test failed tool result"""
        result = ToolResult(
            tool="test",
            success=False,
            error="error message",
        )
        assert result.success is False
        assert result.error == "error message"
    
    def test_tool_result_to_dict(self):
        """Test converting result to dict"""
        result = ToolResult(
            tool="test",
            success=True,
            output="data",
            metadata={"key": "value"},
        )
        result_dict = result.to_dict()
        
        assert result_dict["tool"] == "test"
        assert result_dict["success"] is True
        assert result_dict["output"] == "data"
        assert result_dict["metadata"]["key"] == "value"


class TestToolRegistry:
    """Test ToolRegistry"""
    
    def test_registry_initialization(self):
        """Test registry initializes with built-in tools"""
        config = Config()
        registry = ToolRegistry(config)
        
        assert len(registry.tools) > 0
        assert "terminal" in registry.tools
        assert "read_file" in registry.tools
    
    def test_register_custom_tool(self):
        """Test registering custom tool"""
        config = Config()
        registry = ToolRegistry(config)
        
        mock_tool = MockTool(config)
        registry.register(mock_tool)
        
        assert "mock_tool" in registry.tools
        assert registry.get("mock_tool") == mock_tool
    
    def test_get_enabled_tools(self):
        """Test getting enabled tools"""
        config = Config()
        config.tools.enabled = ["terminal", "read_file"]
        registry = ToolRegistry(config)
        
        enabled = registry.get_enabled()
        enabled_names = [t.name for t in enabled]
        
        assert "terminal" in enabled_names
        assert "read_file" in enabled_names
    
    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test executing a tool successfully"""
        config = Config()
        registry = ToolRegistry(config)
        
        mock_tool = MockTool(config)
        registry.register(mock_tool)
        config.tools.enabled.append("mock_tool")
        
        result = await registry.execute("mock_tool", {"input": "test"})
        
        assert result["success"] is True
        assert "Processed: test" in result["output"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test executing non-existent tool"""
        config = Config()
        registry = ToolRegistry(config)
        
        result = await registry.execute("nonexistent", {})
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_enabled(self):
        """Test executing disabled tool"""
        config = Config()
        config.tools.enabled = []
        registry = ToolRegistry(config)
        
        mock_tool = MockTool(config)
        registry.register(mock_tool)
        
        result = await registry.execute("mock_tool", {"input": "test"})
        
        assert result["success"] is False
        assert "not enabled" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self):
        """Test tool execution that raises error"""
        config = Config()
        registry = ToolRegistry(config)
        
        failing_tool = FailingTool(config)
        registry.register(failing_tool)
        config.tools.enabled.append("failing_tool")
        
        result = await registry.execute("failing_tool", {})
        
        assert result["success"] is False
        assert "Tool failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_missing_required_param(self):
        """Test tool execution with missing required parameter"""
        config = Config()
        registry = ToolRegistry(config)
        
        mock_tool = MockTool(config)
        registry.register(mock_tool)
        config.tools.enabled.append("mock_tool")
        
        result = await registry.execute("mock_tool", {})  # Missing 'input'
        
        assert result["success"] is False
        assert "required parameter" in result["error"].lower()
    
    def test_list_tools(self):
        """Test listing all tools"""
        config = Config()
        registry = ToolRegistry(config)
        
        tools_list = registry.list_tools()
        
        assert len(tools_list) > 0
        assert all("name" in t for t in tools_list)
        assert all("description" in t for t in tools_list)
        assert all("enabled" in t for t in tools_list)


class TestToolBase:
    """Test Tool base class"""
    
    def test_tool_validation_success(self):
        """Test parameter validation succeeds"""
        config = Config()
        tool = MockTool(config)
        
        assert tool.validate_parameters(input="test") is True
    
    def test_tool_validation_missing_required(self):
        """Test validation fails with missing required param"""
        config = Config()
        tool = MockTool(config)
        
        with pytest.raises(ValueError, match="Missing required parameter"):
            tool.validate_parameters()  # Missing 'input'
