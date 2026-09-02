"""
Redis caching layer for LLM responses and tool results
"""

import json
import hashlib
from typing import Optional, Any
import structlog

logger = structlog.get_logger()

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis not installed - caching disabled")


class CacheManager:
    """
    Intelligent caching for LLM responses and tool results
    """
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.advanced.cache_llm_responses or config.advanced.cache_tool_results
        self.ttl = config.advanced.get("cache_ttl", 3600)  # 1 hour default
        
        if self.enabled and REDIS_AVAILABLE:
            redis_url = config.get("redis_url", "redis://localhost:6379")
            self.client = redis.from_url(redis_url, decode_responses=True)
            logger.info("cache_enabled", backend="redis")
        else:
            self.client = None
            self.cache = {}  # Fallback to in-memory
            logger.info("cache_enabled", backend="memory")
    
    def _make_key(self, prefix: str, data: Any) -> str:
        """Generate cache key from data"""
        serialized = json.dumps(data, sort_keys=True)
        hash_val = hashlib.sha256(serialized.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_val}"
    
    async def get_llm_response(self, messages: list) -> Optional[dict]:
        """Get cached LLM response"""
        if not self.enabled or not self.config.advanced.cache_llm_responses:
            return None
        
        key = self._make_key("llm", messages)
        
        try:
            if self.client:
                # Redis backend
                cached = await self.client.get(key)
                if cached:
                    logger.debug("cache_hit", key=key, type="llm")
                    return json.loads(cached)
            else:
                # Memory backend
                if key in self.cache:
                    logger.debug("cache_hit", key=key, type="llm")
                    return self.cache[key]
        except Exception as e:
            logger.error("cache_get_failed", error=str(e))
        
        return None
    
    async def set_llm_response(self, messages: list, response: dict):
        """Cache LLM response"""
        if not self.enabled or not self.config.advanced.cache_llm_responses:
            return
        
        key = self._make_key("llm", messages)
        
        try:
            if self.client:
                # Redis backend with TTL
                await self.client.setex(
                    key,
                    self.ttl,
                    json.dumps(response)
                )
            else:
                # Memory backend (no TTL)
                self.cache[key] = response
            
            logger.debug("cache_set", key=key, type="llm")
        except Exception as e:
            logger.error("cache_set_failed", error=str(e))
    
    async def get_tool_result(self, tool_name: str, parameters: dict) -> Optional[dict]:
        """Get cached tool result"""
        if not self.enabled or not self.config.advanced.cache_tool_results:
            return None
        
        key = self._make_key(f"tool:{tool_name}", parameters)
        
        try:
            if self.client:
                cached = await self.client.get(key)
                if cached:
                    logger.debug("cache_hit", key=key, type="tool", tool=tool_name)
                    return json.loads(cached)
            else:
                if key in self.cache:
                    logger.debug("cache_hit", key=key, type="tool", tool=tool_name)
                    return self.cache[key]
        except Exception as e:
            logger.error("cache_get_failed", error=str(e))
        
        return None
    
    async def set_tool_result(self, tool_name: str, parameters: dict, result: dict):
        """Cache tool result"""
        if not self.enabled or not self.config.advanced.cache_tool_results:
            return
        
        # Don't cache failed results
        if not result.get("success"):
            return
        
        key = self._make_key(f"tool:{tool_name}", parameters)
        
        try:
            if self.client:
                # Shorter TTL for tool results (5 minutes)
                await self.client.setex(
                    key,
                    300,
                    json.dumps(result)
                )
            else:
                self.cache[key] = result
            
            logger.debug("cache_set", key=key, type="tool", tool=tool_name)
        except Exception as e:
            logger.error("cache_set_failed", error=str(e))
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern"""
        if not self.enabled:
            return
        
        try:
            if self.client:
                cursor = 0
                while True:
                    cursor, keys = await self.client.scan(cursor, match=pattern, count=100)
                    if keys:
                        await self.client.delete(*keys)
                    if cursor == 0:
                        break
                logger.info("cache_invalidated", pattern=pattern)
            else:
                # Memory backend - clear matching keys
                to_delete = [k for k in self.cache.keys() if pattern in k]
                for k in to_delete:
                    del self.cache[k]
        except Exception as e:
            logger.error("cache_invalidate_failed", error=str(e))
    
    async def clear_all(self):
        """Clear entire cache"""
        if not self.enabled:
            return
        
        try:
            if self.client:
                await self.client.flushdb()
            else:
                self.cache.clear()
            
            logger.info("cache_cleared")
        except Exception as e:
            logger.error("cache_clear_failed", error=str(e))
    
    async def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            if self.client:
                info = await self.client.info("stats")
                return {
                    "enabled": True,
                    "backend": "redis",
                    "hits": info.get("keyspace_hits", 0),
                    "misses": info.get("keyspace_misses", 0),
                    "hit_rate": info.get("keyspace_hits", 0) / max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)),
                }
            else:
                return {
                    "enabled": True,
                    "backend": "memory",
                    "keys": len(self.cache),
                }
        except Exception as e:
            logger.error("cache_stats_failed", error=str(e))
            return {"enabled": True, "error": str(e)}
