"""
Hot Path Profiler for RANN Agent.

Run: python -m cProfile -o rann.prof rann_agent/cli/rann.py run "hello"
Then: python -c "import pstats; p = pstats.Stats('rann.prof'); p.sort_stats('cumulative').print_stats(20)"
"""

import cProfile
import io
import pstats
import sys
from pathlib import Path

PROFILE_OUTPUT = Path.home() / ".rann-agent" / "profiles"
PROFILE_OUTPUT.mkdir(parents=True, exist_ok=True)


def profile_agent():
    """Profile a simple agent run."""
    import asyncio

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from rann_agent.core.agent import Agent
    from rann_agent.core.config import Config

    async def run():
        agent = Agent(config=Config())
        result = await agent.execute("Say hello in one sentence")
        return result

    profiler = cProfile.Profile()
    profiler.enable()
    asyncio.run(run())
    profiler.disable()

    # Save
    output = PROFILE_OUTPUT / f"agent_{len(list(PROFILE_OUTPUT.glob('*.prof')))}.prof"
    profiler.dump_stats(str(output))

    # Print summary
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats(30)
    print(s.getvalue())
    print(f"Profile saved: {output}")


if __name__ == "__main__":
    profile_agent()
