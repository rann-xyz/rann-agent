"""
Testing and QA tools - All execution routes through ExecutionBackend
"""

import uuid
from typing import Any

import structlog

from rann_agent.tools.registry import Tool, ToolResult
from rann_agent.execution import ExecutionJob, ExecutionPolicy, get_execution_backend

logger = structlog.get_logger()

# Allowed test frameworks - no arbitrary execution
ALLOWED_TEST_FRAMEWORKS = {"pytest", "jest", "go", "cargo", "unittest"}

# Allowed linters - no arbitrary execution
ALLOWED_LINTERS = {"ruff", "black", "eslint", "prettier", "gofmt"}


class TestRunnerTool(Tool):
    """Run tests with various frameworks - routes through ExecutionBackend"""

    name = "test_runner"
    description = "Run tests (pytest, jest, go test, cargo test) through ExecutionBackend"
    parameters = {
        "framework": {
            "type": "string",
            "required": True,
            "enum": list(ALLOWED_TEST_FRAMEWORKS),  # Restrict to allowlist
        },
        "path": {"type": "string", "default": "."},
        "options": {"type": "array", "default": []},
    }

    def __init__(self, config):
        self.config = config

    async def execute(
        self,
        framework: str,
        path: str = ".",
        options: list | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Run tests through ExecutionBackend

        SECURITY: No shell=True, no arbitrary command interpolation.
        Uses structured argv execution through backend.
        """

        if framework not in ALLOWED_TEST_FRAMEWORKS:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Unknown framework: {framework}. Allowed: {ALLOWED_TEST_FRAMEWORKS}",
            ).to_dict()

        options = options or []

        # Build command as argv list (shell=False equivalent)
        if framework == "pytest":
            cmd = ["pytest", path, "-v", "--tb=short"] + options
        elif framework == "jest":
            cmd = ["npx", "jest", path, "--verbose"] + options
        elif framework == "go":
            cmd = ["go", "test", "-v", path] + options
        elif framework == "cargo":
            cmd = ["cargo", "test", "--", "--nocapture"] + options
        elif framework == "unittest":
            cmd = ["python", "-m", "unittest", "discover", path] + options

        # Route through ExecutionBackend
        run_id = f"test_{uuid.uuid4().hex[:12]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        policy = ExecutionPolicy()
        policy.resource_limits.timeout_seconds = 300  # 5 minute default

        job = ExecutionJob(
            job_id=job_id,
            user_id=kwargs.get("user_id", "system"),
            run_id=run_id,
            command=" ".join(cmd),  # Backend will use shell=False with structured args
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
                    "framework": framework,
                    "exit_code": result.exit_code,
                    "passed": result.success,
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
            logger.error("test_runner_error", error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()


class LinterTool(Tool):
    """Code linting and formatting - routes through ExecutionBackend"""

    name = "linter"
    description = "Lint and format code (ruff, black, eslint, gofmt)"
    parameters = {
        "tool": {
            "type": "string",
            "required": True,
            "enum": list(ALLOWED_LINTERS),
        },
        "path": {"type": "string", "required": True},
        "fix": {"type": "boolean", "default": False},
    }

    def __init__(self, config):
        self.config = config

    async def execute(
        self, tool: str, path: str, fix: bool = False, **kwargs
    ) -> dict[str, Any]:
        """Run linter through ExecutionBackend

        SECURITY: Restricted to allowlist of tools.
        Shell string interpolation removed.
        """

        if tool not in ALLOWED_LINTERS:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Unknown linter: {tool}. Allowed: {ALLOWED_LINTERS}",
            ).to_dict()

        # Build command as argv list
        if tool == "ruff":
            cmd = ["ruff", "check", path]
            if fix:
                cmd.append("--fix")
        elif tool == "black":
            if not fix:
                cmd = ["black", path, "--check"]
            else:
                cmd = ["black", path]
        elif tool == "eslint":
            cmd = ["npx", "eslint", path]
            if fix:
                cmd.append("--fix")
        elif tool == "prettier":
            if not fix:
                cmd = ["npx", "prettier", "--check", path]
            else:
                cmd = ["npx", "prettier", "--write", path]
        elif tool == "gofmt":
            cmd = ["gofmt", "-l", path]
            if fix:
                cmd.append("-w")

        # Route through ExecutionBackend
        run_id = f"lint_{uuid.uuid4().hex[:12]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        policy = ExecutionPolicy()
        policy.resource_limits.timeout_seconds = 120

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
                    "linter": tool,
                    "exit_code": result.exit_code,
                    "fixed": fix,
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
            logger.error("linter_error", error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()


class BenchmarkTool(Tool):
    """Performance benchmarking - routes through ExecutionBackend"""

    name = "benchmark"
    description = "Run performance benchmarks and profiling"
    parameters = {
        "type": {
            "type": "string",
            "required": True,
            "enum": ["python", "go", "node", "http"],
        },
        "target": {"type": "string", "required": True},
        "iterations": {"type": "integer", "default": 1000, "maximum": 10000},
    }

    def __init__(self, config):
        self.config = config

    async def execute(
        self, type: str, target: str, iterations: int = 1000, **kwargs
    ) -> dict[str, Any]:
        """Run benchmark through ExecutionBackend

        SECURITY: No shell=True. All benchmarks route through ExecutionBackend.
        Target parameter is NOT interpolated into shell strings.
        """

        # Build command as argv list (no shell interpolation)
        if type == "python":
            cmd = ["python", "-m", "timeit", "-n", str(iterations), "-s", target]
        elif type == "go":
            cmd = ["go", "test", "-bench=" + target, "-benchtime", f"{iterations}x"]
        elif type == "node":
            cmd = ["node", "--eval", target]
        elif type == "http":
            # HTTP benchmarks require explicit allowed targets
            # No arbitrary command execution
            return ToolResult(
                tool=self.name,
                success=False,
                error="HTTP benchmarks require server-side target configuration",
            ).to_dict()
        else:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Unknown benchmark type: {type}",
            ).to_dict()

        # Route through ExecutionBackend
        run_id = f"bench_{uuid.uuid4().hex[:12]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        policy = ExecutionPolicy()
        policy.resource_limits.timeout_seconds = 300

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
                    "iterations": iterations,
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
            logger.error("benchmark_error", error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()


class CoverageTool(Tool):
    """Code coverage analysis - routes through ExecutionBackend"""

    name = "coverage"
    description = "Analyze code coverage"
    parameters = {
        "path": {"type": "string", "default": "."},
        "format": {"type": "string", "default": "html"},
    }

    def __init__(self, config):
        self.config = config

    async def execute(
        self, path: str = ".", format: str = "html", **kwargs
    ) -> dict[str, Any]:
        """Run coverage analysis through ExecutionBackend"""

        # Build command as argv list
        cmd = ["coverage", "run", "-m", "pytest", path]

        # Route through ExecutionBackend
        run_id = f"cov_{uuid.uuid4().hex[:12]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        policy = ExecutionPolicy()
        policy.resource_limits.timeout_seconds = 600

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
                    "format": format,
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
            logger.error("coverage_error", error=str(e))
            return ToolResult(tool=self.name, success=False, error=str(e)).to_dict()