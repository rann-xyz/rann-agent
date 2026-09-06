"""
Cache backend abstraction layer.

All cache backends (InMemory, Redis, etc.) must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
import time


class CacheBackend(ABC):
    """
    Abstract cache backend interface.

    All backends must be async-compatible and thread-safe.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key. Returns None if not found or expired."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set key-value pair with optional TTL in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key. Returns True if key existed, False otherwise."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all keys in this cache namespace."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict:
        """Return backend-specific statistics."""
        pass

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable backend name."""

    async def close(self) -> None:
        """Clean up backend resources. Override in subclasses that hold connections."""
        pass


class TTLCacheMixin:
    """
    Mixin that adds TTL support to any dict-backed cache.

    Stores entries as (value, expiry_timestamp) tuples.
    """

    def _is_expired(self, entry: tuple) -> bool:
        """Check if a (value, expiry) entry has expired."""
        if entry is None:
            return True
        value, expires_at = entry
        if expires_at is None:
            return False
        return time.monotonic() > expires_at

    def _make_entry(self, value: Any, ttl: Optional[int]) -> tuple:
        """Create a (value, expiry_timestamp) entry."""
        if ttl is None:
            return (value, None)
        return (value, time.monotonic() + ttl)

    def _get_value(self, entry: tuple) -> Any:
        """Extract value from entry, returning None if expired."""
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            return None
        return value