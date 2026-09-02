"""
Plugin system for extensibility.
"""

from typing import Dict, Any, Callable, List
import importlib
import inspect


class PluginManager:
    """
    Dynamic plugin loading and management.
    """
    
    def __init__(self):
        self.plugins = {}
        self.hooks = {}
    
    async def load_plugin(self, plugin_path: str) -> bool:
        """Load plugin from path."""
        try:
            module = importlib.import_module(plugin_path)
            
            # Find plugin class
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if hasattr(obj, 'plugin_name'):
                    plugin_instance = obj()
                    self.plugins[plugin_instance.plugin_name] = plugin_instance
                    
                    # Register hooks
                    if hasattr(plugin_instance, 'register_hooks'):
                        await plugin_instance.register_hooks(self)
                    
                    return True
            
            return False
        except Exception as e:
            print(f"Failed to load plugin: {e}")
            return False
    
    async def register_hook(self, hook_name: str, callback: Callable):
        """Register a hook callback."""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        
        self.hooks[hook_name].append(callback)
    
    async def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Execute all callbacks for a hook."""
        if hook_name not in self.hooks:
            return []
        
        results = []
        for callback in self.hooks[hook_name]:
            try:
                result = await callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"Hook execution failed: {e}")
        
        return results
    
    async def get_plugin(self, name: str) -> Any:
        """Get plugin by name."""
        return self.plugins.get(name)
    
    async def list_plugins(self) -> List[str]:
        """List loaded plugins."""
        return list(self.plugins.keys())
