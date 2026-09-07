"""
Tests for Phase 4 multi-agent components:
- SharedContext (cross-agent memory store)
- TaskGraph (DAG-based task decomposition)
- AgentRegistry (dynamic agent lifecycle)
- MessageBus (structured inter-agent communication)
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from rann_agent.orchestration.agent_registry import (
    AgentCapability,
    AgentInfo,
    AgentRegistry,
    AgentStatus,
)
from rann_agent.orchestration.message_bus import Message, MessageBus, MessagePriority, MessageType
from rann_agent.orchestration.shared_context import ContextEntry, SharedContext, VersionVector
from rann_agent.orchestration.task_graph import TaskGraph, TaskNode, TaskPriority, TaskStatus

# ═══════════════════════════════════════════════════════════════════
# SharedContext Tests
# ═══════════════════════════════════════════════════════════════════


class TestContextEntry:
    def test_expired_false_when_no_ttl(self):
        entry = ContextEntry(
            key="k",
            value="v",
            version=1,
            created_at=time.time() - 100,
            updated_at=time.time() - 100,
            ttl=None,
            owner_agent_id="a1",
        )
        assert not entry.is_expired()

    def test_expired_true_when_past_ttl(self):
        entry = ContextEntry(
            key="k",
            value="v",
            version=1,
            created_at=time.time() - 1000,
            updated_at=time.time() - 1000,
            ttl=60,
            owner_agent_id="a1",
        )
        assert entry.is_expired()

    def test_expired_false_when_within_ttl(self):
        entry = ContextEntry(
            key="k",
            value="v",
            version=1,
            created_at=time.time(),
            updated_at=time.time(),
            ttl=3600,
            owner_agent_id="a1",
        )
        assert not entry.is_expired()

    def test_to_dict_roundtrip(self):
        entry = ContextEntry(
            key="k",
            value={"a": 1},
            version=5,
            created_at=100.0,
            updated_at=200.0,
            ttl=300.0,
            owner_agent_id="a1",
            tags=["tag1"],
            access_count=10,
        )
        d = entry.to_dict()
        restored = ContextEntry.from_dict(d)
        assert restored.key == entry.key
        assert restored.value == entry.value
        assert restored.version == entry.version


class TestVersionVector:
    def test_increment(self):
        vv = VersionVector()
        vv.increment("agent1")
        assert vv.get("agent1") == 1
        vv.increment("agent1")
        assert vv.get("agent1") == 2

    def test_merge_takes_max(self):
        vv1 = VersionVector(clock={"a": 5, "b": 1})
        vv2 = VersionVector(clock={"a": 3, "b": 10, "c": 2})
        vv1.merge(vv2)
        assert vv1.get("a") == 5
        assert vv1.get("b") == 10
        assert vv1.get("c") == 2

    def test_happened_before(self):
        vv1 = VersionVector(clock={"a": 1, "b": 2})
        vv2 = VersionVector(clock={"a": 2, "b": 2})
        assert vv1.happened_before(vv2)
        assert not vv2.happened_before(vv1)


class TestSharedContext:
    def test_set_and_get(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        ctx.set("key1", "value1")
        assert ctx.get("key1") == "value1"

    def test_get_default(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        assert ctx.get("missing", "default") == "default"

    def test_set_updates_version(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        ctx.set("k", "v1")
        v1 = ctx.version_for("k")
        ctx.set("k", "v2")
        v2 = ctx.version_for("k")
        assert v2 > v1

    def test_set_if_version_success(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        ctx.set("k", "v1")
        v = ctx.version_for("k")
        result = ctx.set_if_version("k", "v2", expected_version=v)
        assert result is True
        assert ctx.get("k") == "v2"

    def test_set_if_version_mismatch(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        ctx.set("k", "v1")
        result = ctx.set_if_version("k", "v2", expected_version=99)
        assert result is False
        assert ctx.get("k") == "v1"

    def test_delete(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        ctx.set("k", "v")
        assert ctx.get("k") == "v"
        ctx.delete("k")
        assert ctx.get("k") is None

    def test_tags(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        ctx.set("k", "v", tags=["backend", "urgent"])
        assert ctx.find_by_tags(["urgent"]) == {"k": "v"}
        assert ctx.find_by_tags(["backend", "urgent"], match_all=True) == {"k": "v"}
        assert ctx.find_by_tags(["frontend"]) == {}

    def test_clear_by_owner(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        ctx.set("k1", "v1", owner_agent_id="agent1")
        ctx.set("k2", "v2", owner_agent_id="agent2")
        ctx.set("k3", "v3", owner_agent_id="agent1")
        count = ctx.clear(agent_id="agent1")
        assert count == 2
        assert ctx.get("k1") is None
        assert ctx.get("k2") == "v2"
        assert ctx.get("k3") is None

    def test_persistence(self, tmp_path):
        path = tmp_path / "ctx.json"
        ctx1 = SharedContext(persist_path=path)
        ctx1.set("persistent", "value")
        ctx1.set("with_tags", "tv", tags=["tag1"])

        ctx2 = SharedContext(persist_path=path)
        assert ctx2.get("persistent") == "value"
        assert ctx2.get("with_tags") == "tv"

    def test_stats(self, tmp_path):
        ctx = SharedContext(persist_path=tmp_path / "ctx.json")
        ctx.set("k1", "v1", owner_agent_id="a1")
        ctx.set("k2", "v2", owner_agent_id="a2")
        stats = ctx.stats()
        assert stats["total_entries"] == 2
        assert stats["active_entries"] == 2
        assert "a1" in stats["by_owner"]


# ═══════════════════════════════════════════════════════════════════
# TaskGraph Tests
# ═══════════════════════════════════════════════════════════════════


class TestTaskNode:
    def test_is_ready_no_dependencies(self):
        node = TaskNode(id="t1", name="Task 1")
        assert node.is_ready()

    def test_is_ready_with_dependencies_still_pending(self):
        node = TaskNode(id="t2", name="Task 2", dependencies=["t1"])
        assert not node.is_ready()

    def test_can_run_all_deps_done(self):
        node = TaskNode(id="t2", name="Task 2", dependencies=["t1"])
        assert node.can_run(completed_ids={"t1"})
        assert not node.can_run(completed_ids=set())


class TestTaskGraph:
    def test_add_task(self):
        graph = TaskGraph()
        node = graph.add_task("task1", "Build API")
        assert node.id == "task1"
        assert "task1" in graph.tasks

    def test_add_task_auto_id(self):
        graph = TaskGraph()
        node = graph.add_task_auto_id("Build API")
        assert node.id != "Build API"
        assert len(node.id) == 8

    def test_link(self):
        graph = TaskGraph()
        graph.add_task("a", "Task A")
        graph.add_task("b", "Task B")
        graph.link("a", "b")
        assert "a" in graph.tasks["b"].dependencies
        assert "b" in graph.tasks["a"].dependents

    def test_validate_no_cycle(self):
        graph = TaskGraph()
        graph.add_task("a", "A")
        graph.add_task("b", "B", dependencies=["a"])
        graph.add_task("c", "C", dependencies=["b"])
        assert graph.validate() is True

    def test_validate_cycle_detected(self):
        graph = TaskGraph()
        graph.add_task("a", "A", dependencies=["b"])
        graph.add_task("b", "B", dependencies=["a"])
        with pytest.raises(ValueError, match="Cycle"):
            graph.validate()

    def test_get_ready_tasks_empty(self):
        graph = TaskGraph()
        assert graph.get_ready_tasks() == []

    def test_get_ready_tasks_single(self):
        graph = TaskGraph()
        graph.add_task("a", "A")
        graph.add_task("b", "B", dependencies=["a"])
        ready = graph.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "a"

    def test_get_ready_tasks_sorted_by_priority(self):
        graph = TaskGraph()
        graph.add_task("low", "Low", priority=TaskPriority.LOW)
        graph.add_task("high", "High", priority=TaskPriority.HIGH)
        graph.add_task("normal", "Normal", priority=TaskPriority.NORMAL)
        ready = graph.get_ready_tasks()
        assert ready[0].id == "high"
        assert ready[1].id in ("normal", "low")

    def test_critical_path(self):
        graph = TaskGraph()
        graph.add_task("a", "A", estimated_duration=10)
        graph.add_task("b", "B", dependencies=["a"], estimated_duration=20)
        graph.add_task("c", "C", dependencies=["a"], estimated_duration=5)
        graph.add_task("d", "D", dependencies=["b"], estimated_duration=15)
        path = graph.get_critical_path()
        assert path == ["a", "b", "d"]

    def test_parallel_batches(self):
        graph = TaskGraph()
        graph.add_task("a", "A")
        graph.add_task("b", "B", dependencies=["a"])
        graph.add_task("c", "C", dependencies=["a"])
        graph.add_task("d", "D", dependencies=["b", "c"])
        batches = graph.get_parallel_batches()
        assert len(batches) == 3
        assert batches[0] == ["a"]
        assert set(batches[1]) == {"b", "c"}
        assert batches[2] == ["d"]

    def test_is_complete_all_done(self):
        graph = TaskGraph()
        graph.add_task("a", "A")
        graph.add_task("b", "B")
        graph.tasks["a"].status = TaskStatus.COMPLETED
        graph.tasks["b"].status = TaskStatus.COMPLETED
        assert graph.is_complete()

    def test_is_complete_one_failed(self):
        graph = TaskGraph()
        graph.add_task("a", "A")
        graph.add_task("b", "B")
        graph.tasks["a"].status = TaskStatus.COMPLETED
        graph.tasks["b"].status = TaskStatus.FAILED
        assert graph.is_complete()

    def test_get_blocked_tasks(self):
        graph = TaskGraph()
        graph.add_task("a", "A")
        graph.add_task("b", "B", dependencies=["a"])
        graph.add_task("c", "C", dependencies=["a"])
        graph.tasks["a"].status = TaskStatus.FAILED
        blocked = graph.get_blocked_tasks()
        assert len(blocked) == 2

    def test_topological_sort(self):
        graph = TaskGraph()
        graph.add_task("a", "A")
        graph.add_task("b", "B", dependencies=["a"])
        graph.add_task("c", "C", dependencies=["a"])
        graph.add_task("d", "D", dependencies=["b", "c"])
        topo = graph._topological_sort()
        assert topo.index("a") < topo.index("b")
        assert topo.index("a") < topo.index("c")
        assert topo.index("b") < topo.index("d")
        assert topo.index("c") < topo.index("d")


# ═══════════════════════════════════════════════════════════════════
# AgentRegistry Tests
# ═══════════════════════════════════════════════════════════════════


class TestAgentInfo:
    def test_is_alive_recent_heartbeat(self):
        info = AgentInfo(id="a1", name="Agent 1")
        assert info.is_alive(ttl=60)

    def test_is_alive_stale_heartbeat(self):
        info = AgentInfo(id="a1", name="Agent 1", last_heartbeat=time.time() - 120)
        assert not info.is_alive(ttl=60)


class TestAgentRegistry:
    @pytest.mark.asyncio
    async def test_register(self):
        reg = AgentRegistry()
        info = await reg.register("Worker1", role="backend")
        assert info.id is not None
        assert info.role == "backend"
        assert info.status == AgentStatus.STARTING

    @pytest.mark.asyncio
    async def test_register_with_id(self):
        reg = AgentRegistry()
        info = await reg.register_with_id("agent-abc", "NamedAgent", role="reviewer")
        assert info.id == "agent-abc"
        assert info.name == "NamedAgent"

    @pytest.mark.asyncio
    async def test_parent_child_linking(self):
        reg = AgentRegistry()
        parent = await reg.register("Parent", role="coordinator")
        child = await reg.register("Child", parent_id=parent.id, role="worker")
        assert child.parent_id == parent.id
        assert child.id in reg.get(parent.id).child_ids

    @pytest.mark.asyncio
    async def test_heartbeat(self):
        reg = AgentRegistry()
        info = await reg.register("TestAgent")
        old = info.last_heartbeat
        await asyncio.sleep(0.01)
        await reg.heartbeat(info.id)
        assert reg.get(info.id).last_heartbeat >= old

    @pytest.mark.asyncio
    async def test_get_by_role(self):
        reg = AgentRegistry()
        await reg.register("A", role="backend")
        await reg.register("B", role="frontend")
        await reg.register("C", role="backend")
        backend = reg.get_by_role("backend")
        assert len(backend) == 2

    @pytest.mark.asyncio
    async def test_get_by_capability(self):
        reg = AgentRegistry()
        await reg.register("A", capabilities=[AgentCapability.CODE_WRITE, AgentCapability.TERMINAL])
        await reg.register("B", capabilities=[AgentCapability.CODE_READ])
        writers = reg.get_by_capability(AgentCapability.CODE_WRITE)
        assert len(writers) == 1


# ═══════════════════════════════════════════════════════════════════
# MessageBus Tests
# ═══════════════════════════════════════════════════════════════════


class TestMessage:
    def test_is_expired(self):
        msg = Message(
            id="m1", type=MessageType.HEARTBEAT, topic="heartbeat", sender_id="a1", ttl=-1
        )
        assert msg.is_expired()

    def test_roundtrip_dict(self):
        msg = Message(
            id="m1",
            type=MessageType.TASK,
            topic="task.1",
            sender_id="a1",
            payload={"x": 1},
            priority=MessagePriority.HIGH,
        )
        d = msg.to_dict()
        restored = Message.from_dict(d)
        assert restored.id == msg.id
        assert restored.type == msg.type
        assert restored.priority == msg.priority


class TestMessageBus:
    @pytest.mark.asyncio
    async def test_publish_subscribe(self):
        bus = MessageBus()
        await bus.start()
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        await bus.subscribe("topic.*", handler, "sub1")
        await bus.publish("topic.news", sender_id="a1", payload={"msg": "hello"})
        await asyncio.sleep(0.1)
        await bus.stop()

        assert len(received) == 1
        assert received[0].payload["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = MessageBus()
        await bus.start()

        async def handler(msg: Message) -> None:
            pass

        sub_id = await bus.subscribe("topic.*", handler, "sub1")
        await bus.unsubscribe(sub_id)
        await bus.publish("topic.test", sender_id="a1")
        await asyncio.sleep(0.1)
        await bus.stop()
        stats = bus.stats()
        assert stats["subscription_count"] == 0

    @pytest.mark.asyncio
    async def test_wildcard_topic(self):
        bus = MessageBus()
        await bus.start()
        received = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        await bus.subscribe("agent.*", handler, "sub1")
        await bus.publish("agent.frontend.status", sender_id="a1")
        await asyncio.sleep(0.1)
        await bus.stop()
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_priority_order(self):
        bus = MessageBus()
        await bus.start()
        received = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        await bus.subscribe("prio.*", handler, "sub1")
        await bus.publish("prio.low", sender_id="a1", priority=MessagePriority.LOW)
        await bus.publish("prio.high", sender_id="a1", priority=MessagePriority.HIGH)
        await bus.publish("prio.normal", sender_id="a1", priority=MessagePriority.NORMAL)
        await asyncio.sleep(0.15)
        await bus.stop()
        assert len(received) == 3
        assert received[0].topic == "prio.high"
        assert received[1].topic == "prio.normal"

    @pytest.mark.asyncio
    async def test_broadcast(self):
        bus = MessageBus()
        await bus.start()
        received1, received2 = [], []

        async def h1(msg: Message) -> None:
            received1.append(msg)

        async def h2(msg: Message) -> None:
            received2.append(msg)

        await bus.subscribe("broadcast", h1, "sub1")
        await bus.subscribe("broadcast", h2, "sub2")
        await bus.broadcast("broadcast", sender_id="broadcaster", payload={"announcement": "test"})
        await asyncio.sleep(0.1)
        await bus.stop()
        assert len(received1) == 1
        assert len(received2) == 1

    @pytest.mark.asyncio
    async def test_stats(self):
        bus = MessageBus()
        await bus.start()
        await bus.subscribe("stats.test", lambda m: None, "sub1")
        stats = bus.stats()
        await bus.stop()
        assert "subscription_count" in stats
        assert "queue_size" in stats
