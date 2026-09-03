"""
Progress tracking and stall detection for RANN Agent.
As required by MASTER PROMPT Section 17.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import structlog

logger = structlog.get_logger()


@dataclass
class Iteration:
    iteration: int
    objective: str
    action: str
    observation: str
    result: str
    progress_delta: float  # -1 to 1, negative = regression


@dataclass
class StallReport:
    stall_type: str  # repeated_command, zero_progress, oscillation, repeated_error
    iterations_affected: int
    recommendation: str  # retry, replan, escalate, stop
    details: Dict[str, Any] = field(default_factory=dict)


class ProgressEngine:
    """Tracks iteration progress and detects stalls."""

    def __init__(self, max_history: int = 100) -> None:
        self.iterations: List[Iteration] = []
        self.max_history = max_history
        self._action_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}
        self._file_edits: Dict[str, int] = {}

    def record(
        self,
        iteration: int,
        objective: str,
        action: str,
        observation: str,
        result: str,
        progress_delta: float,
    ) -> None:
        iter_record = Iteration(
            iteration=iteration,
            objective=objective,
            action=action,
            observation=observation,
            result=result,
            progress_delta=progress_delta,
        )
        self.iterations.append(iter_record)

        # Track action frequency
        self._action_counts[action] = self._action_counts.get(action, 0) + 1

        # Track errors
        if "error" in result.lower() or "fail" in result.lower():
            self._error_counts[action] = self._error_counts.get(action, 0) + 1

        # Track file edits
        if "edit" in action.lower() or "write" in action.lower():
            self._file_edits[action] = self._file_edits.get(action, 0) + 1

        # Trim history
        if len(self.iterations) > self.max_history:
            self.iterations = self.iterations[-self.max_history:]

        logger.debug(
            "progress_recorded",
            iteration=iteration,
            progress_delta=progress_delta,
            total_progress=self.total_progress,
        )

    @property
    def total_progress(self) -> float:
        if not self.iterations:
            return 0.0
        deltas = [i.progress_delta for i in self.iterations]
        return sum(deltas) / len(deltas)

    def detect_stall(self) -> Optional[StallReport]:
        """Detect if progress has stalled."""
        if len(self.iterations) < 3:
            return None

        recent = self.iterations[-5:]

        # Check for repeated action (same command 3+ times)
        recent_actions = [i.action for i in recent]
        for action, count in self._action_counts.items():
            if count >= 3 and recent_actions.count(action) >= 3:
                return StallReport(
                    stall_type="repeated_command",
                    iterations_affected=count,
                    recommendation="replan",
                    details={"action": action, "count": count},
                )

        # Check for zero progress (all deltas near zero)
        recent_deltas = [i.progress_delta for i in recent]
        if all(abs(d) < 0.1 for d in recent_deltas):
            return StallReport(
                stall_type="zero_progress",
                iterations_affected=len(recent),
                recommendation="escalate",
                details={"recent_deltas": recent_deltas},
            )

        # Check for oscillation (alternating positive/negative)
        if len(recent) >= 4:
            signs = [1 if d > 0 else -1 if d < 0 else 0 for d in recent_deltas]
            if signs[0] != 0 and all(signs[i] == -signs[i - 1] for i in range(1, len(signs))):
                return StallReport(
                    stall_type="oscillation",
                    iterations_affected=len(recent),
                    recommendation="stop",
                    details={"deltas": recent_deltas},
                )

        # Check for repeated errors
        for action, count in self._error_counts.items():
            if count >= 3:
                return StallReport(
                    stall_type="repeated_error",
                    iterations_affected=count,
                    recommendation="stop",
                    details={"action": action, "errors": count},
                )

        return None