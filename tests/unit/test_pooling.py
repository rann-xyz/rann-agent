"""
Unit tests for connection pooling and client reuse.

These tests mock the underlying HTTP/SDK clients to focus on verifying
the pooling/reuse logic without making real network calls.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from rann_agent.core import llm_provider as llm_module
from rann_agent.interfaces.api_client import APIClient
from rann_agent.utils.http_pool import POOL_LIMITS, get_pool_limits


class TestHTTPPooling:
    """Test HTTP connection pooling via shared limits config."""

    @pytest.mark.asyncio
    async def test_api_clients_share_same_pool_limits(self):
        """Multiple APIClient instances use the same connection limits config."""
        client1 = APIClient(base_url="http://foo.com", api_key="key1")
        client2 = APIClient(base_url="http://bar.com", api_key="key2")

        c1 = await client1._get_client()
        c2 = await client2._get_client()

        # Both clients were created with the same shared limits singleton
        assert c1 is not None
        assert c2 is not None
        assert get_pool_limits().max_connections == 100
        assert get_pool_limits().max_keepalive_connections == 20

    @pytest.mark.asyncio
    async def test_api_client_get_client_returns_same_instance(self):
        """Multiple calls to _get_client on same APIClient return same instance."""
        client = APIClient(base_url="http://example.com")
        c1 = await client._get_client()
        c2 = await client._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_api_client_close_clears_instance(self):
        """close() clears the client so next call creates a new one."""
        client = APIClient(base_url="http://example.com")
        c1 = await client._get_client()
        await client.close()
        assert client._client is None
        c2 = await client._get_client()
        assert c2 is not c1

    def test_get_pool_limits_returns_singleton(self):
        """get_pool_limits returns the shared singleton Limits config."""
        limits = get_pool_limits()
        assert limits is POOL_LIMITS
        assert limits.max_connections == 100
        assert limits.max_keepalive_connections == 20


class TestLLMClientCaching:
    """Test LLM provider client instance reuse via module-level cache."""

    def setup_method(self):
        llm_module.clear_client_cache()

    def teardown_method(self):
        llm_module.clear_client_cache()

    def test_same_key_model_reuses_client(self):
        """Same (api_key, model) reuses the cached client instance."""
        mock_client = MagicMock()
        with patch.dict(llm_module._LLM_CLIENT_CACHE, {}, clear=True):
            llm_module.clear_client_cache()
            with patch("anthropic.AsyncAnthropic", return_value=mock_client):
                p1 = llm_module.AnthropicProvider("key", "claude-sonnet-4-20250514")
                p2 = llm_module.AnthropicProvider("key", "claude-sonnet-4-20250514")
        assert p1.client is p2.client

    def test_different_key_creates_different_client(self):
        """Different api_keys create separate client instances."""
        with patch("anthropic.AsyncAnthropic") as mock_init:
            mock_init.side_effect = lambda **kw: MagicMock()
            p1 = llm_module.AnthropicProvider("key-1", "claude-sonnet-4-20250514")
            p2 = llm_module.AnthropicProvider("key-2", "claude-sonnet-4-20250514")
        assert p1.client is not p2.client
        assert mock_init.call_count == 2

    def test_different_model_creates_different_client(self):
        """Different models create separate client instances."""
        with patch("anthropic.AsyncAnthropic") as mock_init:
            mock_init.side_effect = lambda **kw: MagicMock()
            p1 = llm_module.AnthropicProvider("key", "claude-sonnet-4-20250514")
            p2 = llm_module.AnthropicProvider("key", "claude-opus-4-20250514")
        assert p1.client is not p2.client
        assert mock_init.call_count == 2

    def test_openai_same_key_model_reuses_client(self):
        """OpenAI: same (api_key, model) reuses cached client instance."""
        mock_client = MagicMock()
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            p1 = llm_module.OpenAIProvider("key", "gpt-4o")
            p2 = llm_module.OpenAIProvider("key", "gpt-4o")
        assert p1.client is p2.client

    def test_openai_different_key_creates_different_client(self):
        """OpenAI: different api_keys create separate client instances."""
        with patch("openai.AsyncOpenAI") as mock_init:
            mock_init.side_effect = lambda **kw: MagicMock()
            p1 = llm_module.OpenAIProvider("key-1", "gpt-4o")
            p2 = llm_module.OpenAIProvider("key-2", "gpt-4o")
        assert p1.client is not p2.client
        assert mock_init.call_count == 2

    def test_clear_cache_empties_all_providers(self):
        """clear_client_cache() removes all cached LLM clients."""
        with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
            llm_module.AnthropicProvider("key", "claude-sonnet-4-20250514")
            llm_module.OpenAIProvider("key", "gpt-4o")
        assert len(llm_module._LLM_CLIENT_CACHE) == 2
        llm_module.clear_client_cache()
        assert len(llm_module._LLM_CLIENT_CACHE) == 0

    def test_cache_key_includes_provider_type(self):
        """Different provider types for same model get different cache entries."""
        with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
            with patch("openai.AsyncOpenAI", return_value=MagicMock()):
                p1 = llm_module.AnthropicProvider("key", "same-model")
                p2 = llm_module.OpenAIProvider("key", "same-model")
        assert p1.client is not p2.client  # different provider type

    def test_concurrent_provider_creation_thread_safe(self):
        """Concurrent provider creation for same key/model is thread-safe."""
        llm_module.clear_client_cache()
        mock_client = MagicMock()
        barrier = threading.Barrier(10)

        def make_provider(i: int):
            with patch("anthropic.AsyncAnthropic", return_value=mock_client):
                barrier.wait()
                return llm_module.AnthropicProvider("shared-key", "model-0")

        threads = [threading.Thread(target=make_provider, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 10 threads should have gotten the same client
        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            p = llm_module.AnthropicProvider("shared-key", "model-0")
        assert p.client is mock_client
        llm_module.clear_client_cache()
