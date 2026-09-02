#!/usr/bin/env python3
"""
Example: Basic agent usage
"""

import asyncio
from rann_agent import Agent


async def main():
    print("🤖 Rann Agent - Basic Example\n")
    
    # Create agent
    agent = Agent(
        provider="anthropic",  # or "openai" or "ollama"
        model="claude-sonnet-4-20250514",
    )
    
    # Execute a simple task
    print("Task: Analyze this Python file and suggest improvements\n")
    
    result = await agent.execute(
        goal="Read example_basic.py and suggest code improvements",
        context="Focus on code quality, readability, and best practices"
    )
    
    if result.get("done"):
        print("✅ Task completed!\n")
        print(result.get("output", ""))
    else:
        print("❌ Task failed\n")
        print(result.get("error", "Unknown error"))


if __name__ == "__main__":
    asyncio.run(main())
