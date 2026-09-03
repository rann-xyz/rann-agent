"""
Strategy selection module - heuristic-based strategy selection for agent tasks.

Provides strategy selection based on goal analysis and complexity estimation.
Strategies determine how the agent approaches a given task, from direct execution
to multi-agent collaboration to deep research modes.
"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

from rann_agent.core.exceptions import StrategySelectionError

logger = structlog.get_logger()


class StrategyType(Enum):
    """
    Available execution strategies.

    DIRECT: Simple, single-step task execution.
        Use for: straightforward commands, simple queries
        Examples: "list files", "get current time", "simple calculations"

    PLANNER: Multi-step task with planning phase.
        Use for: tasks requiring multiple steps or sub-tasks
        Examples: "refactor module X", "implement feature Y", "write tests"

    MULTI_AGENT: Delegation to multiple specialized agents.
        Use for: complex tasks that benefit from parallel specialization
        Examples: "build full application", "comprehensive code review"

    RESEARCH: Deep research with verification and sources.
        Use for: tasks requiring investigation, comparison, or analysis
        Examples: "compare frameworks", "investigate issue", "research solutions"
    """

    DIRECT = "direct"
    PLANNER = "planner"
    MULTI_AGENT = "multi_agent"
    RESEARCH = "research"

    def __str__(self) -> str:
        return self.value


class StrategySelector:
    """
    Heuristic-based strategy selector.

    Selects an appropriate StrategyType based on:
    - Goal keywords and patterns
    - Estimated complexity
    - Available context
    """

    # Keywords that indicate each strategy
    STRATEGY_KEYWORDS = {
        StrategyType.DIRECT: [
            "list", "get", "show", "find", "check", "what is", "who is",
            "current", "today", "now", "display", "print", "echo",
        ],
        StrategyType.PLANNER: [
            "create", "make", "build", "implement", "write", "refactor",
            "update", "modify", "fix", "add", "remove", "delete",
            "configure", "setup", "install", "deploy", "run", "execute",
        ],
        StrategyType.MULTI_AGENT: [
            "application", "service", "system", "full", "complete",
            "comprehensive", "end-to-end", "entire", "multiple",
            "build a", "develop a", "create a",
        ],
        StrategyType.RESEARCH: [
            "research", "investigate", "compare", "analyze", "evaluate",
            "review", "study", "explore", "understand", "difference",
            "pros and cons", "vs", "versus", "alternative", "benchmark",
        ],
    }

    # Complexity indicators
    HIGH_COMPLEXITY_PATTERNS = [
        r"\band\b.*\band\b",  # Multiple "and" clauses
        r"\bor\b.*\bor\b",  # Multiple "or" clauses
        r"(please|could|would).*(please|could|would)",  # Repeated politeness
        r"(first|then|next|finally|also|additionally)",  # Sequence indicators
        r"\d+\s+(steps?|tasks?|parts?|phases?)",  # Explicit multi-part
        r"(all|both|every|each)",  # Universal quantifiers
    ]

    def __init__(self, complexity_threshold: int = 2) -> None:
        """
        Initialize the strategy selector.

        Args:
            complexity_threshold: Minimum number of complexity indicators
                                  to suggest PLANNER or higher strategy.
        """
        self.complexity_threshold = complexity_threshold
        logger.info("strategy_selector_initialized", complexity_threshold=complexity_threshold)

    def select(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[StrategyType, str]:
        """
        Select the best strategy for the given goal.

        Args:
            goal: The task/goal description.
            context: Optional context dictionary with additional information
                     such as available tools, budget constraints, or
                     user preferences.

        Returns:
            Tuple of (StrategyType, reasoning) where reasoning explains
            why this strategy was selected.

        Raises:
            StrategySelectionError: If strategy selection fails.
        """
        if not goal or not goal.strip():
            raise StrategySelectionError("Goal cannot be empty")

        goal_lower = goal.lower().strip()

        try:
            # Count complexity indicators
            complexity = self._estimate_complexity(goal_lower)

            # Check keyword matches
            strategy_scores = self._score_strategies(goal_lower)

            # Factor in context if provided
            if context:
                strategy_scores = self._apply_context(strategy_scores, context, goal_lower)

            # Boost complexity-influenced strategies
            if complexity >= self.complexity_threshold:
                # Push toward PLANNER or higher
                if strategy_scores[StrategyType.PLANNER] < 0.7:
                    strategy_scores[StrategyType.PLANNER] += 0.2
                if complexity >= self.complexity_threshold + 1:
                    strategy_scores[StrategyType.MULTI_AGENT] += 0.15

            # Select highest scoring strategy
            selected = max(strategy_scores, key=strategy_scores.get)
            reasoning = self._build_reasoning(selected, goal, complexity, strategy_scores)

            logger.info(
                "strategy_selected",
                strategy=selected.value,
                reasoning=reasoning[:100],
                complexity=complexity,
            )

            return selected, reasoning

        except Exception as e:
            logger.error("strategy_selection_failed", error=str(e))
            raise StrategySelectionError(f"Failed to select strategy: {e}") from e

    def _estimate_complexity(self, goal: str) -> int:
        """Estimate task complexity based on patterns."""
        complexity = 0

        for pattern in self.HIGH_COMPLEXITY_PATTERNS:
            if re.search(pattern, goal):
                complexity += 1

        # Count conjunction-separated clauses
        clauses = re.split(r",\s*|,?\s+and\s+|,\s*but\s+", goal)
        if len(clauses) > 2:
            complexity += len(clauses) - 2

        # Check for explicit step indicators
        step_words = ["step", "phase", "stage", "part", "task"]
        for word in step_words:
            if word in goal:
                complexity += 1

        return complexity

    def _score_strategies(self, goal: str) -> Dict[StrategyType, float]:
        """Score each strategy based on keyword matching."""
        scores: Dict[StrategyType, float] = {st: 0.0 for st in StrategyType}

        for strategy, keywords in self.STRATEGY_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in goal)
            if matches > 0:
                # Normalize: more matches = higher score, capped at 0.9
                scores[strategy] = min(0.9, matches * 0.25)

        # If no keywords matched, default to DIRECT
        if all(s == 0.0 for s in scores.values()):
            scores[StrategyType.DIRECT] = 0.5

        return scores

    def _apply_context(
        self,
        scores: Dict[StrategyType, float],
        context: Dict[str, Any],
        goal: str,
    ) -> Dict[StrategyType, float]:
        """Apply context-based adjustments to strategy scores."""
        # User preference override
        preferred = context.get("preferred_strategy")
        if preferred and isinstance(preferred, str):
            try:
                preferred_type = StrategyType(preferred)
                scores[preferred_type] = max(scores[preferred_type], 0.8)
            except ValueError:
                logger.warning("invalid_preferred_strategy", preferred=preferred)

        # Budget constraints
        budget = context.get("budget")
        if budget:
            budget_int = int(budget) if isinstance(budget, (int, str)) else 0
            if budget_int < 1000:
                # Low budget: prefer simpler strategies
                scores[StrategyType.MULTI_AGENT] *= 0.5
                scores[StrategyType.RESEARCH] *= 0.7

        # Tool availability
        available_tools = context.get("available_tools", [])
        if available_tools:
            # If limited tools, avoid MULTI_AGENT
            if len(available_tools) < 5:
                scores[StrategyType.MULTI_AGENT] *= 0.6

        # Explicit multi-agent indicator in goal
        if any(p in goal for p in ["parallel", "concurrent", "simultaneously"]):
            scores[StrategyType.MULTI_AGENT] = max(scores[StrategyType.MULTI_AGENT], 0.7)

        return scores

    def _build_reasoning(
        self,
        strategy: StrategyType,
        goal: str,
        complexity: int,
        scores: Dict[StrategyType, float],
    ) -> str:
        """Build human-readable reasoning for strategy selection."""
        reasoning_parts = []

        # Primary rationale
        if strategy == StrategyType.DIRECT:
            reasoning_parts.append("Goal appears straightforward")
        elif strategy == StrategyType.PLANNER:
            reasoning_parts.append("Goal requires multi-step execution")
        elif strategy == StrategyType.MULTI_AGENT:
            reasoning_parts.append("Goal benefits from parallel specialized agents")
        elif strategy == StrategyType.RESEARCH:
            reasoning_parts.append("Goal requires investigation and analysis")

        # Complexity note
        if complexity >= self.complexity_threshold:
            reasoning_parts.append(f"detected complexity level {complexity}")

        # Score comparison
        sorted_strategies = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_strategies) > 1:
            runner_up = sorted_strategies[1]
            if runner_up[1] > 0.1:
                reasoning_parts.append(
                    f"({strategy.value}={scores[strategy]:.2f} vs "
                    f"{runner_up[0].value}={runner_up[1]:.2f})"
                )

        return "; ".join(reasoning_parts)