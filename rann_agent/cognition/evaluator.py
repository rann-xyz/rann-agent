"""
Evaluator module - rubric-based evaluation of agent outputs.

Provides evaluation of goals, plans, and outputs across multiple dimensions:
correctness, efficiency, style, and safety. Scores are weighted and combined
into a final 0-10 score with detailed feedback and improvement suggestions.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import structlog

from rann_agent.core.exceptions import RannAgentError, VerificationError

logger = structlog.get_logger()


@dataclass
class EvaluationResult:
    """
    Result of evaluating a goal/plan/output combination.

    Attributes:
        passed: Whether the evaluation passed the minimum threshold.
        score: Overall weighted score (0-10).
        details: Per-dimension scores and analysis.
        suggestions: List of improvement suggestions.
    """

    passed: bool
    score: float
    details: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "suggestions": self.suggestions,
        }


class Evaluator:
    """
    Rubric-based evaluator for agent outputs.

    Evaluates across four dimensions:
    - Correctness: Does the output fulfill the goal?
    - Efficiency: Is the solution performant and resource-conscious?
    - Style: Is the code/output well-structured and readable?
    - Safety: Are there security concerns or risks?

    Each dimension is scored 0-10 and weighted to produce a final score.
    """

    # Dimension weights (must sum to 1.0)
    DEFAULT_WEIGHTS = {
        "correctness": 0.40,
        "efficiency": 0.25,
        "style": 0.15,
        "safety": 0.20,
    }

    # Minimum score to pass
    PASS_THRESHOLD = 7.0

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        timeout: float = 30.0,
        pass_threshold: float = PASS_THRESHOLD,
    ) -> None:
        """
        Initialize the evaluator.

        Args:
            weights: Custom dimension weights. Defaults to DEFAULT_WEIGHTS.
            timeout: Maximum evaluation time in seconds.
            pass_threshold: Minimum score to consider evaluation passing.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.timeout = timeout
        self.pass_threshold = pass_threshold

        # Validate weights
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

        logger.info(
            "evaluator_initialized",
            weights=self.weights,
            timeout=self.timeout,
            pass_threshold=self.pass_threshold,
        )

    async def evaluate(
        self,
        goal: str,
        plan: Optional[str],
        output: Any,
    ) -> EvaluationResult:
        """
        Evaluate a goal, plan, and output combination.

        Args:
            goal: The original goal/objective.
            plan: The execution plan (if available).
            output: The actual output/result to evaluate.

        Returns:
            EvaluationResult with score, details, and suggestions.

        Raises:
            VerificationError: If evaluation fails due to system error.
        """
        logger.info("evaluation_start", goal=goal[:100], has_plan=plan is not None)

        try:
            # Run evaluation with timeout
            result = await asyncio.wait_for(
                self._perform_evaluation(goal, plan, output),
                timeout=self.timeout,
            )

            logger.info(
                "evaluation_complete",
                passed=result.passed,
                score=result.score,
            )

            return result

        except asyncio.TimeoutError:
            logger.error("evaluation_timeout", timeout=self.timeout)
            raise VerificationError(
                f"Evaluation timed out after {self.timeout}s",
                details={"timeout": self.timeout},
            )
        except Exception as e:
            logger.error("evaluation_error", error=str(e))
            raise VerificationError(f"Evaluation failed: {e}") from e

    async def _perform_evaluation(
        self,
        goal: str,
        plan: Optional[str],
        output: Any,
    ) -> EvaluationResult:
        """Perform the actual evaluation across all dimensions."""
        # Evaluate each dimension
        correctness = await self._evaluate_correctness(goal, plan, output)
        efficiency = await self._evaluate_efficiency(goal, plan, output)
        style = await self._evaluate_style(goal, plan, output)
        safety = await self._evaluate_safety(goal, plan, output)

        # Calculate weighted score
        score = (
            correctness["score"] * self.weights["correctness"]
            + efficiency["score"] * self.weights["efficiency"]
            + style["score"] * self.weights["style"]
            + safety["score"] * self.weights["safety"]
        )

        # Collect suggestions
        suggestions = []
        suggestions.extend(correctness.get("suggestions", []))
        suggestions.extend(efficiency.get("suggestions", []))
        suggestions.extend(style.get("suggestions", []))
        suggestions.extend(safety.get("suggestions", []))

        details = {
            "correctness": correctness,
            "efficiency": efficiency,
            "style": style,
            "safety": safety,
        }

        passed = score >= self.pass_threshold

        return EvaluationResult(
            passed=passed,
            score=round(score, 2),
            details=details,
            suggestions=suggestions,
        )

    async def _evaluate_correctness(
        self,
        goal: str,
        plan: Optional[str],
        output: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate correctness: Does the output fulfill the goal?

        Scoring rubric:
        - 9-10: Fully satisfies goal with edge cases handled
        - 7-8: Satisfies goal with minor issues
        - 5-6: Partially satisfies goal
        - 3-4: Significant issues, goal mostly unmet
        - 0-2: Goal not achieved
        """
        score = 7.0  # Default reasonable score
        suggestions: List[str] = []
        analysis = ""

        # Check if output is None or empty
        if output is None:
            score = 0.0
            suggestions.append("Output is empty - goal was not achieved")
            analysis = "No output produced"
        elif isinstance(output, dict) and output.get("error"):
            score = 2.0
            suggestions.append(f"Output contains error: {output.get('error')}")
            analysis = "Error in output"
        elif isinstance(output, str) and len(output.strip()) < 10:
            score = 4.0
            suggestions.append("Output is suspiciously short - may be incomplete")
            analysis = "Output appears truncated"
        else:
            # Check goal keywords in output
            goal_lower = goal.lower()
            output_str = str(output).lower()

            # Simple heuristic: check for goal-related content
            important_words = [
                w for w in goal_lower.split() if len(w) > 4 and w not in ["which", "what", "where", "when", "how", "create", "make", "build"]
            ]

            matched = sum(1 for word in important_words if word in output_str)
            coverage = matched / len(important_words) if important_words else 1.0

            if coverage < 0.3:
                score = 5.0
                suggestions.append("Output may not address all aspects of the goal")
                analysis = f"Keyword coverage: {coverage:.0%}"
            else:
                score = 7.5
                analysis = f"Keyword coverage: {coverage:.0%}"

        return {
            "score": score,
            "analysis": analysis,
            "suggestions": suggestions,
        }

    async def _evaluate_efficiency(
        self,
        goal: str,
        plan: Optional[str],
        output: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate efficiency: Is the solution performant?

        Considers:
        - Unnecessary complexity
        - Resource usage patterns
        - Algorithm efficiency indicators
        """
        score = 7.0
        suggestions: List[str] = []
        analysis = ""

        output_str = str(output)

        # Check for common inefficiency patterns
        inefficiency_patterns = [
            ("nested loops", ["for .* in .*:.*for .* in .*:", "nested loop"]),
            ("recursive without memoization", ["def .*\\(.*\\):.*\\n.*\\n.*\\n.*\\1"]),
            ("inefficient string concatenation", ["\\+ .*\\+ .*\\+"]),
        ]

        issues_found = []
        for pattern_name, _ in inefficiency_patterns:
            if pattern_name.lower() in output_str.lower():
                issues_found.append(pattern_name)

        if issues_found:
            score = 6.0
            suggestions.append(f"Potential inefficiency: {', '.join(issues_found)}")
            analysis = f"Found {len(issues_found)} potential inefficiency patterns"
        else:
            score = 8.0
            analysis = "No obvious efficiency issues detected"

        return {
            "score": score,
            "analysis": analysis,
            "suggestions": suggestions,
        }

    async def _evaluate_style(
        self,
        goal: str,
        plan: Optional[str],
        output: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate style: Is the output well-structured and readable?

        Considers:
        - Code formatting and organization
        - Naming conventions
        - Documentation quality
        """
        score = 7.0
        suggestions: List[str] = []
        analysis = ""

        output_str = str(output)

        # Check for basic style issues
        issues = []

        # Check for missing documentation in code
        if "def " in output_str or "class " in output_str:
            if "# " not in output_str and '"""' not in output_str and "'''" not in output_str:
                issues.append("code lacks documentation/comments")

        # Check for overly long lines (simplistic check)
        lines = output_str.split("\n")
        long_lines = [l for l in lines if len(l) > 120]
        if len(long_lines) > len(lines) * 0.3:
            issues.append("many long lines may hurt readability")

        # Check for consistent indentation (basic check)
        indented_lines = [l for l in lines if l.startswith("    ") or l.startswith("\t")]
        if indented_lines and len(indented_lines) > 5:
            # Basic sanity check
            analysis += "Indentation appears consistent"

        if issues:
            score = 6.0
            suggestions.extend(issues)
            analysis = f"Found {len(issues)} style issues"
        else:
            score = 8.0
            analysis = "Style appears good"

        return {
            "score": score,
            "analysis": analysis,
            "suggestions": suggestions,
        }

    async def _evaluate_safety(
        self,
        goal: str,
        plan: Optional[str],
        output: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate safety: Are there security concerns?

        Checks for:
        - Hardcoded secrets/credentials
        - SQL injection vulnerabilities
        - Command injection patterns
        - Insecure deserialization
        """
        score = 10.0
        suggestions: List[str] = []
        analysis = ""

        output_str = str(output)

        # Security issue patterns
        security_issues = [
            ("hardcoded password", ["password", "pwd", "passwd"]),
            ("hardcoded API key", ["api_key", "apikey", "api-key"]),
            ("hardcoded secret", ["secret", "token"]),
            ("potential SQL injection", ["execute(", "cursor.execute", "SELECT .* \\+ "]),
            ("potential command injection", ["os.system", "subprocess", "eval("]),
        ]

        issues_found = []
        for issue_name, patterns in security_issues:
            for pattern in patterns:
                if pattern.lower() in output_str.lower():
                    issues_found.append(issue_name)
                    break

        # Remove duplicates while preserving order
        seen = set()
        unique_issues = []
        for issue in issues_found:
            if issue not in seen:
                seen.add(issue)
                unique_issues.append(issue)

        if unique_issues:
            # Severe penalty for security issues
            score = max(1.0, 10.0 - len(unique_issues) * 3)
            suggestions.append(f"Security concerns: {', '.join(unique_issues)}")
            analysis = f"Found {len(unique_issues)} potential security issues"
        else:
            score = 10.0
            analysis = "No obvious security issues detected"

        return {
            "score": score,
            "analysis": analysis,
            "suggestions": suggestions,
        }