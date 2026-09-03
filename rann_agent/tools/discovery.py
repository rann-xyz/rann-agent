"""
Tool Discovery

Discovers available tools dynamically.
As required by MASTER PROMPT Section 19.
"""

from typing import Dict, List, Optional, Any, Callable
import structlog

logger = structlog.get_logger()


class ToolDiscovery:
    """
    Discovers and catalogs available tools.
    """
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._log = structlog.get_logger().bind(component="tool_discovery")
        self._scan_builtin_tools()
    
    def _scan_builtin_tools(self) -> None:
        """Scan and register built-in tools"""
        from rann_agent.tools.files import FileReadTool, FileWriteTool, FileSearchTool
        from rann_agent.tools.terminal import TerminalTool
        from rann_agent.tools.git import GitTool
        from rann_agent.tools.web import WebSearchTool, WebExtractTool
        from rann_agent.tools.code_exec import CodeExecutionTool
        
        builtin = [
            ("file_read", FileReadTool, "safe", "Read files from disk"),
            ("file_write", FileWriteTool, "low", "Write files to disk"),
            ("file_search", FileSearchTool, "safe", "Search files by pattern"),
            ("terminal", TerminalTool, "medium", "Execute shell commands"),
            ("git", GitTool, "low", "Git version control"),
            ("web_search", WebSearchTool, "safe", "Search the web"),
            ("web_extract", WebExtractTool, "safe", "Extract content from URLs"),
            ("code_execution", CodeExecutionTool, "high", "Execute code in sandbox"),
        ]
        
        for name, cls, risk, desc in builtin:
            self._tools[name] = {
                "name": name,
                "class": cls,
                "risk_level": risk,
                "description": desc,
                "enabled": True
            }
    
    def register(
        self,
        name: str,
        func: Callable,
        description: str = "",
        risk_level: str = "unknown",
        parameters: Optional[Dict[str, Any]] = None,
        enabled: bool = True
    ) -> None:
        """Register a custom tool"""
        self._tools[name] = {
            "name": name,
            "func": func,
            "description": description,
            "risk_level": risk_level,
            "parameters": parameters or {},
            "enabled": enabled
        }
        self._log.info("tool_registered", name=name, risk=risk_level)
    
    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)
    
    def get_all(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.get("enabled", True)]
        return tools
    
    def get_by_risk(self, risk_level: str) -> List[Dict[str, Any]]:
        return [t for t in self._tools.values() if t.get("risk_level") == risk_level]
    
    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        # Simple category matching
        return [t for t in self._tools.values() if category in t.get("name", "")]
    
    def enable(self, name: str) -> bool:
        if name in self._tools:
            self._tools[name]["enabled"] = True
            return True
        return False
    
    def disable(self, name: str) -> bool:
        if name in self._tools:
            self._tools[name]["enabled"] = False
            return True
        return False
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search tools by name or description"""
        query = query.lower()
        return [
            t for t in self._tools.values()
            if query in t.get("name", "").lower() or query in t.get("description", "").lower()
        ]
    
    def get_catalog(self) -> Dict[str, Any]:
        return {
            "total": len(self._tools),
            "enabled": len([t for t in self._tools.values() if t.get("enabled")]),
            "by_risk": {
                risk: len([t for t in self._tools.values() if t.get("risk_level") == risk])
                for risk in ["safe", "low", "medium", "high", "critical", "unknown"]
            },
            "tools": [
                {
                    "name": t["name"],
                    "risk_level": t.get("risk_level"),
                    "description": t.get("description"),
                    "enabled": t.get("enabled", True)
                }
                for t in self._tools.values()
            ]
        }