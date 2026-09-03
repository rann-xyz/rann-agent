#!/usr/bin/env python3
"""
RANN Agent - Basic Example

Minimal example of using RuntimeAgent to execute a task.
"""

import asyncio
from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.budget import Budget


async def main():
    print("RANN Agent - Basic Example\n")
    
    # Create agent with budget limits
    agent = RuntimeAgent(
        budget=Budget(max_tokens=5000, max_turns=10)
    )
    
    # Execute a task
    print("Task: Write a hello world program in Python\n")
    
    result = await agent.execute(
        goal="Write a hello world program in Python",
        context="Keep it simple and clean"
    )
    
    if result.get("done"):
        print("Task completed!\n")
        print(result.get("output", ""))
    else:
        print(f"Task ended after {result.get('turns', 0)} turns")
    
    # Print budget usage
    if "budget" in result:
        budget = result["budget"]
        print(f"\nToken usage: {budget['tracker']['tokens']['used']}/{budget['budget']['max_tokens']}")


if __name__ == "__main__":
    asyncio.run(main())