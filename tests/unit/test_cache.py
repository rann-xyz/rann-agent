"""
Unit tests for the cache module.
"""

import pytest

from rann_agent.cache import (
    InMemoryCache,
    embedding_cache_key,
    get_cache,
    hash_data,
    llm_cache_key,
    reset_cache,
    tool_cache_key,
)


class TestHashData:
    def test_stable_hash(self):
        """Same input always produces same hash."""
        data = {
            "messages": [{"role": "user", "content": "hi"}],
            "model": "claude-sonnet-4",
        }
        h1 = hash_data(data)
        h2 = hash_data(data)
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        """Different inputs produce different hashes."""
        h1 = hash_data({"a": 1})
        h2 = hash_data({"a": 2})
        assert h1 != h2

    def test_hash_length(self):
        """Hash is 16 hex characters."""
        h = hash_data({"test": "value"})
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_key_order_independent(self):
        """Dict key order doesn't affect hash."""
        h1 = hash_data({"a": 1, "b": 2})
        h2 = hash_data({"b": 2, "a": 1})
        assert h1 == h2


class TestCacheKey:
    def test_llm_key_includes_model_and_params(self):
        """LLM cache key changes when model or params change."""
        messages = [{"role": "user", "content": "hello"}]
        k1 = llm_cache_key(messages, "claude-sonnet-4", temperature=0.7)
        k2 = llm_cache_key(messages, "claude-sonnet-4", temperature=1.0)
        k3 = llm_cache_key(messages, "gpt-4o")
        assert k1 != k2
        assert k1 != k3
        assert k1.startswith("llm:")
        assert k2.startswith("llm:")

    def test_tool_key_includes_tool_and_args(self):
        """Tool cache key changes when tool or args change."""
        k1 = tool_cache_key("read_file", {"path": "/tmp/a.txt"})
        k2 = tool_cache_key("read_file", {"path": "/tmp/b.txt"})
        k3 = tool_cache_key("write_file", {"path": "/tmp/a.txt"})
        assert k1 != k2
        assert k1 != k3
        assert k1.startswith("tool:")

    def test_embedding_key_includes_text_and_model(self):
        """Embedding key changes when text or model changes."""
        k1 = embedding_cache_key("hello world", "text-embedding-3-small")
        k2 = embedding_cache_key("hello world", "text-embedding-3-large")
        k3 = embedding_cache_key("different text", "text-embedding-3-small")
        assert k1 != k2
        assert k1 != k3
        assert k1.startswith("embedding:")


class TestInMemoryCache:
    @pytest.fixture
    def cache(self):
        return InMemoryCache(max_size=100)

    @pytest.mark.asyncio
    async def test_get_set(self, cache):
        await cache.set("key1", {"result": "value1"}, ttl=60)
        result = await cache.get("key1")
        assert result == {"result": "value1"}

    @pytest.mark.asyncio
    async def test_get_missing(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        await cache.set("key1", "value1")
        assert await cache.delete("key1") is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_missing(self, cache):
        assert await cache.delete("nonexistent") is False

    @pytest.mark.asyncio
    async def test_exists(self, cache):
        await cache.set("key1", "value1")
        assert await cache.exists("key1") is True
        assert await cache.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, cache):
        await cache.set("key1", "value1", ttl=1)
        assert await cache.get("key1") == "value1"
        import asyncio

        await asyncio.sleep(1.1)
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        await cache.set("key1", "v1")
        await cache.set("key2", "v2")
        await cache.clear()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_stats(self, cache):
        await cache.set("key1", "v1")
        await cache.get("key1")  # hit
        await cache.get("key2")  # miss
        stats = await cache.get_stats()
        assert stats["backend"] == "memory"
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_max_size_eviction(self):
        cache = InMemoryCache(max_size=3)
        for i in range(5):
            await cache.set(f"key{i}", f"value{i}")
        # At least some keys should have been evicted
        stats = await cache.get_stats()
        assert stats["evictions"] > 0


class TestCacheManager:
    @pytest.fixture(autouse=True)
    def reset(self):
        reset_cache()
        yield
        reset_cache()

    @pytest.mark.asyncio
    async def test_llm_cache_roundtrip(self):
        cache = get_cache()
        messages = [{"role": "user", "content": "hi"}]
        response = {
            "content": "hello!",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }
        await cache.set_llm_response(messages, "claude-sonnet-4", response)
        result = await cache.get_llm_response(messages, "claude-sonnet-4")
        assert result == response

    @pytest.mark.asyncio
    async def test_llm_cache_different_models_different_entries(self):
        cache = get_cache()
        messages = [{"role": "user", "content": "hi"}]
        await cache.set_llm_response(messages, "claude-sonnet-4", {"content": "sonnet"})
        await cache.set_llm_response(messages, "gpt-4o", {"content": "gpt"})
        assert (await cache.get_llm_response(messages, "claude-sonnet-4"))["content"] == "sonnet"
        assert (await cache.get_llm_response(messages, "gpt-4o"))["content"] == "gpt"

    @pytest.mark.asyncio
    async def test_tool_cache_only_success(self):
        cache = get_cache()
        await cache.set_tool_result(
            "read_file",
            {"path": "/tmp/a.txt"},
            {"success": True, "content": "file content"},
        )
        await cache.set_tool_result(
            "read_file",
            {"path": "/tmp/b.txt"},
            {"success": False, "error": "not found"},
        )
        # Success should be cached
        assert await cache.get_tool_result("read_file", {"path": "/tmp/a.txt"}) is not None
        # Failure should NOT be cached
        assert await cache.get_tool_result("read_file", {"path": "/tmp/b.txt"}) is None

    @pytest.mark.asyncio
    async def test_embedding_cache_roundtrip(self):
        cache = get_cache()
        embedding = [0.1, 0.2, 0.3] * 100
        await cache.set_embedding("hello world", "text-embedding-3-small", embedding)
        result = await cache.get_embedding("hello world", "text-embedding-3-small")
        assert result == embedding

    @pytest.mark.asyncio
    async def test_cache_disabled_via_env(self):
        import os

        os.environ["RANN_CACHE_ENABLED"] = "false"
        reset_cache()
        cache = get_cache()
        await cache.set_llm_response(
            [{"role": "user", "content": "x"}], "claude-sonnet-4", {"content": "y"}
        )
        result = await cache.get_llm_response([{"role": "user", "content": "x"}], "claude-sonnet-4")
        assert result is None
        os.environ["RANN_CACHE_ENABLED"] = "true"
        reset_cache()

    @pytest.mark.asyncio
    async def test_get_stats(self):
        cache = get_cache()
        stats = await cache.get_stats()
        assert "backend" in stats
        assert "enabled" in stats
        assert stats["enabled"] is True
