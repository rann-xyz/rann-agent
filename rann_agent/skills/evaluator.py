"""
Skill evaluation and performance tracking.

Provides a framework for running skill code against test cases and recording
pass/fail metrics over time using an on-disk JSON ledger.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


# -----------------------------------------------------------------------------
# Data classes
# -----------------------------------------------------------------------------

@dataclass
class TestCase:
    """A single input/expected-output test for a skill."""

    name: str
    input: dict[str, Any] = field(default_factory=dict)
    expected: Any = None
    validate_output: Optional[callable] = None  # not serialised — set in code

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "input": self.input,
            "expected": self.expected,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TestCase:
        return cls(
            name=data["name"],
            input=data.get("input", {}),
            expected=data.get("expected"),
        )


@dataclass
class TestResult:
    """Outcome of running a single test case."""

    test_name: str
    passed: bool
    actual: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationResult:
    """Aggregate result of evaluating a skill against a suite of test cases."""

    skill_id: str
    timestamp: str
    passed_count: int
    failed_count: int
    total_count: int
    results: list[TestResult]
    duration_ms: float = 0.0
    success_rate: float = 0.0

    def __post_init__(self) -> None:
        self.success_rate = self.passed_count / self.total_count if self.total_count > 0 else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> EvaluationResult:
        results = [TestResult(**tr) for tr in data.get("results", [])]
        return cls(
            skill_id=data["skill_id"],
            timestamp=data["timestamp"],
            passed_count=data["passed_count"],
            failed_count=data["failed_count"],
            total_count=data["total_count"],
            results=results,
            duration_ms=data.get("duration_ms", 0.0),
            success_rate=data.get("success_rate", 0.0),
        )


# -----------------------------------------------------------------------------
# Performance ledger
# -----------------------------------------------------------------------------

class PerformanceLedger:
    """
    Append-only JSON ledger of EvaluationResult entries.
    Kept in memory for the session and flushed to disk on demand.
    """

    def __init__(self, ledger_path: Optional[Path] = None) -> None:
        self._ledger_path = ledger_path or Path("~/.rann-agent/data/skill_evaluations.json")
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self._ledger_path.exists():
            return
        try:
            with open(self._ledger_path, encoding="utf-8") as fh:
                self._entries = json.load(fh)
        except json.JSONDecodeError:
            self._entries = []

    def append(self, result: EvaluationResult) -> None:
        self._entries.append(result.to_dict())

    def save(self) -> None:
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._ledger_path, "w", encoding="utf-8") as fh:
            json.dump(self._entries, fh, indent=2)

    def get_history(self, skill_id: Optional[str] = None, limit: int = 100) -> list[EvaluationResult]:
        entries = self._entries
        if skill_id is not None:
            entries = [e for e in entries if e.get("skill_id") == skill_id]
        return [EvaluationResult.from_dict(e) for e in entries[-limit:]]

    def get_metrics(self, skill_id: str) -> dict[str, Any]:
        """Compute aggregate metrics for a skill across all recorded evaluations."""
        history = self.get_history(skill_id=skill_id, limit=1000)
        if not history:
            return {"total_evaluations": 0, "avg_success_rate": 0.0, "total_runs": 0}

        total_runs = sum(e.total_count for e in history)
        passed = sum(e.passed_count for e in history)
        return {
            "total_evaluations": len(history),
            "total_test_runs": total_runs,
            "total_passed": passed,
            "total_failed": total_runs - passed,
            "avg_success_rate": passed / total_runs if total_runs > 0 else 0.0,
            "last_evaluation": history[-1].timestamp if history else None,
        }


# -----------------------------------------------------------------------------
# Skill evaluator
# -----------------------------------------------------------------------------

class SkillEvaluator:
    """
    Evaluates skill code against a suite of test cases and records metrics.

    Uses the ``SkillLoader`` to load and execute skill code in isolation.
    """

    def __init__(
        self,
        ledger_path: Optional[Path] = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._ledger = PerformanceLedger(ledger_path=ledger_path)
        self._default_timeout = default_timeout
        self._logger = logger.bind(component="skill_evaluator")

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def evaluate_skill(
        self,
        skill_id: str,
        skill_code: str,
        test_cases: list[TestCase],
        timeout: Optional[float] = None,
    ) -> EvaluationResult:
        """
        Run ``skill_code`` through the given ``test_cases`` and return an
        ``EvaluationResult`` with pass/fail details.

        Each ``TestCase`` can optionally carry a ``validate_output`` callable
        that receives the actual output and returns True/False.
        Otherwise, a simple equality check against ``expected`` is used.
        """
        from rann_agent.skills.loader import SkillLoader

        timeout = timeout or self._default_timeout
        loader = SkillLoader(timeout=timeout)

        module_result = loader.load_skill(skill_id, source=skill_code)
        if not module_result.loaded:
            return self._error_result(skill_id, f"Load failed: {module_result.error}", test_cases)

        skill_module = module_result.module
        assert skill_module is not None

        start = time.perf_counter()
        results: list[TestResult] = []
        passed = 0
        failed = 0

        for tc in test_cases:
            result = self._run_test_case(skill_module, tc, timeout)
            results.append(result)
            if result.passed:
                passed += 1
            else:
                failed += 1

        duration_ms = (time.perf_counter() - start) * 1000

        eval_result = EvaluationResult(
            skill_id=skill_id,
            timestamp=datetime.utcnow().isoformat(),
            passed_count=passed,
            failed_count=failed,
            total_count=len(test_cases),
            results=results,
            duration_ms=duration_ms,
        )

        self._ledger.append(eval_result)
        self._ledger.save()

        self._logger.info(
            "skill_evaluated",
            skill_id=skill_id,
            passed=passed,
            failed=failed,
            success_rate=eval_result.success_rate,
        )
        return eval_result

    def get_metrics(self, skill_id: str) -> dict[str, Any]:
        """Return aggregate metrics for a skill."""
        return self._ledger.get_metrics(skill_id)

    def get_history(self, skill_id: Optional[str] = None, limit: int = 50) -> list[EvaluationResult]:
        """Return recent evaluation results, optionally filtered by skill."""
        return self._ledger.get_history(skill_id=skill_id, limit=limit)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _run_test_case(
        self,
        skill_module: Any,
        tc: TestCase,
        timeout: float,
    ) -> TestResult:
        from rann_agent.skills.loader import SkillLoader, ExecutionTimeoutError

        run_func = getattr(skill_module, "run", None)
        if run_func is None:
            return TestResult(
                test_name=tc.name,
                passed=False,
                error="'run' function not found in skill module",
            )

        loader = SkillLoader(timeout=timeout)
        start = time.perf_counter()
        try:
            actual = run_func(**tc.input)
        except ExecutionTimeoutError:
            return TestResult(
                test_name=tc.name,
                passed=False,
                error=f"Execution timeout ({timeout}s)",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:  # noqa: BLE001
            return TestResult(
                test_name=tc.name,
                passed=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        duration_ms = (time.perf_counter() - start) * 1000

        # Determine pass/fail
        if tc.validate_output is not None:
            try:
                passed = bool(tc.validate_output(actual))
            except Exception:  # noqa: BLE001
                passed = False
        else:
            passed = actual == tc.expected

        return TestResult(
            test_name=tc.name,
            passed=passed,
            actual=actual,
            duration_ms=duration_ms,
        )

    def _error_result(
        self,
        skill_id: str,
        error: str,
        test_cases: list[TestCase],
    ) -> EvaluationResult:
        return EvaluationResult(
            skill_id=skill_id,
            timestamp=datetime.utcnow().isoformat(),
            passed_count=0,
            failed_count=len(test_cases),
            total_count=len(test_cases),
            results=[
                TestResult(test_name=tc.name, passed=False, error=error)
                for tc in test_cases
            ],
        )