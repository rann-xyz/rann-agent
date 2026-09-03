#!/usr/bin/env python3
"""
RANN Agent - Custom Tool Example

Shows how to register a custom tool with the tool registry.
"""

import asyncio
from rann_agent.tools.registry import ToolRegistry
from rann_agent.tools.discovery import ToolDiscovery


# Define a custom tool function
def get_weather(city: str, units: str = "celsius") -> dict:
    """Get weather for a city (simulated)"""
    return {
        "city": city,
        "temperature": 22 if units == "celsius" else 72,
        "units": units,
        "condition": "sunny"
    }


async def main():
    print("RANN Agent - Custom Tool Example\n")
    
    # Create discovery and register custom tool
    discovery = ToolDiscovery()
    
    discovery.register(
        name="weather",
        func=get_weather,
        description="Get current weather for a city",
        risk_level="safe",
        parameters={
            "city": {"type": "string", "required": True},
            "units": {"type": "string", "default": "celsius"}
        }
    )
    
    # Verify it's registered
    tool = discovery.get("weather")
    print(f"Tool registered: {tool['name']}")
    print(f"Description: {tool['description']}")
    print(f"Risk level: {tool['risk_level']}")
    
    # Test the function directly
    result = get_weather("Jakarta", "celsius")
    print(f"\nWeather result: {result}")


if __name__ == "__main__":
    asyncio.run(main())