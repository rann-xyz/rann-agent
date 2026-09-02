"""
Tool registry and execution system
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import structlog

logger = structlog.get_logger()


class Tool(ABC):
    """Base class for all tools"""
    
    name: str = "base_tool"
    description: str = "Base tool"
    parameters: Dict[str, Any] = {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool
        
        Returns:
            Dict with keys: success, output, error, metadata
        """
        pass
    
    def validate_parameters(self, **kwargs) -> bool:
        """Validate input parameters"""
        for param, spec in self.parameters.items():
            if spec.get("required", False) and param not in kwargs:
                raise ValueError(f"Missing required parameter: {param}")
        return True


class ToolResult:
    """Standardized tool result"""
    
    def __init__(
        self,
        tool: str,
        success: bool,
        output: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        self.tool = tool
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


class ToolRegistry:
    """
    Central registry for all tools
    """
    
    def __init__(self, config):
        self.config = config
        self.tools: Dict[str, Tool] = {}
        
        # Register built-in tools
        self._register_builtin_tools()
        
        logger.info("tool_registry_init", tools=len(self.tools))
    
    def _register_builtin_tools(self):
        """Register all built-in tools"""
        from rann_agent.tools.terminal import TerminalTool
        from rann_agent.tools.files import FileReadTool, FileWriteTool, FileSearchTool
        from rann_agent.tools.web import WebSearchTool, WebExtractTool
        from rann_agent.tools.code_exec import CodeExecutionTool
        from rann_agent.tools.git import GitTool
        
        # Register each tool
        for tool_class in [
            TerminalTool,
            FileReadTool,
            FileWriteTool,
            FileSearchTool,
            WebSearchTool,
            WebExtractTool,
            CodeExecutionTool,
            GitTool,
        ]:
            tool = tool_class(self.config)
            self.tools[tool.name] = tool
    
    def register(self, tool: Tool):
        """Register a custom tool"""
        self.tools[tool.name] = tool
        logger.info("tool_registered", name=tool.name)
    
    def get(self, name: str) -> Optional[Tool]:
        """Get tool by name"""
        return self.tools.get(name)
    
    def get_enabled(self) -> List[Tool]:
        """Get list of enabled tools"""
        enabled_names = self.config.tools.enabled
        return [
            tool for name, tool in self.tools.items()
            if name in enabled_names
        ]
    
    async def execute(self, name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name
        
        Args:
            name: Tool name
            parameters: Tool parameters
            
        Returns:
            Tool result dict
        """
        tool = self.get(name)
        if not tool:
            return ToolResult(
                tool=name,
                success=False,
                error=f"Tool not found: {name}"
            ).to_dict()
        
        # Check if tool is enabled
        if name not in self.config.tools.enabled:
            return ToolResult(
                tool=name,
                success=False,
                error=f"Tool not enabled: {name}"
            ).to_dict()
        
        try:
            # Validate parameters
            tool.validate_parameters(**parameters)
            
            # Execute
            logger.debug("tool_execute_start", tool=name, params=parameters)
            result = await tool.execute(**parameters)
            logger.debug("tool_execute_complete", tool=name, success=result.get("success"))
            
            return result
            
        except Exception as e:
            logger.error("tool_execute_failed", tool=name, error=str(e))
            return ToolResult(
                tool=name,
                success=False,
                error=str(e)
            ).to_dict()
    
    def list_tools(self) -> List[Dict[str, str]]:
        """List all available tools"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "enabled": tool.name in self.config.tools.enabled,
            }
            for tool in self.tools.values()
        ]
