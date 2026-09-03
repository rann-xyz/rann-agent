"""
Task Graph

Explicit dependency graph for multi-step task decomposition.
As required by MASTER PROMPT Section 12.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum
import structlog

logger = structlog.get_logger()


class TaskStatus(Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskNode:
    """A node in the task graph"""
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Dependencies
    dependencies: Set[str] = field(default_factory=set)  # task_ids this depends on
    dependents: Set[str] = field(default_factory=set)    # task_ids that depend on this
    
    # Execution
    assigned_to: Optional[str] = None  # agent_id or None for main
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Callbacks
    on_complete: Optional[Callable] = None
    on_fail: Optional[Callable] = None
    
    def can_execute(self) -> bool:
        """Check if this task can be executed"""
        return self.status in {TaskStatus.READY, TaskStatus.PENDING}
    
    def is_terminal(self) -> bool:
        """Check if this task is in a terminal state"""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED}


class TaskGraph:
    """
    Manages a task dependency graph with parallel execution support.
    
    Features:
    - Explicit dependency declarations
    - Automatic ready-state computation
    - Parallel task scheduling
    - Progress tracking
    - Retry logic
    """
    
    def __init__(self, graph_id: str, root_task_id: str = "root"):
        self.graph_id = graph_id
        self.tasks: Dict[str, TaskNode] = {}
        self.root_task_id = root_task_id
        self._execution_order: List[str] = []
        self._log = structlog.get_logger().bind(component="task_graph", graph_id=graph_id)
        
        # Create root task
        self.add_task(
            task_id=root_task_id,
            description="Root task",
            priority=TaskPriority.CRITICAL
        )
    
    def add_task(
        self,
        task_id: str,
        description: str,
        dependencies: Optional[List[str]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        input_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        **kwargs
    ) -> TaskNode:
        """Add a task to the graph"""
        if task_id in self.tasks:
            raise ValueError(f"Task {task_id} already exists")
        
        task = TaskNode(
            task_id=task_id,
            description=description,
            priority=priority,
            dependencies=set(dependencies or []),
            input_data=input_data or {},
            max_retries=max_retries,
            **kwargs
        )
        
        self.tasks[task_id] = task
        
        # Update dependents for dependencies
        for dep_id in task.dependencies:
            if dep_id in self.tasks:
                self.tasks[dep_id].dependents.add(task_id)
            else:
                self._log.warning("dependency_not_found", task_id=task_id, dep_id=dep_id)
        
        self._update_task_status(task_id)
        self._log.info("task_added", task_id=task_id, dependencies=list(dependencies or []))
        
        return task
    
    def get_task(self, task_id: str) -> Optional[TaskNode]:
        """Get a task by ID"""
        return self.tasks.get(task_id)
    
    def get_ready_tasks(self) -> List[TaskNode]:
        """Get all tasks that are ready to execute"""
        ready = []
        for task in self.tasks.values():
            if task.can_execute() and self._all_dependencies_met(task):
                ready.append(task)
        
        # Sort by priority (highest first)
        ready.sort(key=lambda t: t.priority.value, reverse=True)
        return ready
    
    def _all_dependencies_met(self, task: TaskNode) -> bool:
        """Check if all dependencies are satisfied"""
        for dep_id in task.dependencies:
            dep = self.tasks.get(dep_id)
            if not dep or not dep.is_terminal():
                return False
            if dep.status == TaskStatus.FAILED:
                return False  # Don't execute if any dependency failed
            if dep.status != TaskStatus.COMPLETED:
                return False
        return True
    
    def _update_task_status(self, task_id: str) -> None:
        """Update task status based on dependencies"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        if task.is_terminal():
            return
        
        if not self._all_dependencies_met(task):
            task.status = TaskStatus.BLOCKED
        else:
            task.status = TaskStatus.READY
    
    def mark_running(self, task_id: str) -> None:
        """Mark a task as running"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = TaskStatus.RUNNING
        task.started_at = self._now()
        self._log.info("task_started", task_id=task_id)
    
    def mark_completed(self, task_id: str, output_data: Optional[Dict[str, Any]] = None) -> None:
        """Mark a task as completed"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = self._now()
        if output_data:
            task.output_data = output_data
        
        self._log.info("task_completed", task_id=task_id)
        
        # Update dependent tasks
        for dep_id in task.dependents:
            self._update_task_status(dep_id)
        
        # Trigger callback
        if task.on_complete:
            try:
                task.on_complete(task)
            except Exception as e:
                self._log.error("task_complete_callback_failed", task_id=task_id, error=str(e))
    
    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.retry_count += 1
        task.error = error
        
        if task.retry_count < task.max_retries:
            task.status = TaskStatus.READY  # Allow retry
            self._log.warning("task_retry", task_id=task_id, retry=task.retry_count)
        else:
            task.status = TaskStatus.FAILED
            task.completed_at = self._now()
            self._log.error("task_failed", task_id=task_id, error=error, retries=task.retry_count)
            
            # Mark dependents as blocked/failed
            for dep_id in task.dependents:
                dep = self.tasks.get(dep_id)
                if dep and not dep.is_terminal():
                    dep.status = TaskStatus.BLOCKED
    
    def mark_skipped(self, task_id: str) -> None:
        """Mark a task as skipped"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = TaskStatus.SKIPPED
        task.completed_at = self._now()
        self._log.info("task_skipped", task_id=task_id)
        
        # Update dependents
        for dep_id in task.dependents:
            self._update_task_status(dep_id)
    
    def is_complete(self) -> bool:
        """Check if the graph is complete"""
        return self.root_task_id in self.tasks and self.tasks[self.root_task_id].is_terminal()
    
    def get_progress(self) -> Dict[str, Any]:
        """Get progress summary"""
        total = len(self.tasks)
        if total == 0:
            return {"total": 0, "completed": 0, "failed": 0, "running": 0, "pending": 0, "blocked": 0}
        
        counts = {s: 0 for s in TaskStatus}
        for task in self.tasks.values():
            counts[task.status] += 1
        
        return {
            "total": total,
            "completed": counts[TaskStatus.COMPLETED],
            "failed": counts[TaskStatus.FAILED],
            "running": counts[TaskStatus.RUNNING],
            "pending": counts[TaskStatus.PENDING],
            "blocked": counts[TaskStatus.BLOCKED],
            "skipped": counts[TaskStatus.SKIPPED],
            "percent_complete": (counts[TaskStatus.COMPLETED] / total) * 100
        }
    
    def get_execution_plan(self) -> List[str]:
        """Get a topological order of tasks ready for execution"""
        if self._execution_order:
            return self._execution_order
        
        # Simple topological sort
        visited = set()
        order = []
        
        def visit(task_id: str):
            if task_id in visited:
                return
            visited.add(task_id)
            
            task = self.tasks.get(task_id)
            if task:
                for dep_id in task.dependencies:
                    visit(dep_id)
                order.append(task_id)
        
        visit(self.root_task_id)
        self._execution_order = order
        return order
    
    def get_subgraph(self, task_ids: Set[str]) -> "TaskGraph":
        """Extract a subgraph containing only the specified tasks"""
        subgraph = TaskGraph(f"{self.graph_id}_subgraph")
        
        for task_id in task_ids:
            task = self.tasks.get(task_id)
            if task:
                # Filter dependencies to only those in the subgraph
                deps = task.dependencies & task_ids
                subgraph.add_task(
                    task_id=task.task_id,
                    description=task.description,
                    dependencies=list(deps),
                    priority=task.priority,
                    input_data=task.input_data.copy(),
                    max_retries=task.max_retries
                )
        
        return subgraph
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "graph_id": self.graph_id,
            "root_task_id": self.root_task_id,
            "tasks": {
                tid: {
                    "task_id": t.task_id,
                    "description": t.description,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "dependencies": list(t.dependencies),
                    "dependents": list(t.dependents),
                    "assigned_to": t.assigned_to,
                    "output_data": t.output_data,
                    "error": t.error,
                    "retry_count": t.retry_count
                }
                for tid, t in self.tasks.items()
            },
            "progress": self.get_progress()
        }
    
    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().isoformat()