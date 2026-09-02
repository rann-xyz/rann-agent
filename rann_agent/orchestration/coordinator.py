"""
Multi-agent orchestration and coordination
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class Task:
    """Task definition for sub-agents"""
    goal: str
    context: Optional[str] = None
    role: str = "leaf"  # leaf | orchestrator
    dependencies: List[str] = None  # Task IDs this depends on
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class Coordinator:
    """
    Multi-agent coordinator - spawns and manages sub-agents
    """
    
    def __init__(self, config, parent_agent):
        self.config = config
        self.parent = parent_agent
        self.max_concurrent = config.agent.orchestration.max_concurrent_agents
        self.max_depth = config.agent.orchestration.max_depth
        self.current_depth = 0
        
        # Active sub-agents
        self.agents: Dict[str, Any] = {}
        
        logger.info("coordinator_init", max_concurrent=self.max_concurrent)
    
    async def execute_parallel(self, tasks: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Execute multiple tasks in parallel
        
        Args:
            tasks: List of task dicts with 'goal' and optional 'context'
            
        Returns:
            List of results, one per task
        """
        logger.info("execute_parallel_start", task_count=len(tasks))
        
        # Limit concurrent tasks
        tasks_to_run = tasks[:self.max_concurrent]
        
        # Spawn agents for each task
        agent_tasks = []
        for i, task_def in enumerate(tasks_to_run):
            agent = await self._spawn_agent(f"agent_{i}")
            task = agent.execute(
                goal=task_def["goal"],
                context=task_def.get("context"),
            )
            agent_tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*agent_tasks, return_exceptions=True)
        
        # Format results
        formatted = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                formatted.append({
                    "task": tasks_to_run[i]["goal"],
                    "success": False,
                    "error": str(result),
                })
            else:
                formatted.append({
                    "task": tasks_to_run[i]["goal"],
                    "success": True,
                    "result": result,
                })
        
        logger.info("execute_parallel_complete", completed=len(formatted))
        return formatted
    
    async def execute_graph(self, tasks: List[Task]) -> List[Dict[str, Any]]:
        """
        Execute tasks with dependency resolution (DAG)
        
        Args:
            tasks: List of Task objects with dependencies
            
        Returns:
            List of results in completion order
        """
        logger.info("execute_graph_start", task_count=len(tasks))
        
        # Build dependency graph
        task_map = {f"task_{i}": task for i, task in enumerate(tasks)}
        results = {}
        completed = set()
        
        async def execute_task(task_id: str, task: Task):
            """Execute one task after its dependencies"""
            # Wait for dependencies
            if task.dependencies:
                await asyncio.gather(
                    *[wait_for_completion(dep) for dep in task.dependencies]
                )
            
            # Execute
            agent = await self._spawn_agent(task_id)
            result = await agent.execute(goal=task.goal, context=task.context)
            
            results[task_id] = result
            completed.add(task_id)
            return result
        
        async def wait_for_completion(task_id: str):
            """Wait for a task to complete"""
            while task_id not in completed:
                await asyncio.sleep(0.1)
        
        # Execute all tasks (will respect dependencies)
        await asyncio.gather(
            *[execute_task(tid, task) for tid, task in task_map.items()]
        )
        
        logger.info("execute_graph_complete", completed=len(results))
        return list(results.values())
    
    async def _spawn_agent(self, agent_id: str):
        """Spawn a new sub-agent"""
        if self.current_depth >= self.max_depth:
            raise Exception(f"Max agent depth reached: {self.max_depth}")
        
        # Import here to avoid circular dependency
        from rann_agent.core.agent import Agent
        
        agent = Agent(
            config=self.config,
            memory=False,  # Sub-agents don't have independent memory
        )
        
        self.agents[agent_id] = agent
        logger.debug("agent_spawned", agent_id=agent_id)
        
        return agent
    
    def list_agents(self) -> List[Dict[str, str]]:
        """List active sub-agents"""
        return [
            {"id": agent_id, "status": "active"}
            for agent_id in self.agents.keys()
        ]
    
    async def stop_agent(self, agent_id: str):
        """Stop a sub-agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info("agent_stopped", agent_id=agent_id)
