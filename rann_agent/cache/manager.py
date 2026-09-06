"""
Cache manager — unified API for all caching needs.

Usage:
    cache = get_cache()  # returns singleton
    await cache.get_llm_response(messages, model, params)
    await cache.get_tool_result(tool_name, args)
    await cache.get_embedding(text, model)

The cache backend is selected automatically:
- RedisCache if REDIS_URL env var is set and redis package is installed
- InMemoryCache otherwise (always available)
"""
import os
import threading
from typing import Any, Optional

import structlog

from rann_agent.cache.backend import CacheBackend
from rann_agent.cache.memory import InMemoryCache
from rann_agent.cache.redis_ import RedisCache, REDIS_AVAILABLE as REDIS_INSTALLED
from rann_agent.cache.keys import (
    llm_cache_key,
    tool_cache_key,
    embedding_cache_key,
)

logger = structlog.get_logger()

# Global singleton
_cache: Optional["CacheManager"] = None
_cache_lock = threading.Lock()

def _is_cache_enabled() -> bool:
    """Check if cache is enabled — re-reads env each call so feature flag works at runtime."""
    return os.environ.get("RANN_CACHE_ENABLED", "true").lower() in ("true", "1", "yes")


def get_cache() -> "CacheManager":
    """Get the global CacheManager singleton."""
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = CacheManager()
        return _cache


def reset_cache() -> None:
    """Reset the global cache singleton (useful for testing)."""
    global _cache
    with _cache_lock:
        if _cache is not None:
            # fire-and-forget close
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_cache.backend.close() if hasattr(_cache.backend, "close") else asyncio.sleep(0))
            except RuntimeError:
                pass
        _cache = None


class CacheManager:
    """
    Unified caching API for LLM responses, tool results, and embeddings.

    Automatically selects the best available backend (Redis > InMemory).
    All operations are async and non-blocking.

    Args:
        llm_ttl: TTL in seconds for LLM response cache (default: 3600 = 1h)
        tool_ttl: TTL for tool result cache (default: 300 = 5min)
        embedding_ttl: TTL for embedding cache (default: 86400 = 24h)
    """

    def __init__(
        self,
        *,
        llm_ttl: int = 3600,
        tool_ttl: int = 300,
        embedding_ttl: int = 86400,
        redis_url: Optional[str] = None,
    ):
        self._enabled = _is_cache_enabled()
        self._llm_ttl = llm_ttl
        self._tool_ttl = tool_ttl
        self._embedding_ttl = embedding_ttl

        # Select backend
        self._backend: CacheBackend = self._select_backend(redis_url)
        logger.info(
            "cache_manager_initialized",
            enabled=self._enabled,
            backend=self._backend.backend_name,
            llm_ttl=self._llm_ttl,
            tool_ttl=self._tool_ttl,
            embedding_ttl=self._embedding_ttl,
        )

    def _select_backend(self, redis_url: Optional[str]) -> CacheBackend:
        """Pick Redis if available and configured, otherwise InMemory."""
        url = redis_url or os.environ.get("REDIS_URL", "")
        if url and REDIS_INSTALLED:
            try:
                return RedisCache(url=url, default_ttl=self._llm_ttl)
            except Exception as e:
                logger.warning("redis_backend_failed_fallback", error=str(e))

        if REDIS_INSTALLED and url:
            logger.info("redis_url_set_but_not_available_using_memory")
        return InMemoryCache(max_size=10000)

    # -------------------------------------------------------------------------
    # LLM Response Cache
    # -------------------------------------------------------------------------

    async def get_llm_response(
        self,
        messages: list,
        model: str,
        **params,
    ) -> Optional[dict]:
        """
        Get cached LLM response for identical messages + params.

        Returns None on cache miss.
        """
        if not self._enabled:
            return None

        key = llm_cache_key(messages, model, **params)
        result = await self._backend.get(key)
        if result is not None:
            logger.debug("llm_cache_hit", key=key, model=model)
        return result

    async def set_llm_response(
        self,
        messages: list,
        model: str,
        response: dict,
        **params,
    ) -> None:
        """Cache an LLM response."""
        if not self._enabled:
            return

        key = llm_cache_key(messages, model, **params)
        await self._backend.set(key, response, ttl=self._llm_ttl)
        logger.debug("llm_cache_set", key=key, model=model)

    # -------------------------------------------------------------------------
    # Tool Result Cache
    # -------------------------------------------------------------------------

    async def get_tool_result(
        self,
        tool_name: str,
        args: dict,
    ) -> Optional[dict]:
        """
        Get cached result for an idempotent tool call.

        Returns None on cache miss.
        """
        if not self._enabled:
            return None

        key = tool_cache_key(tool_name, args)
        result = await self._backend.get(key)
        if result is not None:
            logger.debug("tool_cache_hit", key=key, tool=tool_name)
        return result

    async def set_tool_result(
        self,
        tool_name: str,
        args: dict,
        result: dict,
    ) -> None:
        """Cache a tool call result."""
        if not self._enabled:
            return

        # Only cache successful results
        if not result.get("success", True):
            return

        key = tool_cache_key(tool_name, args)
        await self._backend.set(key, result, ttl=self._tool_ttl)
        logger.debug("tool_cache_set", key=key, tool=tool_name)

    # -------------------------------------------------------------------------
    # Embedding Cache
    # -------------------------------------------------------------------------

    async def get_embedding(
        self,
        text: str,
        model: str,
    ) -> Optional[list]:
        """
        Get cached embedding vector for text.

        Returns None on cache miss.
        """
        if not self._enabled:
            return None

        key = embedding_cache_key(text, model)
        result = await self._backend.get(key)
        if result is not None:
            logger.debug("embedding_cache_hit", key=key, model=model)
        return result

    async def set_embedding(
        self,
        text: str,
        model: str,
        embedding: list,
    ) -> None:
        """Cache an embedding vector."""
        if not self._enabled:
            return

        key = embedding_cache_key(text, model)
        await self._backend.set(key, embedding, ttl=self._embedding_ttl)
        logger.debug("embedding_cache_set", key=key, model=model)

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    @property
    def backend(self) -> CacheBackend:
        """The underlying cache backend."""
        return self._backend

    async def invalidate(self, pattern: str = "*") -> int:
        """
        Invalidate cache entries matching pattern.

        Returns count of deleted keys (approximate for Redis).
        """
        if not self._enabled:
            return 0

        # For in-memory, we clear everything (pattern support would need more code)
        if self._backend.backend_name == "memory":
            await self._backend.clear()
            return 0  # Unknown count

        # Redis: use SCAN with pattern
        try:
            import redis.asyncio as redis
            client = getattr(self._backend, "_client", None)
            if client is None:
                return 0
            count = 0
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    await client.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
            logger.info("cache_invalidated", pattern=pattern, count=count)
            return count
        except Exception as e:
            logger.warning("cache_invalidate_failed", pattern=pattern, error=str(e))
            return 0

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        stats = await self._backend.get_stats()
        stats["enabled"] = self._enabled
        return stats

    async def clear(self) -> None:
        """Clear all cache entries."""
        await self._backend.clear()
        logger.info("cache_cleared")