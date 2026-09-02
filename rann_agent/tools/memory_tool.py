"""
Advanced memory tools for agent.
"""

from typing import Dict, Any
from ..memory.vector_memory import VectorMemory
from ..memory.episodic_memory import EpisodicMemory
from ..memory.semantic_memory import SemanticMemory


class MemoryTool:
    """Tool for accessing agent memory systems."""
    
    name = "memory"
    description = "Store and retrieve long-term memories"
    
    def __init__(self):
        self.vector_memory = VectorMemory()
        self.episodic_memory = EpisodicMemory()
        self.semantic_memory = SemanticMemory()
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Execute memory operations.
        
        Actions:
            - store: Store information
            - retrieve: Retrieve relevant memories
            - add_fact: Store a fact
            - get_fact: Get a fact
            - add_episode: Record an episode
            - get_recent_episodes: Get recent episodes
        """
        if action == "store":
            content = kwargs.get("content", "")
            category = kwargs.get("category", "general")
            memory_id = await self.vector_memory.store(content, category=category)
            return {"success": True, "memory_id": memory_id}
        
        elif action == "retrieve":
            query = kwargs.get("query", "")
            n_results = kwargs.get("n_results", 5)
            memories = await self.vector_memory.retrieve(query, n_results)
            return {"success": True, "memories": memories}
        
        elif action == "add_fact":
            key = kwargs.get("key", "")
            value = kwargs.get("value")
            category = kwargs.get("category", "general")
            await self.semantic_memory.add_fact(key, value, category)
            return {"success": True}
        
        elif action == "get_fact":
            key = kwargs.get("key", "")
            value = await self.semantic_memory.get_fact(key)
            return {"success": True, "value": value}
        
        elif action == "add_episode":
            event_type = kwargs.get("event_type", "")
            content = kwargs.get("content", {})
            outcome = kwargs.get("outcome", "success")
            episode_id = await self.episodic_memory.add_episode(
                event_type, content, outcome
            )
            return {"success": True, "episode_id": episode_id}
        
        elif action == "get_recent_episodes":
            n = kwargs.get("n", 10)
            episodes = await self.episodic_memory.get_recent(n)
            return {"success": True, "episodes": episodes}
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
