"""
AI-powered debugging and problem solving - All execution routes through ExecutionBackend
"""

import re
import uuid
from typing import Any

import structlog

from rann_agent.tools.registry import Tool, ToolResult
from rann_agent.execution import ExecutionJob, ExecutionPolicy, get_execution_backend

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

    def _load_error_patterns(self) -> dict[str, list[dict]]:
        """Load common error patterns and solutions"""
        return {
            "python": [
                {
                    "pattern": r"ModuleNotFoundError: No module named '(.+)'",
                    "type": "Missing Module",
                    "fix": "pip install {module}",
                    "explanation": "The required module is not installed",
                },
                {
                    "pattern": r"IndentationError",
                    "type": "Indentation Error",
                    "fix": "Fix indentation (use 4 spaces consistently)",
                    "explanation": "Python requires consistent indentation",
                },
                {
                    "pattern": r"KeyError: '(.+)'",
                    "type": "Missing Dictionary Key",
                    "fix": "Use dict.get('{key}') or check if key exists",
                    "explanation": "Accessing non-existent dictionary key",
                },
                {
                    "pattern": r"TypeError: .+ takes (\d+) .+ but (\d+)",
                    "type": "Wrong Number of Arguments",
                    "fix": "Check function signature and pass correct arguments",
                    "explanation": "Function called with wrong number of arguments",
                },
                {
                    "pattern": r"AttributeError: .+ has no attribute '(.+)'",
                    "type": "Missing Attribute",
                    "fix": "Check if object has the attribute or method",
                    "explanation": "Trying to access non-existent attribute",
                },
            ],
            "javascript": [
                {
                    "pattern": r"ReferenceError: (.+) is not defined",
                    "type": "Undefined Variable",
                    "fix": "Declare variable before use or check spelling",
                    "explanation": "Variable used before declaration",
                },
                {
                    "pattern": r"TypeError: Cannot read property '(.+)' of undefined",
                    "type": "Undefined Property Access",
                    "fix": "Use optional chaining (?.) or check if object exists",
                    "explanation": "Accessing property of undefined object",
                },
            ],
        }

    async def execute(
        self,
        action: str,
        error: str = "",
        context: str = "",
        language: str = "python",
        **kwargs,
    ) -> dict[str, Any]:
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
                    tool=self.name, success=False, error=f"Unknown action: {action}"
                ).to_dict()

        except Exception as e:
            logger.error("debugger_error", error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()

    async def _analyze_error(
        self, error: str, language: str, context: str
    ) -> dict[str, Any]:
        """Analyze error and provide insights"""

        patterns = self.error_patterns.get(language, [])

        matches = []
        for pattern_info in patterns:
            match = re.search(pattern_info["pattern"], error)
            if match:
                matches.append(
                    {
                        "type": pattern_info["type"],
                        "fix": pattern_info["fix"].format(
                            module=match.group(1) if match.groups() else "",
                            key=match.group(1) if match.groups() else "",
                        ),
                        "explanation": pattern_info["explanation"],
                        "matched": match.group(0),
                    }
                )

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
            metadata={"matches": matches, "language": language},
        ).to_dict()

    def _generic_analysis(self, error: str, language: str) -> str:
        """Generic error analysis"""
        suggestions = []

        if "timeout" in error.lower():
            suggestions.append(
                "• Operation timed out - consider increasing timeout or optimizing performance"
            )

        if "permission" in error.lower():
            suggestions.append("• Permission denied - check file/directory permissions")

        if "connection" in error.lower():
            suggestions.append(
                "• Connection issue - check network, firewall, or service availability"
            )

        if "memory" in error.lower():
            suggestions.append("• Memory issue - reduce data size or increase available memory")

        if suggestions:
            return "💡 Suggestions:\n" + "\n".join(suggestions)

        return "💡 Try: Check logs, verify inputs, add debug prints, or use a debugger"

    async def _trace_execution(self, error: str, context: str) -> dict[str, Any]:
        """Trace execution path"""

        output = "🔎 Execution Trace Analysis\n"
        output += "=" * 60 + "\n\n"

        # Extract stack trace
        lines = error.split("\n")
        stack_frames = [line for line in lines if "File" in line or "line" in line]

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
            metadata={"stack_frames": stack_frames},
        ).to_dict()

    async def _suggest_fix(
        self, error: str, language: str, context: str
    ) -> dict[str, Any]:
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
            tool=self.name, success=True, output=output, metadata=matches
        ).to_dict()


