"""
Dynamic tool creation system - agent creates its own tools.
"""

from typing import Dict, Any, Callable
import ast
import inspect


class ToolFactory:
    """
    Dynamically create and load new tools.
    """
    
    def __init__(self):
        self.custom_tools = {}
    
    async def create_tool(
        self,
        name: str,
        description: str,
        code: str
    ) -> bool:
        """
        Create a new tool from code.
        
        Args:
            name: Tool name
            description: What the tool does
            code: Python function code
        """
        try:
            # Parse code
            tree = ast.parse(code)
            
            # Compile and execute
            exec_globals = {}
            exec(compile(tree, '<string>', 'exec'), exec_globals)
            
            # Find function
            for key, value in exec_globals.items():
                if callable(value) and not key.startswith('_'):
                    self.custom_tools[name] = {
                        'function': value,
                        'description': description,
                        'signature': inspect.signature(value)
                    }
                    return True
            
            return False
        except Exception as e:
            print(f"Failed to create tool: {e}")
            return False
    
    async def call_tool(self, name: str, *args, **kwargs) -> Any:
        """Call a custom tool."""
        if name not in self.custom_tools:
            raise ValueError(f"Tool {name} not found")
        
        tool = self.custom_tools[name]
        return await tool['function'](*args, **kwargs)
    
    async def list_tools(self) -> Dict[str, str]:
        """List available custom tools."""
        return {
            name: tool['description']
            for name, tool in self.custom_tools.items()
        }
    
    async def remove_tool(self, name: str) -> bool:
        """Remove a custom tool."""
        if name in self.custom_tools:
            del self.custom_tools[name]
            return True
        return False
