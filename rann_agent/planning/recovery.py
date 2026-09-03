"""
Recovery engine for RANN Agent.
As required by MASTER PROMPT Section 16.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Type, Callable
from enum import Enum
import structlog

logger = structlog.get_logger()


class FailureType(Enum):
    SYNTAX = "syntax"
    IMPORT = "import"
    DEPENDENCY = "dependency"
    RUNTIME = "runtime"
    TEST = "test"
    LINT = "lint"
    TYPE = "type"
    ENVIRONMENT = "environment"
    PERMISSION = "permission"
    NETWORK = "network"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    TOOL = "tool"
    PLANNING = "planning"
    REASONING = "reasoning"
    REQUIREMENT = "requirement"
    SECURITY = "security"


@dataclass
class FailureAnalysis:
    failure_type: FailureType
    root_cause: str
    contributing_factors: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    recovery_plan: str = ""


@dataclass
class RecoveryResult:
    recovered: bool
    strategy_used: str
    patched: bool = False
    re_run_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RecoveryStrategy(Callable[[FailureAnalysis], RecoveryResult]):
    """Base class for recovery strategies."""
    failure_types: List[FailureType] = []

    def __call__(self, failure: FailureAnalysis) -> RecoveryResult:
        raise NotImplementedError


class PatchSyntax(RecoveryStrategy):
    failure_types = [FailureType.SYNTAX]

    def __call__(self, failure: FailureAnalysis) -> RecoveryResult:
        logger.info("recovery_attempt", strategy="PatchSyntax", failure=failure.failure_type)
        return RecoveryResult(recovered=False, strategy_used="PatchSyntax")


class InstallDeps(RecoveryStrategy):
    failure_types = [FailureType.IMPORT, FailureType.DEPENDENCY]

    def __call__(self, failure: FailureAnalysis) -> RecoveryResult:
        logger.info("recovery_attempt", strategy="InstallDeps", failure=failure.failure_type)
        return RecoveryResult(recovered=False, strategy_used="InstallDeps")


class AddErrorHandling(RecoveryStrategy):
    failure_types = [FailureType.RUNTIME]

    def __call__(self, failure: FailureAnalysis) -> RecoveryResult:
        logger.info("recovery_attempt", strategy="AddErrorHandling", failure=failure.failure_type)
        return RecoveryResult(recovered=False, strategy_used="AddErrorHandling")


class FixTest(RecoveryStrategy):
    failure_types = [FailureType.TEST]

    def __call__(self, failure: FailureAnalysis) -> RecoveryResult:
        logger.info("recovery_attempt", strategy="FixTest", failure=failure.failure_type)
        return RecoveryResult(recovered=False, strategy_used="FixTest")


class ReduceScope(RecoveryStrategy):
    failure_types = [FailureType.TIMEOUT, FailureType.RESOURCE]

    def __call__(self, failure: FailureAnalysis) -> RecoveryResult:
        logger.info("recovery_attempt", strategy="ReduceScope", failure=failure.failure_type)
        return RecoveryResult(recovered=False, strategy_used="ReduceScope")


class RetryWithBackoff(RecoveryStrategy):
    failure_types = [FailureType.NETWORK]

    def __call__(self, failure: FailureAnalysis) -> RecoveryResult:
        logger.info("recovery_attempt", strategy="RetryWithBackoff", failure=failure.failure_type)
        return RecoveryResult(recovered=False, strategy_used="RetryWithBackoff")


class RecoveryEngine:
    """Selects and executes recovery strategies for failures."""

    def __init__(self) -> None:
        self.strategies: Dict[FailureType, List[RecoveryStrategy]] = {}
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        defaults: List[RecoveryStrategy] = [
            PatchSyntax(),
            InstallDeps(),
            AddErrorHandling(),
            FixTest(),
            ReduceScope(),
            RetryWithBackoff(),
        ]
        for strategy in defaults:
            for ft in strategy.failure_types:
                if ft not in self.strategies:
                    self.strategies[ft] = []
                self.strategies[ft].append(strategy)

    def analyze(self, error_message: str, context: Dict[str, Any]) -> FailureAnalysis:
        """Classify an error and determine root cause."""
        error_lower = error_message.lower()

        # Simple keyword-based classification
        if "syntax" in error_lower or "invalid syntax" in error_lower:
            ft = FailureType.SYNTAX
        elif "import" in error_lower or "modulenotfound" in error_lower:
            ft = FailureType.IMPORT
        elif "timeout" in error_lower or "timed out" in error_lower:
            ft = FailureType.TIMEOUT
        elif "permission" in error_lower or "access denied" in error_lower:
            ft = FailureType.PERMISSION
        elif "connection" in error_lower or "network" in error_lower:
            ft = FailureType.NETWORK
        elif "test" in error_lower or "assertion" in error_lower:
            ft = FailureType.TEST
        elif "memory" in error_lower or "cpu" in error_lower or "resource" in error_lower:
            ft = FailureType.RESOURCE
        elif "security" in error_lower or "injection" in error_lower:
            ft = FailureType.SECURITY
        else:
            ft = FailureType.RUNTIME

        return FailureAnalysis(
            failure_type=ft,
            root_cause=error_message[:200],
            evidence=[error_message],
            recovery_plan=f"Apply {ft.value} recovery strategy",
        )

    def recover(self, failure: FailureAnalysis) -> RecoveryResult:
        """Attempt recovery using appropriate strategies."""
        strategies = self.strategies.get(failure.failure_type, [])

        if not strategies:
            logger.warning("no_recovery_strategy", failure_type=failure.failure_type)
            return RecoveryResult(
                recovered=False,
                strategy_used="none",
                error=f"No strategy for {failure.failure_type.value}",
            )

        for strategy in strategies:
            try:
                result = strategy(failure)
                if result.recovered:
                    logger.info("recovery_succeeded", strategy=result.strategy_used)
                    return result
            except Exception as e:
                logger.warning("recovery_strategy_failed", strategy=type(strategy).__name__, error=str(e))

        logger.warning("all_recovery_strategies_failed", failure_type=failure.failure_type)
        return RecoveryResult(
            recovered=False,
            strategy_used="exhausted",
            error="All recovery strategies failed",
        )