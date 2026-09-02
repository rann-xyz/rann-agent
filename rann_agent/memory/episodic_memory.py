"""
Episodic memory - stores experiences and events chronologically.
"""

from typing import List, Dict, Any
from datetime import datetime
import json


class EpisodicMemory:
    """Stores agent experiences and events over time."""
    
    def __init__(self):
        self.episodes = []
        self.max_episodes = 1000
    
    async def add_episode(
        self,
        event_type: str,
        content: Dict[str, Any],
        outcome: str = "success"
    ) -> str:
        """Record a new episode."""
        episode = {
            'id': f"ep_{len(self.episodes)}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'content': content,
            'outcome': outcome
        }
        
        self.episodes.append(episode)
        
        # Trim old episodes
        if len(self.episodes) > self.max_episodes:
            self.episodes = self.episodes[-self.max_episodes:]
        
        return episode['id']
    
    async def get_recent(self, n: int = 10) -> List[Dict]:
        """Get recent episodes."""
        return self.episodes[-n:]
    
    async def search(self, event_type: str = None, outcome: str = None) -> List[Dict]:
        """Search episodes by criteria."""
        results = self.episodes
        
        if event_type:
            results = [e for e in results if e['event_type'] == event_type]
        
        if outcome:
            results = [e for e in results if e['outcome'] == outcome]
        
        return results
