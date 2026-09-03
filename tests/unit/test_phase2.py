"""Unit tests for Phase 2: Task Graph, Tool Policy, Model Router"""

import pytest
from rann_agent.orchestration.task_graph import TaskGraph, TaskStatus, TaskPriority
from rann_agent.orchestration.tool_policy import ToolPolicyEngine, RiskLevel, PolicyAction, ToolPolicy
from rann_agent.orchestration.model_router import ModelRouter, TaskComplexity


class TestTaskGraph:
    def test_create_graph(self):
        g = TaskGraph("test-graph")
        assert g.graph_id == "test-graph"
        assert g.root_task_id in g.tasks
    
    def test_add_task(self):
        g = TaskGraph("test")
        g.add_task("task1", "Do thing", priority=TaskPriority.HIGH)
        assert "task1" in g.tasks
        assert g.tasks["task1"].priority == TaskPriority.HIGH
    
    def test_dependencies(self):
        g = TaskGraph("test")
        g.add_task("a", "A")
        g.add_task("b", "B", dependencies=["a"])
        g.add_task("c", "C", dependencies=["a"])
        g.add_task("d", "D", dependencies=["b", "c"])
        assert g.tasks["a"].dependents == {"b", "c"}
        assert g.tasks["d"].dependencies == {"b", "c"}
    
    def test_ready_tasks_by_priority(self):
        g = TaskGraph("test")
        g.add_task("low", "Low", priority=TaskPriority.LOW)
        g.add_task("high", "High", priority=TaskPriority.HIGH)
        ready = [t for t in g.get_ready_tasks() if t.task_id != g.root_task_id]
        assert ready[0].task_id == "high"
    
    def test_blocked_until_deps_done(self):
        g = TaskGraph("test")
        g.add_task("a", "A")
        g.add_task("b", "B", dependencies=["a"])
        assert g.tasks["b"].status == TaskStatus.BLOCKED
        g.mark_completed("a")
        assert g.tasks["b"].status == TaskStatus.READY
    
    def test_mark_completed(self):
        g = TaskGraph("test")
        g.add_task("t1", "Task 1")
        g.mark_completed("t1", {"result": "done"})
        assert g.tasks["t1"].status == TaskStatus.COMPLETED
        assert g.tasks["t1"].output_data["result"] == "done"
    
    def test_mark_failed_with_retry(self):
        g = TaskGraph("test")
        g.add_task("t1", "Task 1", max_retries=2)
        g.mark_failed("t1", "Error")
        assert g.tasks["t1"].retry_count == 1
        assert g.tasks["t1"].status == TaskStatus.READY
        g.mark_failed("t1", "Error")
        assert g.tasks["t1"].status == TaskStatus.FAILED
    
    def test_progress(self):
        g = TaskGraph("test")
        g.add_task("a", "A")
        g.add_task("b", "B")
        g.mark_completed("a")
        prog = g.get_progress()
        assert prog["total"] == 3  # root + a + b
        assert prog["completed"] == 1
    
    def test_to_dict(self):
        g = TaskGraph("test")
        g.add_task("t1", "Task 1")
        d = g.to_dict()
        assert d["graph_id"] == "test"
        assert "t1" in d["tasks"]


class TestToolPolicyEngine:
    def test_default_policies(self):
        engine = ToolPolicyEngine()
        assert engine.get_policy("file_read") is not None
        assert engine.get_policy("docker") is not None
    
    def test_safe_tool_allowed(self):
        engine = ToolPolicyEngine()
        decision = engine.check("file_read")
        assert decision.allowed
        assert decision.risk_level == RiskLevel.SAFE
    
    def test_critical_tool_denied(self):
        engine = ToolPolicyEngine()
        decision = engine.check("docker")
        assert not decision.allowed
    
    def test_rate_limit(self):
        engine = ToolPolicyEngine()
        engine.set_policy(ToolPolicy("test_tool", RiskLevel.LOW, PolicyAction.ALLOW, max_calls_per_run=2))
        engine.record_call("test_tool")
        engine.record_call("test_tool")
        decision = engine.check("test_tool")
        assert decision.action == PolicyAction.RATE_LIMIT
    
    def test_summary(self):
        engine = ToolPolicyEngine()
        s = engine.get_summary()
        assert s["total_policies"] > 0


class TestModelRouter:
    def test_trivial_task(self):
        router = ModelRouter()
        result = router.route("What is Python?")
        assert result.complexity == TaskComplexity.TRIVIAL
    
    def test_high_complexity(self):
        router = ModelRouter()
        result = router.route("Implement a new database engine from scratch")
        assert result.complexity == TaskComplexity.HIGH
    
    def test_vision_routing(self):
        router = ModelRouter()
        result = router.route("Describe this image", requires_vision=True)
        assert result.model in router.MODELS
    
    def test_user_preference(self):
        router = ModelRouter()
        router.set_user_preference("user1", "gpt-4o-mini")
        result = router.route("What is 2+2", user="user1")
        assert result.model == "gpt-4o-mini"
    
    def test_available_models(self):
        router = ModelRouter()
        models = router.get_available_models()
        assert len(models) >= 5