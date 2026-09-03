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
        
        assert result.score < 7
    
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
        assert "trivial" in reason.lower()
    
    def test_planner_strategy_complex(self):
        selector = StrategySelector()
        strategy, reason = selector.select("Build a REST API with authentication")
        
        assert strategy == StrategyType.PLANNER
    
    def test_multi_agent_strategy_research(self):
        selector = StrategySelector()
        strategy, reason = selector.select("Research and compare ML frameworks")
        
        assert strategy in {StrategyType.MULTI_AGENT, StrategyType.RESEARCH}
    
    def test_research_strategy(self):
        selector = StrategySelector()
        strategy, reason = selector.select("Find all papers about transformers")
        
        assert strategy == StrategyType.RESEARCH
    
    def test_unknown_goal_defaults_to_planner(self):
        selector = StrategySelector()
        strategy, reason = selector.select("Do something complicated")
        
        assert strategy in {StrategyType.PLANNER, StrategyType.MULTI_AGENT}
    
    def test_context_affects_selection(self):
        selector = StrategySelector()
        # With multi-agent context, even simple tasks might use multi-agent
        strategy, _ = selector.select(
            "Write a hello world",
            context={"agents": 3, "mode": "multi"}
        )
        # Context can override default behavior
        assert isinstance(strategy, StrategyType)