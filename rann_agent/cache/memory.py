"""
In-memory cache backend.

Default cache backend — no external dependencies, no setup required.
Thread-safe using a dictionary with a lock. Entries expire based on TTL.
"""
import asyncio
import threading
import time
from typing import Any, Optional

from rann_agent.cache.backend import CacheBackend, TTLCacheMixin


class InMemoryCache(CacheBackend, TTLCacheMixin):
    """
    Thread-safe in-memory cache with TTL support.

    Uses a dict with a reentrant lock. Expired entries are lazily
    pruned on access (not in the background).

    Suitable for single-instance deployments. For multi-process
    or distributed setups, use RedisCache instead.
    """

    def __init__(self, *, max_size: int = 10000):
        self._store: dict[str, tuple[Any, Optional[float]]] = {}
        self._lock = threading.RLock()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def backend_name(self) -> str:
        return "memory"

    async def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            value = self._get_value(entry)
            if value is not None:
                self._hits += 1
            else:
                self._misses += 1
                # Lazily remove expired entry
                if entry is not None:
                    self._store.pop(key, None)
            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            # Evict if at capacity (oldest-first, not LRU — simple but effective)
            if len(self._store) >= self._max_size and key not in self._store:
                # Remove a stale entry if one exists, otherwise remove the first N entries
                self._evict_stale(1)
                if len(self._store) >= self._max_size:
                    # Still full — remove oldest entries
                    oldest_keys = list(self._store.keys())[: max(1, self._max_size // 10)]
                    for k in oldest_keys:
                        self._store.pop(k, None)
                        self._evictions += 1
            self._store[key] = self._make_entry(value, ttl)

    async def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                self._store.pop(key)
                return True
            return False

    async def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    async def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if self._is_expired(entry):
                self._store.pop(key, None)
                return False
            return True

    async def get_stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "backend": "memory",
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
                "evictions": self._evictions,
            }

    def _evict_stale(self, count: int = 1) -> int:
        """Remove up to `count` expired entries. Returns actual count removed."""
        removed = 0
        stale_keys = [
            k for k, v in self._store.items() if self._is_expired(v)
        ]
        for k in stale_keys[:count]:
            self._store.pop(k, None)
            removed += 1
            self._evictions += 1
        return removed

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)