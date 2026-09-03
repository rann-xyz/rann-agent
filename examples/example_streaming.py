#!/usr/bin/env python3
"""
RANN Agent - Streaming Example

Shows how to stream agent responses token by token.
"""

import asyncio
from rann_agent.core.runtime import RuntimeAgent


async def main():
    print("RANN Agent - Streaming Example\n")
    
    agent = RuntimeAgent()
    
    print("Task: Explain what a decorator does in Python\n")
    print("Agent response (streaming):\n")
    print("-" * 60)
    
    async for token in agent.stream(
        goal="Explain what a decorator does in Python"
    ):
        print(token, end="", flush=True)
    
    print("\n" + "-" * 60)
    print("\nStreaming complete!")


if __name__ == "__main__":
    asyncio.run(main())