"""
RANN Agent SLO Benchmarks

Performance benchmarks that define our contractual SLOs.
These run in CI and must pass before merging.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# Performance SLOs
# =============================================================================
SLOs = {
    "tool_registry_init_ms": 100,
    "db_connection_ms": 100,
    "context_trim_500_msgs_ms": 50,
    "state_100_transitions_ms": 20,
    "cache_lookup_us": 1000,
    "event_emission_per_event_us": 5000,
    "concurrent_100_writes_s": 2.0,
    "memory_footprint_mb": 200,
}


@pytest.mark.slo
class TestSLOBenchmarks:
    """
    Contractual performance SLOs.
    FAILING these blocks merging to main.
    """

    @pytest.fixture
    def config(self):
        from rann_agent.core.config import Config

        return Config()

    def test_slo_tool_registry_init(self, config):
        from rann_agent.tools.registry import ToolRegistry

        times = []
        for _ in range(5):
            start = time.perf_counter()
            ToolRegistry(config=config)
            times.append(time.perf_counter() - start)

        avg_ms = (sum(times) / len(times)) * 1000
        slo_ms = SLOs["tool_registry_init_ms"]
        assert avg_ms < slo_ms, f"SLO FAIL: ToolRegistry init {avg_ms:.1f}ms > {slo_ms}ms"

    def test_slo_state_transitions(self, config):
        from rann_agent.core.state import VALID_TRANSITIONS, AgentState

        times = []
        for _ in range(5):
            state = AgentState.QUEUED
            start = time.perf_counter()
            for _ in range(100):
                next_states = list(VALID_TRANSITIONS.get(state, []))
                if next_states:
                    state = next_states[0]
            times.append(time.perf_counter() - start)

        avg_ms = (sum(times) / len(times)) * 1000
        slo_ms = SLOs["state_100_transitions_ms"]
        assert avg_ms < slo_ms, f"SLO FAIL: 100 transitions {avg_ms:.1f}ms > {slo_ms}ms"

    def test_slo_context_trim(self, config):
        from rann_agent.utils.context_window import ContextWindowManager

        messages = [{"role": "system", "content": "You are RANN."}] + [
            {"role": "user", "content": f"Msg {i} " + "x" * 200} for i in range(500)
        ]

        manager = ContextWindowManager(model="claude-sonnet-4-20250514")
        times = []
        for _ in range(5):
            start = time.perf_counter()
            manager.fit(messages)
            times.append(time.perf_counter() - start)

        avg_ms = (sum(times) / len(times)) * 1000
        slo_ms = SLOs["context_trim_500_msgs_ms"]
        assert avg_ms < slo_ms, f"SLO FAIL: context trim {avg_ms:.1f}ms > {slo_ms}ms"
