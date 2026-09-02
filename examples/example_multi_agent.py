#!/usr/bin/env python3
"""
Example: Multi-agent orchestration
"""

import asyncio
from rann_agent import Agent


async def main():
    print("🤖 Rann Agent - Multi-Agent Example\n")
    
    # Create coordinator
    agent = Agent()
    coordinator = agent.spawn_coordinator()
    
    # Define parallel tasks
    tasks = [
        {
            "goal": "Run pytest and report test coverage",
            "context": "Focus on percentage and failing tests",
        },
        {
            "goal": "Analyze Python files with ruff and report issues",
            "context": "Check for code quality issues",
        },
        {
            "goal": "Generate API documentation from FastAPI routes",
            "context": "Create markdown documentation",
        },
    ]
    
    print(f"Spawning {len(tasks)} agents to work in parallel...\n")
    
    # Execute in parallel
    results = await coordinator.execute_parallel(tasks)
    
    # Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60 + "\n")
    
    for i, result in enumerate(results, 1):
        status = "✅" if result.get("success") else "❌"
        print(f"{status} Agent {i}: {result.get('task', 'Unknown')[:50]}")
        
        if result.get("success"):
            output = result.get("result", {}).get("output", "")
            print(f"   {output[:100]}...\n")
        else:
            print(f"   Error: {result.get('error', 'Unknown')}\n")


if __name__ == "__main__":
    asyncio.run(main())
