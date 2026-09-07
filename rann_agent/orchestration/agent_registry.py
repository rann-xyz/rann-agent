"""
AgentRegistry — Tracks and manages dynamic agent lifecycle.

Maintains a registry of active agents with their state, capabilities,
resource usage, and parent-child relationships. Enables dynamic spawning,
monitoring, and cleanup of sub-agents.
"""

from __future__ import annotations

import asyncio
import signal
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class AgentStatus(Enum):
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class AgentCapability(Enum):
    CODE_WRITE = "code_write"
    CODE_READ = "code_read"
    TERMINAL = "terminal"
    WEB_SEARCH = "web_search"
    FILE_DELETE = "file_delete"
    DEPLOY = "deploy"
    TEST = "test"
    REVIEW = "review"
    DEBUG = "debug"


@dataclass
class AgentInfo:
    """Information about a registered agent."""

    id: str
    name: str
    status: AgentStatus = AgentStatus.STARTING
    parent_id: str | None = None
    child_ids: list[str] = field(default_factory=list)
    role: str = "generalist"  # e.g., "backend", "frontend", "devops", "reviewer"
    capabilities: list[AgentCapability] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    current_task: str | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    token_usage: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_alive(self, ttl: float = 60.0) -> bool:
        """Check if agent is still alive (recent heartbeat)."""
        return time.time() - self.last_heartbeat < ttl

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "role": self.role,
            "capabilities": [c.value for c in self.capabilities],
            "created_at": self.created_at,
            "last_heartbeat": self.last_heartbeat,
            "current_task": self.current_task,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "token_usage": self.token_usage,
            "metadata": self.metadata,
        }


