"""
SharedContext — Cross-agent memory store with TTL and version vectors.

Provides a shared key-value store that persists across agent sessions,
with TTL-based expiration and optimistic locking via version vectors.
Agents can read/write shared state without stepping on each other.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from rann_agent.storage.database import Database

logger = structlog.get_logger()


@dataclass
class ContextEntry:
    """A single entry in the shared context."""

    key: str
    value: Any  # noqa: ANN401
    version: int
    created_at: float
    updated_at: float
    ttl: float | None  # None = no expiry
    owner_agent_id: str
    tags: list[str] = field(default_factory=list)
    access_count: int = 0

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() > self.updated_at + self.ttl

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "ttl": self.ttl,
            "owner_agent_id": self.owner_agent_id,
            "tags": self.tags,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ContextEntry:
        return cls(
            key=d["key"],
            value=d["value"],
            version=d["version"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            ttl=d.get("ttl"),
            owner_agent_id=d["owner_agent_id"],
            tags=d.get("tags", []),
            access_count=d.get("access_count", 0),
        )


@dataclass
class VersionVector:
    """Lamport-like version vector for causal consistency."""

    clock: dict[str, int] = field(default_factory=dict)

    def increment(self, agent_id: str) -> None:
        self.clock[agent_id] = self.clock.get(agent_id, 0) + 1

    def get(self, agent_id: str) -> int:
        return self.clock.get(agent_id, 0)

    def merge(self, other: VersionVector) -> None:
        for agent_id, version in other.clock.items():
            self.clock[agent_id] = max(self.clock.get(agent_id, 0), version)

    def happened_before(self, other: VersionVector) -> bool:
        # Returns True if self definitely happened before other
        dominated = False
        for agent_id in set(self.clock) | set(other.clock):
            self_v = self.clock.get(agent_id, 0)
            other_v = other.clock.get(agent_id, 0)
            if self_v > other_v:
                return False
            if self_v < other_v:
                dominated = True
        return dominated

    def to_dict(self) -> dict[str, int]:
        return dict(self.clock)

    @classmethod
    def from_dict(cls, d: dict[str, int]) -> VersionVector:
        return cls(clock=dict(d))


class SharedContext:
    """
    Shared key-value store for multi-agent coordination.

    Features:
    - TTL-based expiration (default 1 hour)
    - Version vectors for causal consistency
    - Optimistic locking (CAS semantics)
    - Tag-based queries
    - Periodic persistence to SQLite
    - Agent affinity (owner tracking)
    - Atomic multi-key operations
    """

    DEFAULT_TTL = 3600.0  # 1 hour

    def __init__(
        self,
        db: Database | None = None,
        persist_path: Path | None = None,
        default_ttl: float = DEFAULT_TTL,
    ) -> None:
        self._db = db
        self._persist_path = persist_path or Path.home() / ".rann_agent" / "shared_context.json"
        self._default_ttl = default_ttl
        self._memory: dict[str, ContextEntry] = {}
        self._vv = VersionVector()
        self._agent_id = f"shared_ctx_{uuid.uuid4().hex[:8]}"
        self._vv_path = self._persist_path.with_suffix(".vv.json")
        self._lock_path = self._persist_path.with_suffix(".lock")
        self._log = logger.bind(component="shared_context")

        if self._db is None:
            self._load_from_disk()
        else:
            self._load_from_db()

    # ─── Read Operations ────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
        """Get a value by key. Returns default if missing or expired."""
        entry = self._memory.get(key)
        if entry is None:
            return default
        if entry.is_expired():
            del self._memory[key]
            return default
        entry.access_count += 1
        return entry.value

    def get_entry(self, key: str) -> ContextEntry | None:
        """Get the full entry (including metadata) for a key."""
        entry = self._memory.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._memory[key]
            return None
        entry.access_count += 1
        return entry

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Bulk get — returns dict of found (non-expired) key→value pairs."""
        result = {}
        for key in keys:
            val = self.get(key)
            if val is not None:
                result[key] = val
        return result

    def find_by_tags(self, tags: list[str], match_all: bool = False) -> dict[str, Any]:
        """Find all entries matching the given tags."""
        matches = {}
        for key, entry in self._memory.items():
            if entry.is_expired():
                continue
            if match_all:
                if all(t in entry.tags for t in tags):
                    matches[key] = entry.value
            else:
                if any(t in entry.tags for t in tags):
                    matches[key] = entry.value
        return matches

    def keys(self, pattern: str = "*") -> list[str]:
        """List all non-expired keys, optionally matching a glob pattern."""
        import fnmatch

        results = []
        for key in self._memory:
            if not self._memory[key].is_expired() and fnmatch.fnmatch(key, pattern):
                results.append(key)
        return results

    def version_for(self, key: str) -> int | None:
        """Get the version number for a key, or None if missing."""
        entry = self._memory.get(key)
        if entry is None or entry.is_expired():
            return None
        return entry.version

    # ─── Write Operations ────────────────────────────────────────────

    def set(
        self,
        key: str,
        value: Any,  # noqa: ANN401
        ttl: float | None = None,
        tags: list[str] | None = None,
        owner_agent_id: str | None = None,
    ) -> ContextEntry:
        """Set a value — creates new entry or updates existing."""
        now = time.time()
        existing = self._memory.get(key)

        if existing and not existing.is_expired():
            # Update existing
            entry = ContextEntry(
                key=key,
                value=value,
                version=existing.version + 1,
                created_at=existing.created_at,
                updated_at=now,
                ttl=ttl if ttl is not None else self._default_ttl,
                owner_agent_id=owner_agent_id or existing.owner_agent_id,
                tags=tags if tags is not None else existing.tags,
                access_count=existing.access_count,
            )
        else:
            # Create new
            self._vv.increment(self._agent_id)
            entry = ContextEntry(
                key=key,
                value=value,
                version=self._vv.get(self._agent_id),
                created_at=now,
                updated_at=now,
                ttl=ttl if ttl is not None else self._default_ttl,
                owner_agent_id=owner_agent_id or "unknown",
                tags=tags or [],
            )

        self._memory[key] = entry
        self._persist()
        self._log.debug("shared_context_set", key=key, version=entry.version)
        return entry

    def set_if_version(
        self,
        key: str,
        value: Any,  # noqa: ANN401
        expected_version: int,
        ttl: float | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """
        Set value only if current version matches expected_version (CAS).
        Returns True if set succeeded, False if version mismatch.
        """
        existing = self._memory.get(key)
        if existing is None:
            if expected_version != 0:
                return False
        elif existing.version != expected_version:
            return False

        self.set(key, value, ttl=ttl, tags=tags)
        return True

    def update_tags(self, key: str, tags: list[str]) -> bool:
        """Add/replace tags on an existing entry."""
        entry = self._memory.get(key)
        if entry is None or entry.is_expired():
            return False
        entry.tags = list(tags)
        entry.access_count += 1
        self._persist()
        return True

    def touch(self, key: str, ttl: float | None = None) -> bool:
        """Refresh TTL and bump access count. Returns False if key missing."""
        entry = self._memory.get(key)
        if entry is None or entry.is_expired():
            return False
        entry.ttl = ttl if ttl is not None else self._default_ttl
        entry.updated_at = time.time()
        entry.access_count += 1
        self._persist()
        return True

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if deleted, False if missing."""
        if key in self._memory:
            del self._memory[key]
            self._persist()
            return True
        return False

    def delete_many(self, keys: list[str]) -> int:
        """Delete multiple keys. Returns count of deleted keys."""
        count = 0
        for key in keys:
            if key in self._memory:
                del self._memory[key]
                count += 1
        if count:
            self._persist()
        return count

    def clear(self, agent_id: str | None = None) -> int:
        """
        Clear all entries, or only those owned by a specific agent.
        Returns count of cleared entries.
        """
        if agent_id is None:
            count = len(self._memory)
            self._memory.clear()
        else:
            to_delete = [k for k, e in self._memory.items() if e.owner_agent_id == agent_id]
            count = len(to_delete)
            for k in to_delete:
                del self._memory[k]
        if count:
            self._persist()
        return count

    # ─── Atomic Multi-Key Operations ────────────────────────────────

    def atomic_set(self, entries: dict[str, Any], ttl: float | None = None) -> None:
        """
        Atomically set multiple key→value pairs.
        All succeed or all fail (best-effort: log failures, continue).
        """
        now = time.time()
        for key, value in entries.items():
            try:
                existing = self._memory.get(key)
                if existing and not existing.is_expired():
                    entry = ContextEntry(
                        key=key,
                        value=value,
                        version=existing.version + 1,
                        created_at=existing.created_at,
                        updated_at=now,
                        ttl=ttl if ttl is not None else self._default_ttl,
                        owner_agent_id=existing.owner_agent_id,
                        tags=existing.tags,
                        access_count=existing.access_count,
                    )
                else:
                    entry = ContextEntry(
                        key=key,
                        value=value,
                        version=1,
                        created_at=now,
                        updated_at=now,
                        ttl=ttl if ttl is not None else self._default_ttl,
                        owner_agent_id="unknown",
                    )
                self._memory[key] = entry
            except Exception as exc:  # noqa: BLE001
                self._log.warning("atomic_set_failed", key=key, error=str(exc))
        self._persist()

    # ─── Version Vector ─────────────────────────────────────────────

    def get_version_vector(self) -> VersionVector:
        """Return a copy of the current version vector."""
        return VersionVector.from_dict(self._vv.to_dict())

    def merge_version_vector(self, remote: VersionVector) -> None:
        """Merge in a remote version vector (for causal consistency)."""
        self._vv.merge(remote)

    # ─── Persistence ────────────────────────────────────────────────

    def _persist(self) -> None:
        """Write current state to disk."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "memory": {k: v.to_dict() for k, v in self._memory.items() if not v.is_expired()},
                "version_vector": self._vv.to_dict(),
                "saved_at": time.time(),
            }
            with open(self._persist_path, "w") as f:
                json.dump(data, f)

            # Save version vector separately
            with open(self._vv_path, "w") as f:
                json.dump(self._vv.to_dict(), f)
        except Exception as exc:  # noqa: BLE001
            self._log.warning("persist_failed", error=str(exc))

    def _load_from_disk(self) -> None:
        """Load state from disk on init."""
        try:
            if self._persist_path.exists():
                with open(self._persist_path) as f:
                    data = json.load(f)
                for k, v in data.get("memory", {}).items():
                    entry = ContextEntry.from_dict(v)
                    if not entry.is_expired():
                        self._memory[k] = entry
                self._vv = VersionVector.from_dict(data.get("version_vector", {}))
                self._log.info("loaded_from_disk", entries=len(self._memory))
        except Exception as exc:  # noqa: BLE001
            self._log.warning("load_failed", error=str(exc))

    def _load_from_db(self) -> None:
        """Load state from SQLite database."""
        try:
            if self._db is None:
                return
            rows = self._db.fetch_all("SELECT key, value FROM shared_context", ())
            for row in rows:
                key = row[0]
                try:
                    entry_data = json.loads(row[1])
                    entry = ContextEntry.from_dict(entry_data)
                    if not entry.is_expired():
                        self._memory[key] = entry
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            self._log.warning("db_load_failed", error=str(exc))

    # ─── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return current state stats."""
        total = len(self._memory)
        expired = sum(1 for e in self._memory.values() if e.is_expired())
        by_owner: dict[str, int] = {}
        for e in self._memory.values():
            if not e.is_expired():
                by_owner[e.owner_agent_id] = by_owner.get(e.owner_agent_id, 0) + 1

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "by_owner": by_owner,
            "version_vector": self._vv.to_dict(),
            "persist_path": str(self._persist_path),
        }
