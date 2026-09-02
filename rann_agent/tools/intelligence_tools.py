"""
AI-powered debugging and problem solving
"""

from typing import Dict, Any, List
import structlog
import re

from rann_agent.tools.registry import Tool, ToolResult

logger = structlog.get_logger()


class DebuggerTool(Tool):
    """Intelligent debugging assistant"""
    
    name = "debugger"
    description = "Analyze errors, suggest fixes, trace execution"
    parameters = {
        "action": {"type": "string", "required": True},  # analyze | trace | suggest_fix
        "error": {"type": "string", "default": ""},
        "context": {"type": "string", "default": ""},
        "language": {"type": "string", "default": "python"},
    }
    
    def __init__(self, config):
        self.config = config
        self.error_patterns = self._load_error_patterns()
    
    def _load_error_patterns(self) -> Dict[str, List[Dict]]:
        """Load common error patterns and solutions"""
        return {
            "python": [
                {
                    "pattern": r"ModuleNotFoundError: No module named '(.+)'",
                    "type": "Missing Module",
                    "fix": "pip install {module}",
                    "explanation": "The required module is not installed"
                },
                {
                    "pattern": r"IndentationError",
                    "type": "Indentation Error",
                    "fix": "Fix indentation (use 4 spaces consistently)",
                    "explanation": "Python requires consistent indentation"
                },
                {
                    "pattern": r"KeyError: '(.+)'",
                    "type": "Missing Dictionary Key",
                    "fix": "Use dict.get('{key}') or check if key exists",
                    "explanation": "Accessing non-existent dictionary key"
                },
                {
                    "pattern": r"TypeError: .+ takes (\d+) .+ but (\d+)",
                    "type": "Wrong Number of Arguments",
                    "fix": "Check function signature and pass correct arguments",
                    "explanation": "Function called with wrong number of arguments"
                },
                {
                    "pattern": r"AttributeError: .+ has no attribute '(.+)'",
                    "type": "Missing Attribute",
                    "fix": "Check if object has the attribute or method",
                    "explanation": "Trying to access non-existent attribute"
                },
            ],
            "javascript": [
                {
                    "pattern": r"ReferenceError: (.+) is not defined",
                    "type": "Undefined Variable",
                    "fix": "Declare variable before use or check spelling",
                    "explanation": "Variable used before declaration"
                },
                {
                    "pattern": r"TypeError: Cannot read property '(.+)' of undefined",
                    "type": "Undefined Property Access",
                    "fix": "Use optional chaining (?.) or check if object exists",
                    "explanation": "Accessing property of undefined object"
                },
            ]
        }
    
    async def execute(self, action: str, error: str = "", context: str = "", language: str = "python", **kwargs) -> Dict[str, Any]:
        """Execute debugging action"""
        
        try:
            if action == "analyze":
                return await self._analyze_error(error, language, context)
            
            elif action == "trace":
                return await self._trace_execution(error, context)
            
            elif action == "suggest_fix":
                return await self._suggest_fix(error, language, context)
            
            else:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Unknown action: {action}"
                ).to_dict()
        
        except Exception as e:
            logger.error("debugger_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
    
    async def _analyze_error(self, error: str, language: str, context: str) -> Dict[str, Any]:
        """Analyze error and provide insights"""
        
        patterns = self.error_patterns.get(language, [])
        
        matches = []
        for pattern_info in patterns:
            match = re.search(pattern_info["pattern"], error)
            if match:
                matches.append({
                    "type": pattern_info["type"],
                    "fix": pattern_info["fix"].format(
                        module=match.group(1) if match.groups() else "",
                        key=match.group(1) if match.groups() else ""
                    ),
                    "explanation": pattern_info["explanation"],
                    "matched": match.group(0)
                })
        
        # Format output
        output = "🔍 Error Analysis\n"
        output += "=" * 60 + "\n\n"
        output += f"Error:\n{error}\n\n"
        
        if matches:
            output += "📊 Identified Issues:\n\n"
            for i, m in enumerate(matches, 1):
                output += f"{i}. {m['type']}\n"
                output += f"   Explanation: {m['explanation']}\n"
                output += f"   💡 Fix: {m['fix']}\n\n"
        else:
            output += "⚠️  No known pattern matched. Analyzing manually...\n\n"
            output += self._generic_analysis(error, language)
        
        if context:
            output += f"\n📝 Context:\n{context}\n"
        
        return ToolResult(
            tool=self.name,
            success=True,
            output=output,
            metadata={"matches": matches, "language": language}
        ).to_dict()
    
    def _generic_analysis(self, error: str, language: str) -> str:
        """Generic error analysis"""
        suggestions = []
        
        if "timeout" in error.lower():
            suggestions.append("• Operation timed out - consider increasing timeout or optimizing performance")
        
        if "permission" in error.lower():
            suggestions.append("• Permission denied - check file/directory permissions")
        
        if "connection" in error.lower():
            suggestions.append("• Connection issue - check network, firewall, or service availability")
        
        if "memory" in error.lower():
            suggestions.append("• Memory issue - reduce data size or increase available memory")
        
        if suggestions:
            return "💡 Suggestions:\n" + "\n".join(suggestions)
        
        return "💡 Try: Check logs, verify inputs, add debug prints, or use a debugger"
    
    async def _trace_execution(self, error: str, context: str) -> Dict[str, Any]:
        """Trace execution path"""
        
        output = "🔎 Execution Trace Analysis\n"
        output += "=" * 60 + "\n\n"
        
        # Extract stack trace
        lines = error.split('\n')
        stack_frames = [line for line in lines if 'File' in line or 'line' in line]
        
        if stack_frames:
            output += "📍 Stack Trace:\n"
            for frame in stack_frames:
                output += f"  {frame}\n"
        
        output += "\n💡 Trace Analysis:\n"
        output += "• Check the last frame for immediate cause\n"
        output += "• Look for unexpected values in variables\n"
        output += "• Verify function calls are correct\n"
        
        return ToolResult(
            tool=self.name,
            success=True,
            output=output,
            metadata={"stack_frames": stack_frames}
        ).to_dict()
    
    async def _suggest_fix(self, error: str, language: str, context: str) -> Dict[str, Any]:
        """Suggest fixes for the error"""
        
        analysis = await self._analyze_error(error, language, context)
        
        output = "🛠️  Suggested Fixes\n"
        output += "=" * 60 + "\n\n"
        
        matches = analysis.get("metadata", {}).get("matches", [])
        
        if matches:
            for i, m in enumerate(matches, 1):
                output += f"Fix {i}: {m['fix']}\n\n"
        else:
            output += "General debugging steps:\n"
            output += "1. Add logging/print statements\n"
            output += "2. Check variable values\n"
            output += "3. Verify function arguments\n"
            output += "4. Test with simpler inputs\n"
            output += "5. Review recent changes\n"
        
        return ToolResult(
            tool=self.name,
            success=True,
            output=output,
            metadata=matches
        ).to_dict()


class PerformanceProfilerTool(Tool):
    """Profile and optimize performance"""
    
    name = "profiler"
    description = "Profile code performance, find bottlenecks"
    parameters = {
        "target": {"type": "string", "required": True},
        "type": {"type": "string", "default": "cpu"},  # cpu | memory | io
        "duration": {"type": "integer", "default": 10},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, target: str, type: str = "cpu", duration: int = 10, **kwargs) -> Dict[str, Any]:
        """Profile performance"""
        
        import subprocess
        
        try:
            if type == "cpu":
                # Use py-spy for Python
                cmd = f"py-spy top --duration {duration} -- python {target}"
            
            elif type == "memory":
                # Use memory_profiler
                cmd = f"python -m memory_profiler {target}"
            
            elif type == "io":
                # Use strace
                cmd = f"strace -c python {target}"
            
            else:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Unknown profile type: {type}"
                ).to_dict()
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=duration + 5
            )
            
            output = "📊 Performance Profile\n"
            output += "=" * 60 + "\n\n"
            output += result.stdout or result.stderr
            
            return ToolResult(
                tool=self.name,
                success=result.returncode == 0,
                output=output,
                metadata={"type": type, "duration": duration}
            ).to_dict()
        
        except Exception as e:
            logger.error("profiler_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()


class SecurityScannerTool(Tool):
    """Security vulnerability scanning"""
    
    name = "security_scanner"
    description = "Scan for security vulnerabilities and best practices"
    parameters = {
        "path": {"type": "string", "required": True},
        "scan_type": {"type": "string", "default": "all"},  # all | dependencies | code | secrets
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, path: str, scan_type: str = "all", **kwargs) -> Dict[str, Any]:
        """Run security scan"""
        
        import subprocess
        
        results = []
        
        try:
            if scan_type in ["all", "dependencies"]:
                # Scan dependencies
                cmd = f"safety check --json || pip-audit || true"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                results.append(("Dependencies", result.stdout or result.stderr))
            
            if scan_type in ["all", "code"]:
                # Scan code
                cmd = f"bandit -r {path} || true"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                results.append(("Code", result.stdout or result.stderr))
            
            if scan_type in ["all", "secrets"]:
                # Scan for secrets
                cmd = f"gitleaks detect --source {path} --verbose || true"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                results.append(("Secrets", result.stdout or result.stderr))
            
            output = "🔒 Security Scan Results\n"
            output += "=" * 60 + "\n\n"
            
            for scan_name, scan_result in results:
                output += f"## {scan_name}\n"
                output += scan_result[:1000]  # Limit output
                output += "\n\n"
            
            return ToolResult(
                tool=self.name,
                success=True,
                output=output,
                metadata={"scan_type": scan_type, "scans": len(results)}
            ).to_dict()
        
        except Exception as e:
            logger.error("security_scan_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