@dataclass
class AgentRegistry:
    """
    Central registry for all active agents in a multi-agent session.

    Features:
    - Register/deregister agents with unique IDs
    - Parent-child relationship tracking
    - Heartbeat monitoring (detect stale agents)
    - Capability-based agent lookup
    - Resource usage tracking
    - Cascading termination (kill children when parent dies)
    - Role-based agent assignment
    """

    def __init__(self, heartbeat_ttl: float = 60.0) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._heartbeat_ttl = heartbeat_ttl
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._log = logger.bind(component="agent_registry")
        self._lock = asyncio.Lock()

    # ─── Registration ─────────────────────────────────────────────

    async def register(
        self,
        name: str,
        parent_id: str | None = None,
        role: str = "generalist",
        capabilities: list[AgentCapability] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentInfo:
        """Register a new agent and return its info."""
        async with self._lock:
            agent_id = uuid.uuid4().hex[:12]
            info = AgentInfo(
                id=agent_id,
                name=name,
                parent_id=parent_id,
                role=role,
                capabilities=capabilities or [],
                metadata=metadata or {},
            )
            self._agents[agent_id] = info

            # Link to parent
            if parent_id and parent_id in self._agents:
                self._agents[parent_id].child_ids.append(agent_id)

            self._log.info("agent_registered", agent_id=agent_id, name=name, role=role)
            return info

    async def register_with_id(
        self,
        agent_id: str,
        name: str,
        parent_id: str | None = None,
        role: str = "generalist",
        capabilities: list[AgentCapability] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentInfo:
        """Register with a specific agent ID (for deterministic IDs)."""
        async with self._lock:
            info = AgentInfo(
                id=agent_id,
                name=name,
                parent_id=parent_id,
                role=role,
                capabilities=capabilities or [],
                metadata=metadata or {},
            )
            self._agents[agent_id] = info
            if parent_id and parent_id in self._agents:
                self._agents[parent_id].child_ids.append(agent_id)
            self._log.info("agent_registered", agent_id=agent_id, name=name, role=role)
            return info

    async def deregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        async with self._lock:
            if agent_id not in self._agents:
                return False

            info = self._agents[agent_id]

            # Remove from parent's child list
            if info.parent_id and info.parent_id in self._agents:
                if agent_id in self._agents[info.parent_id].child_ids:
                    self._agents[info.parent_id].child_ids.remove(agent_id)

            # Kill children recursively
            for child_id in list(info.child_ids):
                await self.deregister(child_id)

            # Terminate subprocess if any
            if agent_id in self._processes:
                try:
                    self._processes[agent_id].terminate()
                    del self._processes[agent_id]
                except Exception:  # noqa: BLE001
                    pass

            del self._agents[agent_id]
            self._log.info("agent_deregistered", agent_id=agent_id)
            return True

    # ─── Status Updates ───────────────────────────────────────────

    async def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Update agent status."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id].status = status
            return True

    async def heartbeat(self, agent_id: str) -> bool:
        """Update agent's last heartbeat timestamp."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id].last_heartbeat = time.time()
            return True

    async def set_task(self, agent_id: str, task: str | None) -> bool:
        """Set the current task for an agent."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id].current_task = task
            if task:
                self._agents[agent_id].status = AgentStatus.BUSY
            return True

    async def increment_completed(self, agent_id: str) -> bool:
        """Increment tasks_completed counter."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id].tasks_completed += 1
            return True

    async def increment_failed(self, agent_id: str) -> bool:
        """Increment tasks_failed counter."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id].tasks_failed += 1
            return True

    async def add_token_usage(self, agent_id: str, tokens: int) -> bool:
        """Add to token usage counter."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id].token_usage += tokens
            return True

    # ─── Queries ──────────────────────────────────────────────────

    def get(self, agent_id: str) -> AgentInfo | None:
        """Get agent info by ID."""
        return self._agents.get(agent_id)

    def get_all(self) -> list[AgentInfo]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_by_role(self, role: str) -> list[AgentInfo]:
        """Get all agents with a specific role."""
        return [a for a in self._agents.values() if a.role == role]

    def get_by_capability(self, capability: AgentCapability) -> list[AgentInfo]:
        """Get all agents with a specific capability."""
        return [a for a in self._agents.values() if capability in a.capabilities]

    def get_by_status(self, status: AgentStatus) -> list[AgentInfo]:
        """Get all agents with a specific status."""
        return [a for a in self._agents.values() if a.status == status]

    def get_children(self, agent_id: str) -> list[AgentInfo]:
        """Get all direct child agents."""
        info = self._agents.get(agent_id)
        if info is None:
            return []
        return [self._agents[cid] for cid in info.child_ids if cid in self._agents]

    def get_parent(self, agent_id: str) -> AgentInfo | None:
        """Get the parent agent."""
        info = self._agents.get(agent_id)
        if info is None or info.parent_id is None:
            return None
        return self._agents.get(info.parent_id)

    def get_idle_agents(self, role: str | None = None) -> list[AgentInfo]:
        """Get all idle agents, optionally filtered by role."""
        idle = [a for a in self._agents.values() if a.status == AgentStatus.IDLE]
        if role:
            idle = [a for a in idle if a.role == role]
        return idle

    # ─── Monitoring ───────────────────────────────────────────────

    def get_stale_agents(self) -> list[AgentInfo]:
        """Get agents that have missed their heartbeat."""
        return [a for a in self._agents.values() if not a.is_alive(self._heartbeat_ttl)]

    def cleanup_stale_agents(self) -> list[str]:
        """Remove stale agents and return their IDs."""
        stale = self.get_stale_agents()
        cleaned: list[str] = []
        for agent in stale:
            # Don't remove if still has active children
            if not agent.child_ids:
                asyncio.create_task(self.deregister(agent.id))
                cleaned.append(agent.id)
        if cleaned:
            self._log.info("stale_agents_cleaned", count=len(cleaned), ids=cleaned)
        return cleaned

    def stats(self) -> dict[str, Any]:
        """Return registry statistics."""
        by_status: dict[str, int] = {}
        by_role: dict[str, int] = {}
        total_tokens = 0

        for agent in self._agents.values():
            by_status[agent.status.value] = by_status.get(agent.status.value, 0) + 1
            by_role[agent.role] = by_role.get(agent.role, 0) + 1
            total_tokens += agent.token_usage

        return {
            "total_agents": len(self._agents),
            "by_status": by_status,
            "by_role": by_role,
            "total_token_usage": total_tokens,
            "stale_agents": len(self.get_stale_agents()),
        }
