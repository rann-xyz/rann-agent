#!/usr/bin/env python3
"""
Example: Custom tool implementation
"""

import asyncio
from typing import Dict, Any
from rann_agent import Agent
from rann_agent.tools.registry import Tool, ToolResult


class WeatherTool(Tool):
    """Custom tool: Get weather information"""
    
    name = "weather"
    description = "Get current weather for a city"
    parameters = {
        "city": {"type": "string", "required": True},
        "units": {"type": "string", "default": "celsius"},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, city: str, units: str = "celsius", **kwargs) -> Dict[str, Any]:
        """Get weather (mock implementation)"""
        # In real implementation, call weather API
        
        # Mock data
        weather_data = {
            "Jakarta": {"temp": 32, "condition": "Sunny"},
            "London": {"temp": 15, "condition": "Cloudy"},
            "Tokyo": {"temp": 22, "condition": "Rainy"},
        }
        
        if city not in weather_data:
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Weather data not available for {city}"
            ).to_dict()
        
        data = weather_data[city]
        output = f"Weather in {city}: {data['temp']}°C, {data['condition']}"
        
        return ToolResult(
            tool=self.name,
            success=True,
            output=output,
            metadata={"city": city, "units": units}
        ).to_dict()


async def main():
    print("🤖 Rann Agent - Custom Tool Example\n")
    
    # Create agent
    agent = Agent()
    
    # Register custom tool
    weather_tool = WeatherTool(agent.config)
    agent.tools.register(weather_tool)
    
    print("Registered custom 'weather' tool\n")
    
    # Use the tool
    print("Task: Get weather for multiple cities\n")
    
    result = await agent.execute(
        goal="Get weather for Jakarta, London, and Tokyo. Compare temperatures.",
    )
    
    if result.get("done"):
        print("✅ Task completed!\n")
        print(result.get("output", ""))
    else:
        print("❌ Task failed\n")
        print(result.get("error", ""))


if __name__ == "__main__":
    asyncio.run(main())
