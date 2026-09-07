"""
TaskGraph — DAG-based task decomposition with dependency resolution.

Breaks complex tasks into a directed acyclic graph of subtasks,
resolves dependencies, identifies critical path, and enables
parallel execution by independent agents.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog


class TaskStatus(Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskNode:
    """A single node (subtask) in the task graph."""

    id: str
    name: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    assigned_agent: str | None = None
    dependencies: list[str] = field(default_factory=list)  # task IDs this depends on
    dependents: list[str] = field(default_factory=list)  # task IDs that depend on this
    result: Any = None  # noqa: ANN401
    error: str | None = None
    estimated_duration: float | None = None  # seconds
    actual_duration: float | None = None
    started_at: float | None = None
    completed_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_ready(self) -> bool:
        return self.status == TaskStatus.PENDING and not self.dependencies

    def can_run(self, completed_ids: set[str]) -> bool:
        if self.status != TaskStatus.PENDING:
            return False
        return all(dep in completed_ids for dep in self.dependencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "assigned_agent": self.assigned_agent,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "result": self.result,
            "error": self.error,
            "estimated_duration": self.estimated_duration,
            "actual_duration": self.actual_duration,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TaskNode:
        return cls(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            status=TaskStatus(d.get("status", "pending")),
            priority=TaskPriority(d.get("priority", 1)),
            assigned_agent=d.get("assigned_agent"),
            dependencies=d.get("dependencies", []),
            dependents=d.get("dependents", []),
            result=d.get("result"),
            error=d.get("error"),
            estimated_duration=d.get("estimated_duration"),
            actual_duration=d.get("actual_duration"),
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            metadata=d.get("metadata", {}),
        )


@dataclass
class TaskGraph:
    """
    Directed Acyclic Graph of tasks with dependency management.

    Usage:
        graph = TaskGraph()
        graph.add_task("a", "Task A")
        graph.add_task("b", "Task B", dependencies=["a"])
        graph.add_task("c", "Task C", dependencies=["a"])
        graph.add_task("d", "Task D", dependencies=["b", "c"])
        graph.validate()  # raises if cycle detected
        ready = graph.get_ready_tasks()  # returns ["a"]
    """

    tasks: dict[str, TaskNode] = field(default_factory=dict)
    root_id: str | None = None
    _log: Any = field(
        default_factory=lambda: structlog.get_logger().bind(component="task_graph"), repr=False
    )  # noqa: E501

    def add_task(
        self,
        task_id: str,
        name: str,
        description: str = "",
        dependencies: list[str] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        estimated_duration: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskNode:
        """Add a task node to the graph."""
        if task_id in self.tasks:
            raise ValueError(f"Task {task_id!r} already exists in graph")

        node = TaskNode(
            id=task_id,
            name=name,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            estimated_duration=estimated_duration,
            metadata=metadata or {},
        )

        # Validate dependencies exist
        for dep_id in node.dependencies:
            if dep_id not in self.tasks and dep_id != task_id:
                self._log.warning("unknown_dependency", task=task_id, dependency=dep_id)

        self.tasks[task_id] = node
        self._update_dependents(task_id)
        # Also update dependents lists of all dependencies (they now have a new dependent)
        for dep_id in node.dependencies:
            if dep_id in self.tasks:
                self._update_dependents(dep_id)
        return node

    def add_task_auto_id(
        self,
        name: str,
        description: str = "",
        dependencies: list[str] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        estimated_duration: float | None = None,
    ) -> TaskNode:
        """Add a task with an auto-generated UUID."""
        task_id = uuid.uuid4().hex[:8]
        return self.add_task(task_id, name, description, dependencies, priority, estimated_duration)

    def link(self, from_task: str, to_task: str) -> None:
        """Add a dependency: to_task depends on from_task."""
        if from_task not in self.tasks:
            raise KeyError(f"Task {from_task!r} not found in graph")
        if to_task not in self.tasks:
            raise KeyError(f"Task {to_task!r} not found in graph")

        if from_task not in self.tasks[to_task].dependencies:
            self.tasks[to_task].dependencies.append(from_task)
        if to_task not in self.tasks[from_task].dependents:
            self.tasks[from_task].dependents.append(to_task)

    def remove_task(self, task_id: str) -> None:
        """Remove a task and clean up dependency references."""
        if task_id not in self.tasks:
            return
        node = self.tasks[task_id]

        # Remove from dependents of dependencies
        for dep_id in node.dependencies:
            if dep_id in self.tasks:
                if task_id in self.tasks[dep_id].dependents:
                    self.tasks[dep_id].dependents.remove(task_id)

        # Remove from dependencies of dependents
        for dep_id in node.dependents:
            if dep_id in self.tasks:
                if task_id in self.tasks[dep_id].dependencies:
                    self.tasks[dep_id].dependencies.remove(task_id)

        del self.tasks[task_id]

    def validate(self) -> bool:
        """
        Validate the graph — checks for cycles and missing dependencies.
        Raises ValueError if invalid.
        """
        # Check for cycles using DFS
        self._detect_cycles()

        # Check for missing dependencies
        for task_id, node in self.tasks.items():
            for dep_id in node.dependencies:
                if dep_id not in self.tasks:
                    raise ValueError(f"Task {task_id!r} depends on unknown task {dep_id!r}")

        return True

    def _detect_cycles(self) -> None:
        """Detect cycles using DFS. Raises ValueError on cycle."""
        WHITE, GREY, BLACK = 0, 1, 2
        color: dict[str, int] = {tid: WHITE for tid in self.tasks}

        def dfs(tid: str) -> None:
            color[tid] = GREY
            for dep in self.tasks[tid].dependencies:
                if color.get(dep, WHITE) == GREY:
                    raise ValueError(f"Cycle detected involving task {tid!r}")
                if color.get(dep, WHITE) == WHITE:
                    dfs(dep)
            color[tid] = BLACK

        for tid in self.tasks:
            if color[tid] == WHITE:
                dfs(tid)

    def _update_dependents(self, task_id: str) -> None:
        """Rebuild the dependents list FOR task_id (tasks that depend on it)."""
        self.tasks[task_id].dependents = [
            tid for tid, node in self.tasks.items() if task_id in node.dependencies
        ]

    # ─── Query Methods ─────────────────────────────────────────────

    def get_ready_tasks(self) -> list[TaskNode]:
        """Get all tasks that are ready to run (no pending dependencies)."""
        completed_ids = {tid for tid, n in self.tasks.items() if n.status == TaskStatus.COMPLETED}
        ready = []
        for tid, node in self.tasks.items():
            if node.can_run(completed_ids):
                ready.append(node)
        # Sort by priority descending, then by estimated_duration
        ready.sort(key=lambda n: (-n.priority.value, n.estimated_duration or 0))
        return ready

    def get_running_tasks(self) -> list[TaskNode]:
        """Get all currently running tasks."""
        return [n for n in self.tasks.values() if n.status == TaskStatus.RUNNING]

    def get_completed_tasks(self) -> list[TaskNode]:
        """Get all completed tasks."""
        return [n for n in self.tasks.values() if n.status == TaskStatus.COMPLETED]

    def get_failed_tasks(self) -> list[TaskNode]:
        """Get all failed tasks."""
        return [n for n in self.tasks.values() if n.status == TaskStatus.FAILED]

    def get_blocked_tasks(self) -> list[TaskNode]:
        """Get tasks that are blocked (had dependencies that failed)."""
        blocked = []
        for node in self.tasks.values():
            if node.status == TaskStatus.PENDING:
                failed_deps = [
                    dep
                    for dep in node.dependencies
                    if dep in self.tasks and self.tasks[dep].status == TaskStatus.FAILED
                ]
                if failed_deps:
                    node.status = TaskStatus.BLOCKED
                    node.error = f"Blocked by failed dependencies: {failed_deps}"
                    blocked.append(node)
        return blocked

    def get_critical_path(self) -> list[str]:
        """
        Get the critical path (longest chain of tasks through the graph).
        Returns list of task IDs in execution order.
        """
        if not self.tasks:
            return []

        # Topological sort
        topo = self._topological_sort()

        # Longest path (by estimated_duration)
        dist: dict[str, float] = {}
        prev: dict[str, str | None] = {}

        for tid in topo:
            dist[tid] = self.tasks[tid].estimated_duration or 0
            prev[tid] = None

        for tid in topo:
            for dep_id in self.tasks[tid].dependencies:
                path_len = dist[dep_id] + (self.tasks[tid].estimated_duration or 0)
                if path_len > dist[tid]:
                    dist[tid] = path_len
                    prev[tid] = dep_id

        # Find the end of the longest path
        end = max(dist, key=lambda t: dist[t])

        # Reconstruct path
        path = []
        current: str | None = end
        while current is not None:
            path.append(current)
            current = prev[current]
        path.reverse()
        return path

    def _topological_sort(self) -> list[str]:
        """Return tasks in topological order (dependencies first)."""
        in_degree: dict[str, int] = {tid: len(n.dependencies) for tid, n in self.tasks.items()}
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            tid = queue.pop(0)
            result.append(tid)
            for dep_id in self.tasks[tid].dependents:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    queue.append(dep_id)

        if len(result) != len(self.tasks):
            raise ValueError("Topological sort failed — cycle detected")
        return result

    def get_parallel_batches(self) -> list[list[str]]:
        """
        Get task IDs grouped into batches that can run in parallel.
        Each batch contains tasks with no inter-dependencies.
        """
        self.validate()
        batches: list[list[str]] = []
        remaining = set(self.tasks.keys())
        completed: set[str] = set()

        while remaining:
            # Find tasks with all dependencies satisfied
            batch = []
            for tid in sorted(remaining):
                node = self.tasks[tid]
                if node.status != TaskStatus.PENDING:
                    continue
                if all(dep in completed for dep in node.dependencies):
                    batch.append(tid)

            if not batch:
                # Deadlock — remaining tasks have unmet dependencies
                break

            batches.append(batch)
            for tid in batch:
                remaining.discard(tid)
                completed.add(tid)

        return batches

    def is_complete(self) -> bool:
        """Check if all tasks are complete (or failed/skipped)."""
        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED}
        return all(n.status in terminal for n in self.tasks.values())

    def summary(self) -> dict[str, Any]:
        """Return a summary dict of the graph state."""
        by_status: dict[str, int] = {}
        for node in self.tasks.values():
            by_status[node.status.value] = by_status.get(node.status.value, 0) + 1

        return {
            "total_tasks": len(self.tasks),
            "by_status": by_status,
            "critical_path": self.get_critical_path(),
            "parallel_batches": len(self.get_parallel_batches()),
            "is_valid": True,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a dict."""
        return {
            "tasks": {tid: node.to_dict() for tid, node in self.tasks.items()},
            "root_id": self.root_id,
        }
