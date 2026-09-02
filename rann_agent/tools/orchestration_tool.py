"""
Orchestration tool for multi-agent coordination.
"""

from typing import Dict, Any, List
from ..orchestration.multi_agent import AgentOrchestrator


class OrchestrationTool:
    """Multi-agent orchestration and delegation."""
    
    name = "orchestration"
    description = "Spawn and manage multiple AI agents"
    
    def __init__(self):
        self.orchestrator = AgentOrchestrator()
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Execute orchestration operations.
        
        Actions:
            - spawn_agent: Create a new agent
            - assign_task: Assign task to specific agent
            - delegate: Auto-delegate to best agent
            - execute_task: Execute a task
            - get_status: Get orchestrator status
        """
        if action == "spawn_agent":
            agent_type = kwargs.get("type", "general")
            name = kwargs.get("name", "Agent")
            capabilities = kwargs.get("capabilities", [])
            
            agent_id = await self.orchestrator.spawn_agent(
                agent_type, name, capabilities
            )
            return {"success": True, "agent_id": agent_id}
        
        elif action == "assign_task":
            agent_id = kwargs.get("agent_id", "")
            task = kwargs.get("task", "")
            
            task_id = await self.orchestrator.assign_task(agent_id, task)
            return {"success": True, "task_id": task_id}
        
        elif action == "delegate":
            task = kwargs.get("task", "")
            capabilities = kwargs.get("required_capabilities", [])
            
            task_id = await self.orchestrator.delegate(task, capabilities)
            return {"success": True, "task_id": task_id}
        
        elif action == "execute_task":
            task_id = kwargs.get("task_id", "")
            result = await self.orchestrator.execute_task(task_id)
            return result
        
        elif action == "get_status":
            status = await self.orchestrator.get_status()
            return {"success": True, "status": status}
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
