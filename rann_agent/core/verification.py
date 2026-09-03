"""
Verification Engine

Verifies task completion with evidence-based proof.
As required by MASTER PROMPT Section 23-24.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import structlog

logger = structlog.get_logger()


class VerificationStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


class VerificationLevel(Enum):
    """Verification rigor levels"""
    NONE = "none"           # No verification
    BASIC = "basic"         # Simple output check
    MODERATE = "moderate"   # Run tests
    STRICT = "strict"       # Full regression suite
    PARANOID = "paranoid"   # All checks + security


@dataclass
class VerificationResult:
    """Result of a verification check"""
    status: VerificationStatus
    checks: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0
    
    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASSED
    
    @property
    def all_checks_passed(self) -> bool:
        return all(c.get("passed", False) for c in self.checks)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "passed": self.passed,
            "checks": self.checks,
            "evidence": self.evidence,
            "errors": self.errors,
            "warnings": self.warnings,
            "duration_ms": self.duration_ms
        }


@dataclass
class VerificationCheck:
    """A single verification check"""
    name: str
    description: str
    verify: Callable  # Async function that returns (passed, evidence, error)
    required: bool = True
    timeout_seconds: float = 60


class VerificationEngine:
    """
    Verifies task completion with evidence.
    
    Never trusts model claims - always verifies with runtime evidence.
    """
    
    def __init__(self, level: VerificationLevel = VerificationLevel.MODERATE):
        self.level = level
        self._checks: List[VerificationCheck] = []
        
        logger.info("verification_engine_init", level=level.value)
    
    def add_check(self, check: VerificationCheck) -> None:
        """Add a verification check"""
        self._checks.append(check)
        logger.debug("verification_check_added", name=check.name)
    
    def add_assertion(
        self,
        name: str,
        description: str,
        assertion: Callable,  # Sync function: () -> bool
        required: bool = True
    ) -> None:
        """Add a simple assertion check"""
        async def verify_fn():
            try:
                result = assertion()
                return result, {}, None
            except Exception as e:
                return False, {}, str(e)
        
        self.add_check(VerificationCheck(
            name=name,
            description=description,
            verify=verify_fn,
            required=required
        ))
    
    async def verify(
        self,
        task: str,
        output: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """
        Run all verification checks.
        
        Args:
            task: The original task description
            output: The task output to verify
            context: Additional context (files created, commands run, etc.)
            
        Returns:
            VerificationResult with status and evidence
        """
        import time
        start = time.time()
        
        result = VerificationResult(status=VerificationStatus.PENDING)
        context = context or {}
        
        logger.info("verification_started", task=task[:100], checks=len(self._checks))
        
        if self.level == VerificationLevel.NONE:
            result.status = VerificationStatus.SKIPPED
            return result
        
        for check in self._checks:
            try:
                logger.debug("running_check", check=check.name)
                
                passed, evidence, error = await check.verify()
                
                check_result = {
                    "name": check.name,
                    "description": check.description,
                    "passed": passed,
                    "required": check.required,
                    "evidence": evidence,
                    "error": error
                }
                
                result.checks.append(check_result)
                
                if evidence:
                    result.evidence[check.name] = evidence
                
                if error:
                    result.errors.append(f"{check.name}: {error}")
                    if check.required:
                        result.status = VerificationStatus.FAILED
                
            except Exception as e:
                logger.error("check_failed", check=check.name, error=str(e))
                result.errors.append(f"{check.name}: {str(e)}")
                if check.required:
                    result.status = VerificationStatus.FAILED
        
        # Determine overall status
        if result.status != VerificationStatus.FAILED:
            if self.level == VerificationLevel.PARANOID:
                if not result.all_checks_passed:
                    result.status = VerificationStatus.FAILED
                else:
                    result.status = VerificationStatus.PASSED
            else:
                result.status = VerificationStatus.PASSED
        
        result.duration_ms = (time.time() - start) * 1000
        
        logger.info(
            "verification_completed",
            status=result.status.value,
            checks_passed=sum(1 for c in result.checks if c["passed"]),
            checks_failed=sum(1 for c in result.checks if not c["passed"] and c["required"]),
            duration_ms=result.duration_ms
        )
        
        return result


# Standard verification checks factory
class VerificationChecks:
    """Factory for common verification checks"""
    
    @staticmethod
    def file_exists(path: str) -> VerificationCheck:
        """Verify a file exists"""
        import os
        from pathlib import Path
        
        async def verify():
            exists = Path(path).exists()
            evidence = {"path": path, "exists": exists}
            if exists:
                stat = Path(path).stat()
                evidence["size_bytes"] = stat.st_size
                evidence["modified"] = stat.st_mtime
            return exists, evidence, None
        
        return VerificationCheck(
            name=f"file_exists:{path}",
            description=f"File {path} exists",
            verify=verify
        )
    
    @staticmethod
    def file_contains(path: str, pattern: str) -> VerificationCheck:
        """Verify a file contains a pattern"""
        import re
        from pathlib import Path
        
        async def verify():
            try:
                content = Path(path).read_text()
                matches = re.findall(pattern, content)
                passed = bool(matches)
                return passed, {"matches": matches, "count": len(matches)}, None
            except Exception as e:
                return False, {}, str(e)
        
        return VerificationCheck(
            name=f"file_contains:{path}",
            description=f"File {path} contains pattern {pattern}",
            verify=verify
        )
    
    @staticmethod
    def command_succeeds(command: str, cwd: Optional[str] = None) -> VerificationCheck:
        """Verify a command succeeds (exit code 0)"""
        import subprocess
        
        async def verify():
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                passed = result.returncode == 0
                return passed, {
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr[:500]
                }, None if passed else f"Exit code {result.returncode}"
            except Exception as e:
                return False, {}, str(e)
        
        return VerificationCheck(
            name=f"command:{command[:50]}",
            description=f"Command succeeds: {command[:50]}",
            verify=verify
        )
    
    @staticmethod
    def python_syntax(file_path: str) -> VerificationCheck:
        """Verify Python file has valid syntax"""
        import ast
        from pathlib import Path
        
        async def verify():
            try:
                content = Path(file_path).read_text()
                ast.parse(content)
                return True, {}, None
            except SyntaxError as e:
                return False, {}, f"Syntax error: {e}"
        
        return VerificationCheck(
            name=f"python_syntax:{file_path}",
            description=f"Python syntax valid: {file_path}",
            verify=verify
        )
    
    @staticmethod
    def git_no_uncommitted_changes(repo_path: str) -> VerificationCheck:
        """Verify no uncommitted changes"""
        import subprocess
        
        async def verify():
            try:
                result = subprocess.run(
                    "git status --porcelain",
                    shell=True,
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                has_changes = bool(result.stdout.strip())
                return not has_changes, {"has_uncommitted": has_changes}, None
            except Exception as e:
                return False, {}, str(e)
        
        return VerificationCheck(
            name="git_clean",
            description="No uncommitted changes",
            verify=verify
        )