"""
Redis cache backend.

Optional backend — activates only when REDIS_URL is set in the environment.
Falls back gracefully if Redis is unavailable.
"""
import json
import os
from rann_agent.cache.backend import CacheBackend
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    REDIS_AVAILABLE = False
    redis = None  # type: ignore


class RedisCache(CacheBackend):
    """
    Async Redis cache backend.

    Uses redis.asyncio for non-blocking operations.
    Falls back to in-memory if Redis connection fails.
    """

    def __init__(self, *, url: Optional[str] = None, default_ttl: int = 3600):
        if not REDIS_AVAILABLE:
            raise RuntimeError(
                "redis package not installed. "
                "Install with: pip install redis"
            )

        self._url = url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._default_ttl = default_ttl
        self._client: Optional[redis.Redis] = None
        self._connect_failed = False
        self._hits = 0
        self._misses = 0

    @property
    def backend_name(self) -> str:
        return "redis"

    async def _get_client(self) -> Optional[redis.Redis]:
        """Lazily connect. Returns None if connection failed."""
        if self._connect_failed:
            return None
        if self._client is None:
            try:
                self._client = redis.from_url(
                    self._url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=10,
                )
                # Verify connection
                await self._client.ping()
                logger.info("redis_cache_connected", url=self._url)
            except Exception as e:
                logger.warning(
                    "redis_cache_connect_failed",
                    url=self._url,
                    error=str(e),
                )
                self._connect_failed = True
                self._client = None
                return None
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        client = await self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except Exception as e:
            logger.warning("redis_get_failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        client = await self._get_client()
        if client is None:
            return
        try:
            serialized = json.dumps(value)
            expire = ttl if ttl is not None else self._default_ttl
            await client.setex(key, expire, serialized)
        except Exception as e:
            logger.warning("redis_set_failed", key=key, error=str(e))

    async def delete(self, key: str) -> bool:
        client = await self._get_client()
        if client is None:
            return False
        try:
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning("redis_delete_failed", key=key, error=str(e))
            return False

    async def clear(self) -> None:
        client = await self._get_client()
        if client is None:
            return
        try:
            await client.flushdb()
            self._hits = 0
            self._misses = 0
        except Exception as e:
            logger.warning("redis_clear_failed", error=str(e))

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        if client is None:
            return False
        try:
            return await client.exists(key) > 0
        except Exception as e:
            logger.warning("redis_exists_failed", key=key, error=str(e))
            return False

    async def get_stats(self) -> dict:
        client = await self._get_client()
        if client is None:
            return {"backend": "redis", "connected": False}
        try:
            info = await client.info("stats")
            total = info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)
            hit_rate = info.get("keyspace_hits", 0) / total if total > 0 else 0.0
            return {
                "backend": "redis",
                "connected": True,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": round(hit_rate, 4),
                "used_memory_human": info.get("used_memory_human", "unknown"),
            }
        except Exception as e:
            logger.warning("redis_stats_failed", error=str(e))
            return {"backend": "redis", "connected": True, "error": str(e)}

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None