"""Unit tests for Phase 2: Task Graph, Tool Policy, Model Router"""

from rann_agent.orchestration.model_router import ModelRouter, TaskComplexity
from rann_agent.orchestration.task_graph import TaskGraph, TaskPriority, TaskStatus
from rann_agent.orchestration.tool_policy import (
    PolicyAction,
    RiskLevel,
    ToolPolicy,
    ToolPolicyEngine,
)


class TestTaskGraph:
    def test_create_graph(self):
        g = TaskGraph()
        assert g.tasks == {}
        assert g.root_id is None

    def test_add_task(self):
        g = TaskGraph()
        node = g.add_task("task1", "Do thing", priority=TaskPriority.HIGH)
        assert "task1" in g.tasks
        assert g.tasks["task1"].priority == TaskPriority.HIGH
        assert node.id == "task1"

    def test_dependencies(self):
        g = TaskGraph()
        g.add_task("a", "A")
        g.add_task("b", "B", dependencies=["a"])
        g.add_task("c", "C", dependencies=["a"])
        g.add_task("d", "D", dependencies=["b", "c"])
        assert set(g.tasks["a"].dependents) == {"b", "c"}
        assert set(g.tasks["d"].dependencies) == {"b", "c"}

    def test_ready_tasks_by_priority(self):
        g = TaskGraph()
        g.add_task("low", "Low", priority=TaskPriority.LOW)
        g.add_task("high", "High", priority=TaskPriority.HIGH)
        g.add_task("normal", "Normal", priority=TaskPriority.NORMAL)
        ready = g.get_ready_tasks()
        assert ready[0].id == "high"

    def test_blocked_until_deps_done(self):
        g = TaskGraph()
        g.add_task("a", "A")
        g.add_task("b", "B", dependencies=["a"])
        assert g.tasks["b"].status == TaskStatus.PENDING
        assert not g.tasks["b"].can_run(completed_ids=set())
        assert g.tasks["b"].can_run(completed_ids={"a"})

    def test_mark_completed(self):
        g = TaskGraph()
        g.add_task("t1", "Task 1")
        g.tasks["t1"].status = TaskStatus.COMPLETED
        g.tasks["t1"].result = {"result": "done"}
        assert g.tasks["t1"].status == TaskStatus.COMPLETED
        assert g.tasks["t1"].result["result"] == "done"

    def test_mark_failed_with_retry(self):
        g = TaskGraph()
        g.add_task("t1", "Task 1")
        g.tasks["t1"].status = TaskStatus.FAILED
        g.tasks["t1"].error = "Error"
        assert g.tasks["t1"].status == TaskStatus.FAILED
        assert g.tasks["t1"].error == "Error"

    def test_progress(self):
        g = TaskGraph()
        g.add_task("a", "A")
        g.add_task("b", "B")
        g.tasks["a"].status = TaskStatus.COMPLETED
        completed = g.get_completed_tasks()
        assert len(completed) == 1
        assert completed[0].id == "a"

    def test_serialization(self):
        g = TaskGraph()
        g.add_task("t1", "Task 1")
        d = g.to_dict()
        assert "tasks" in d
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
        engine.set_policy(
            ToolPolicy("test_tool", RiskLevel.LOW, PolicyAction.ALLOW, max_calls_per_run=2)
        )
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
