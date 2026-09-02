#!/usr/bin/env python3
"""
Example: Streaming execution
"""

import asyncio
from rann_agent import Agent


async def main():
    print("🤖 Rann Agent - Streaming Example\n")
    
    agent = Agent()
    
    print("Task: Write a FastAPI endpoint for user registration\n")
    print("Agent response (streaming):\n")
    print("-" * 60)
    
    async for token in agent.stream(
        goal="Write a FastAPI endpoint for user registration with email validation",
        context="Include password hashing, email verification, and proper error handling"
    ):
        print(token, end="", flush=True)
    
    print("\n" + "-" * 60)
    print("\n✅ Streaming complete!")


if __name__ == "__main__":
    asyncio.run(main())
