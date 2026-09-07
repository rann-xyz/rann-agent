#!/usr/bin/env python3
"""
Profile the agent execution loop (hot path only).
Pre-import all modules, then profile the actual agent loop.

Run: python scripts/profile_agent.py
"""

import asyncio
import cProfile
import io
import pstats
from pathlib import Path

PROFILE_OUTPUT = Path.home() / ".rann-agent" / "profiles"
PROFILE_OUTPUT.mkdir(parents=True, exist_ok=True)


async def run_agent_loop():
    """Run just the agent execution loop without import overhead."""
    from rann_agent.core.config import Config
    from rann_agent.core.context import Context
    from rann_agent.tools.registry import ToolRegistry

    call_count = 0

    class MockProvider:
        def __init__(self):
            self.model = "mock-model"

        async def complete(self, messages, tools=None):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.0001)  # Simulate minimal LLM processing

            if call_count == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "name": "read_file",
                            "parameters": {
                                "path": "/home/userland/rann-agent/README.md",
                                "limit": 50,
                            },
                        }
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                    "model": self.model,
                }
            elif call_count == 2:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "name": "write_file",
                            "parameters": {"path": "/tmp/test.txt", "content": "test"},
                        }
                    ],
                    "usage": {"input_tokens": 150, "output_tokens": 60},
                    "model": self.model,
                }
            else:
                return {
                    "content": "Done",
                    "usage": {"input_tokens": 200, "output_tokens": 80},
                    "model": self.model,
                }

    # Setup (outside profiling region)
    config = Config.load()
    registry = ToolRegistry(config)
    context = Context()
    context.add_user_message("Read the README and summarize.")

    # Pre-fetch enabled tools once

    # Agent loop (the actual hot path)
    for turn in range(10):
        messages = context.get_messages()
        response = await MockProvider().complete(messages)

        if response.get("tool_calls"):
            for tool_call in response["tool_calls"]:
                result = await registry.execute(tool_call["name"], tool_call.get("parameters", {}))
                context.add_tool_results([result])
        else:
            if response.get("content"):
                context.add_assistant_message(response["content"])
            break

    return call_count


def main():
    print("=" * 70)
    print("RANN Agent Profiler - Execution Loop Focus")
    print("=" * 70)
    print()

    # Pre-import to get them out of the way
    print("Pre-importing modules...")
    print("Imports complete.")
    print()

    # Now profile just the loop
    print("Running agent loop with profiling...")

    profiler = cProfile.Profile()
    profiler.enable()

    elapsed = asyncio.run(run_agent_loop())

    profiler.disable()

    print(f"Execution time: {elapsed*1000:.2f}ms for {elapsed} LLM calls")
    print()

    # Save
    existing = len(list(PROFILE_OUTPUT.glob("agent_*.prof")))
    output_path = PROFILE_OUTPUT / f"agent_{existing + 1}.prof"
    profiler.dump_stats(str(output_path))

    # Print stats
    print("=" * 70)
    print("TOP 25 FUNCTIONS BY CUMULATIVE TIME")
    print("=" * 70)

    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats(25)
    print(s.getvalue())

    print()
    print("=" * 70)
    print("TOP 25 FUNCTIONS BY TOTAL TIME")
    print("=" * 70)

    s2 = io.StringIO()
    ps2 = pstats.Stats(profiler, stream=s2).sort_stats("time")
    ps2.print_stats(25)
    print(s2.getvalue())

    # Analysis of bottlenecks
    print()
    print("=" * 70)
    print("HOT PATH BOTTLENECK ANALYSIS")
    print("=" * 70)

    stats = pstats.Stats(profiler)
    bottlenecks = []
    for func, data in stats.stats.items():
        _cc, _nc, tt, ct, _callers = data
        filename, line, func_name = func
        # Focus on rann_agent code, not stdlib
        if "rann_agent" in filename and ct > 0.001:
            bottlenecks.append((ct, tt, filename, line, func_name))

    bottlenecks.sort(reverse=True)
    print("\nRANN Agent bottlenecks (cumtime > 1ms):")
    for ct, tt, filename, line, func_name in bottlenecks[:20]:
        print(f"  {ct*1000:.2f}ms cum / {tt*1000:.2f}ms self | {filename}:{line} | {func_name}")

    print(f"\nProfile saved: {output_path}")
    return output_path


if __name__ == "__main__":
    main()