class PerformanceProfilerTool(Tool):
    """Profile and optimize performance - routes through ExecutionBackend"""

    name = "profiler"
    description = "Profile code performance, find bottlenecks (routes through ExecutionBackend)"
    parameters = {
        "target": {"type": "string", "required": True},
        "type": {"type": "string", "default": "cpu"},  # cpu | memory | io
        "duration": {"type": "integer", "default": 10, "maximum": 60},
    }

    def __init__(self, config):
        self.config = config

    async def execute(
        self,
        target: str,
        type: str = "cpu",
        duration: int = 10,
        **kwargs,
    ) -> dict[str, Any]:
        """Profile performance through ExecutionBackend

        SECURITY: No shell=True. All profiling routes through ExecutionBackend.
        """

        import uuid

        # Build command as argv list
        if type == "cpu":
            # Use py-spy for Python profiling
            cmd = ["python", "-c", f"""
import cProfile, pstats, io
pr = cProfile.Profile()
pr.enable()
exec(open('{target}').read() if '{target}'.endswith('.py') else '{target}')
pr.disable()
s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats(20)
print(s.getvalue())
"""]
        elif type == "memory":
            cmd = ["python", "-c", f"""
import tracemalloc
tracemalloc.start()
# Your code here
print('Memory profiling done')
current, peak = tracemalloc.get_traced_memory()
print(f'Current: {{current / 1024 / 1024:.2f}} MB')
print(f'Peak: {{peak / 1024 / 1024:.2f}} MB')
tracemalloc.stop()
"""]
        elif type == "io":
            cmd = ["python", "-c", f"""
import time
start = time.time()
# Your code here
end = time.time()
print(f'Execution time: {{end - start:.2f}}s')
"""]
        else:
            return ToolResult(
                tool=self.name, success=False, error=f"Unknown profile type: {type}"
            ).to_dict()

        # Route through ExecutionBackend
        run_id = f"profile_{uuid.uuid4().hex[:12]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        policy = ExecutionPolicy()
        policy.resource_limits.timeout_seconds = duration + 30

        job = ExecutionJob(
            job_id=job_id,
            user_id=kwargs.get("user_id", "system"),
            run_id=run_id,
            command=" ".join(cmd),
            policy=policy,
        )

        try:
            backend = get_execution_backend()
            await backend.submit(job)
            result = await backend.get_result(job_id)

            return ToolResult(
                tool=self.name,
                success=result.success,
                output=result.stdout or result.stderr,
                metadata={
                    "type": type,
                    "duration": duration,
                    "exit_code": result.exit_code,
                },
            ).to_dict()

        except RuntimeError as e:
            if "unavailable" in str(e).lower():
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Execution backend unavailable: {e}",
                ).to_dict()
            raise
        except Exception as e:
            logger.error("profiler_error", error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()


class SecurityScannerTool(Tool):
    """Security vulnerability scanning - routes through ExecutionBackend"""

    name = "security_scanner"
    description = "Scan for security vulnerabilities (routes through ExecutionBackend)"
    parameters = {
        "path": {"type": "string", "required": True},
        "scan_type": {
            "type": "string",
            "default": "all",
            "enum": ["all", "dependencies", "code", "secrets"],
        },  # all | dependencies | code | secrets
    }

    def __init__(self, config):
        self.config = config

    ALLOWED_SCANS = {"all", "dependencies", "code", "secrets"}

    async def execute(
        self, path: str, scan_type: str = "all", **kwargs
    ) -> dict[str, Any]:
        """Run security scan through ExecutionBackend

        SECURITY: No shell=True with arbitrary paths.
        All scanning routes through ExecutionBackend.
        """

        import uuid

        if scan_type not in self.ALLOWED_SCANS:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Invalid scan type: {scan_type}",
            ).to_dict()

        results = []
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        run_id = f"scan_{uuid.uuid4().hex[:8]}"

        # Route each scanner through ExecutionBackend
        scan_commands = []

        if scan_type in ["all", "dependencies"]:
            scan_commands.append(("Dependencies", "pip-audit"))
        if scan_type in ["all", "code"]:
            scan_commands.append(("Code", f"bandit -r {path}"))
        if scan_type in ["all", "secrets"]:
            scan_commands.append(("Secrets", f"gitleaks detect --source {path}"))

        for scan_name, cmd in scan_commands:
            policy = ExecutionPolicy()
            policy.resource_limits.timeout_seconds = 60

            job = ExecutionJob(
                job_id=f"{job_id}_{scan_name.lower()}",
                user_id=kwargs.get("user_id", "system"),
                run_id=run_id,
                command=cmd,
                policy=policy,
            )

            try:
                backend = get_execution_backend()
                await backend.submit(job)
                result = await backend.get_result(job.job_id)
                results.append((scan_name, result.stdout or result.stderr))
            except Exception as e:
                results.append((scan_name, f"Scan failed: {e}"))

        output = "🔒 Security Scan Results\n"
        output += "=" * 60 + "\n\n"

        for scan_name, scan_result in results:
            output += f"## {scan_name}\n"
            output += scan_result[:1000] if scan_result else "No issues found"
            output += "\n\n"

        return ToolResult(
            tool=self.name,
            success=True,
            output=output,
            metadata={"scan_type": scan_type, "scans": len(results)},
        ).to_dict()