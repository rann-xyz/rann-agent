"""
RANN Agent Cache Module

Provides a layered caching system for LLM responses, tool results, and embeddings.
Designed for high-throughput autonomous agent workloads.

Architecture:
    CacheManager (public API)
        └── CacheBackend (abstract)
                ├── InMemoryCache (default, no deps)
                └── RedisCache (optional, activates when REDIS_URL is set)
"""

from rann_agent.cache.backend import CacheBackend
from rann_agent.cache.keys import (
    cache_key,
    embedding_cache_key,
    hash_data,
    llm_cache_key,
    tool_cache_key,
)
from rann_agent.cache.manager import CacheManager, get_cache, reset_cache
from rann_agent.cache.memory import InMemoryCache
from rann_agent.cache.redis_ import RedisCache

__all__ = [
    "CacheBackend",
    "CacheManager",
    "InMemoryCache",
    "RedisCache",
    "cache_key",
    "embedding_cache_key",
    "get_cache",
    "hash_data",
    "llm_cache_key",
    "reset_cache",
    "tool_cache_key",
]
