"""
Multi-agent orchestration system.
Spawn, manage, and coordinate multiple agents.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
import uuid


class AgentStatus(Enum):
    """Agent status states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentTask:
    """Task assigned to an agent."""
    task_id: str
    description: str
    agent_id: str
    status: AgentStatus = AgentStatus.IDLE
    result: Optional[Any] = None
    error: Optional[str] = None


class AgentOrchestrator:
    """
    Manages multiple agents working in parallel or hierarchically.
    """
    
    def __init__(self):
        self.agents = {}
        self.tasks = {}
        self.task_queue = []
    
    async def spawn_agent(
        self,
        agent_type: str,
        name: str,
        capabilities: List[str]
    ) -> str:
        """Spawn a new agent."""
        agent_id = str(uuid.uuid4())[:8]
        
        self.agents[agent_id] = {
            'id': agent_id,
            'name': name,
            'type': agent_type,
            'capabilities': capabilities,
            'status': AgentStatus.IDLE,
            'tasks_completed': 0,
            'success_rate': 1.0
        }
        
        return agent_id
    
    async def assign_task(
        self,
        agent_id: str,
        task_description: str
    ) -> str:
        """Assign task to specific agent."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")
        
        task_id = str(uuid.uuid4())[:8]
        task = AgentTask(
            task_id=task_id,
            description=task_description,
            agent_id=agent_id
        )
        
        self.tasks[task_id] = task
        self.task_queue.append(task_id)
        
        return task_id
    
    async def delegate(
        self,
        task_description: str,
        required_capabilities: List[str] = None
    ) -> str:
        """Automatically delegate task to best available agent."""
        # Find suitable agent
        suitable_agents = []
        
        for agent_id, agent in self.agents.items():
            if agent['status'] == AgentStatus.IDLE:
                if not required_capabilities:
                    suitable_agents.append(agent_id)
                else:
                    if all(cap in agent['capabilities'] for cap in required_capabilities):
                        suitable_agents.append(agent_id)
        
        if not suitable_agents:
            raise ValueError("No suitable agent available")
        
        # Pick best agent (highest success rate)
        best_agent = max(
            suitable_agents,
            key=lambda aid: self.agents[aid]['success_rate']
        )
        
        return await self.assign_task(best_agent, task_description)
    
    async def execute_task(self, task_id: str) -> Dict:
        """Execute a task."""
        if task_id not in self.tasks:
            return {'error': 'Task not found'}
        
        task = self.tasks[task_id]
        agent = self.agents[task.agent_id]
        
        # Update status
        task.status = AgentStatus.RUNNING
        agent['status'] = AgentStatus.RUNNING
        
        try:
            # Simulate task execution
            result = await self._run_task(task, agent)
            
            task.status = AgentStatus.COMPLETED
            task.result = result
            
            agent['tasks_completed'] += 1
            agent['status'] = AgentStatus.IDLE
            
            return {'success': True, 'result': result}
        
        except Exception as e:
            task.status = AgentStatus.FAILED
            task.error = str(e)
            agent['status'] = AgentStatus.IDLE
            
            return {'success': False, 'error': str(e)}
    
    async def _run_task(self, task: AgentTask, agent: Dict) -> Any:
        """Internal task execution."""
        # This would call actual agent logic
        await asyncio.sleep(0.1)  # Simulate work
        return f"Task '{task.description}' completed by {agent['name']}"
    
    async def get_status(self) -> Dict:
        """Get orchestrator status."""
        return {
            'total_agents': len(self.agents),
            'active_agents': sum(
                1 for a in self.agents.values()
                if a['status'] == AgentStatus.RUNNING
            ),
            'pending_tasks': len(self.task_queue),
            'completed_tasks': sum(
                1 for t in self.tasks.values()
                if t.status == AgentStatus.COMPLETED
            )
        }
