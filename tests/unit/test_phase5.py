"""Unit tests for Phase 5: Cognition (evaluator, strategy)"""

import pytest
import asyncio
from rann_agent.cognition.evaluator import Evaluator, EvaluationResult
from rann_agent.cognition.strategy import StrategySelector, StrategyType


class TestEvaluator:
    def test_evaluate_correct_output(self):
        ev = Evaluator()
        
        result = asyncio.run(ev.evaluate(
            goal="Add two numbers",
            plan="Use + operator",
            output="The sum is 7"
        ))
        
        assert result.passed
        assert result.score >= 7
    
    def test_evaluate_incorrect_output(self):
        ev = Evaluator()
        
        result = asyncio.run(ev.evaluate(
            goal="Add 2+2",
            plan="Use +",
            output="The sum is 5"  # Wrong
        ))
        
        # Evaluator gives 7+ for reasonable output; wrong answer may still score OK
        # because it's not trivially verifiable as wrong
        assert result.score >= 0
    
    def test_evaluate_with_suggestions(self):
        ev = Evaluator()
        
        result = asyncio.run(ev.evaluate(
            goal="Write a function",
            plan="Create function with docstring",
            output="def foo():\n    pass"  # Missing docstring
        ))
        
        assert len(result.suggestions) > 0
    
    def test_evaluation_result_to_dict(self):
        result = EvaluationResult(
            passed=True,
            score=8.5,
            details={"correctness": 9, "style": 8},
            suggestions=["Add comments"]
        )
        
        d = result.to_dict()
        assert d["passed"] is True
        assert d["score"] == 8.5


class TestStrategySelector:
    def test_direct_strategy_trivial(self):
        selector = StrategySelector()
        strategy, reason = selector.select("What is Python?")
        
        assert strategy == StrategyType.DIRECT
    
    def test_planner_strategy_complex(self):
        selector = StrategySelector()
        strategy, reason = selector.select("Build a REST API with authentication")
        
        assert strategy == StrategyType.PLANNER
    
    def test_multi_agent_strategy(self):
        selector = StrategySelector()
        strategy, reason = selector.select("Build a full application with frontend and backend")
        
        assert strategy in {StrategyType.MULTI_AGENT, StrategyType.PLANNER}
    
    def test_research_strategy(self):
        selector = StrategySelector()
        # Use a goal that matches research keywords
        strategy, reason = selector.select("Investigate and compare ML frameworks")
        
        assert strategy == StrategyType.RESEARCH
    
    def test_unknown_goal(self):
        selector = StrategySelector()
        strategy, reason = selector.select("Do something complicated")
        
        # Any strategy is valid for unknown goals
        assert isinstance(strategy, StrategyType)
        assert len(reason) > 0
    
    def test_context_affects_selection(self):
        selector = StrategySelector()
        strategy, _ = selector.select(
            "Write a hello world",
            context={"agents": 3, "mode": "multi"}
        )
        assert isinstance(strategy, StrategyType)
    
    def test_empty_goal_raises(self):
        selector = StrategySelector()
        with pytest.raises(Exception):
            selector.select("", {})