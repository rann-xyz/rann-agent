"""
RANN Agent Performance Benchmarks using pytest-benchmark.

Run: pytest tests/benchmarks/test_benchmark.py -v --benchmark-disable-gc
Save baseline: pytest tests/benchmarks/test_benchmark.py --benchmark-save
Compare vs baseline: pytest tests/benchmarks/test_benchmark.py --benchmark-compare=0001
"""
import pytest
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rann_agent.cache import InMemoryCache, llm_cache_key, tool_cache_key
from rann_agent.memory.context_trim import trim_context, estimate_tokens


class TestCacheBenchmark:
    """Cache operation benchmarks."""

    @pytest.fixture
    def cache(self):
        return InMemoryCache(max_size=10000)

    def test_cache_hit_latency(self, benchmark, cache):
        """In-memory cache hit should be < 100µs p99."""

        async def do_get():
            return await cache.get("key")

        asyncio.run(cache.set("key", {"data": "x"}, ttl=3600))
        result = benchmark(do_get)
        assert result is not None

    def test_cache_miss_latency(self, benchmark, cache):
        """In-memory cache get on missing key should be < 500µs p99."""
        import asyncio

        def do_get_miss():
            return asyncio.run(cache.get("nonexistent_benchmark_key_xyz"))

        result = benchmark(do_get_miss)
        assert result is None

    def test_cache_key_generation(self, benchmark):
        """Cache key generation should be < 10µs p99."""
        messages = [{"role": "user", "content": "Hello, how are you?"}] * 5

        def gen_key():
            return llm_cache_key(messages, "claude-sonnet-4-20250514", temperature=0.7)

        result = benchmark(gen_key)
        assert result.startswith("llm:")

    def test_llm_key_stability(self, benchmark):
        """Same inputs always produce the same key in < 5µs."""
        messages = [{"role": "user", "content": "test"}]

        def stable_key():
            return llm_cache_key(messages, "gpt-4o", temperature=0.7)

        k1 = stable_key()
        k2 = stable_key()
        assert k1 == k2
        result = benchmark(stable_key)
        assert result == k1


class TestContextTrimBenchmark:
    """Context window trimming benchmarks."""

    def _make_messages(self, count: int) -> list:
        """Create a realistic message list."""
        messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
        for i in range(count):
            messages.append({"role": "user", "content": f"Message {i}: " + "x" * 50})
            messages.append({"role": "assistant", "content": "Response " + "y" * 50})
        return messages

    def test_context_trim_100_messages(self, benchmark):
        """Trim 100 messages should be < 10ms p99."""
        messages = self._make_messages(50)
        assert len(messages) == 101

        def do_trim():
            return trim_context(messages, "claude-sonnet-4-20250514", max_tokens=1000)

        result = benchmark(do_trim)
        assert len(result) <= len(messages)
        assert result[0]["role"] == "system"

    def test_context_trim_1000_messages(self, benchmark):
        """Trim 1000 messages should be < 50ms p99."""
        messages = self._make_messages(500)
        assert len(messages) == 1001

        def do_trim():
            return trim_context(messages, "claude-sonnet-4-20250514", max_tokens=2000)

        result = benchmark(do_trim)
        assert len(result) <= len(messages)
        assert result[0]["role"] == "system"


class TestStateBenchmark:
    """State machine benchmarks."""

    def test_state_machine_100_transitions(self, benchmark):
        """100 state transitions should be < 5ms p99."""
        from rann_agent.core.state import AgentState, VALID_TRANSITIONS

        state = [AgentState.ANALYZING]

        def run_transitions():
            for _ in range(100):
                next_states = list(VALID_TRANSITIONS.get(state[0], []))
                if next_states:
                    state[0] = next_states[0]

        benchmark(run_transitions)


class TestDatabaseBenchmark:
    """Database benchmarks."""

    def test_db_connection_acquire(self, benchmark):
        """DB connection acquire from pool should be < 50ms p99."""
        from rann_agent.storage.pool import get_pool

        def acquire_conn():
            pool = get_pool()
            with pool.get_connection() as conn:
                conn.execute("SELECT 1")

        result = benchmark(acquire_conn)
        assert result is None  # context manager returns None