"""
User modeling with dialectic memory (inspired by Honcho).
Builds a deepening model of the user across sessions.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class UserModel:
    """
    Builds and maintains a model of the user.
    Learns preferences, habits, communication style, and context.
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile = {
            'id': user_id,
            'name': None,
            'preferences': {},
            'habits': {},
            'communication_style': {},
            'context': {},
            'interaction_count': 0,
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat()
        }
        self.interaction_history = []
    
    async def update_from_interaction(
        self,
        message: str,
        response: str,
        metadata: Dict[str, Any] = None
    ):
        """Update user model from an interaction."""
        self.profile['interaction_count'] += 1
        self.profile['last_seen'] = datetime.now().isoformat()
        
        # Store interaction
        self.interaction_history.append({
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'response': response,
            'metadata': metadata or {}
        })
        
        # Analyze and update model
        await self._analyze_interaction(message, response, metadata)
    
    async def _analyze_interaction(
        self,
        message: str,
        response: str,
        metadata: Optional[Dict] = None
    ):
        """Analyze interaction to update user model."""
        # Detect preferences
        if 'prefer' in message.lower() or 'like' in message.lower():
            await self._extract_preference(message)
        
        # Detect habits (time patterns, recurring requests)
        await self._update_habits(message, metadata)
        
        # Analyze communication style
        await self._analyze_communication_style(message)
    
    async def _extract_preference(self, message: str):
        """Extract user preferences from message."""
        # Simple keyword extraction (can be enhanced with NLP)
        if 'prefer' in message.lower():
            # Example: "I prefer Python over JavaScript"
            parts = message.lower().split('prefer')
            if len(parts) > 1:
                preference = parts[1].strip()
                self.profile['preferences']['general'] = preference
    
    async def _update_habits(self, message: str, metadata: Optional[Dict] = None):
        """Track user habits and patterns."""
        hour = datetime.now().hour
        
        # Track active hours
        if 'active_hours' not in self.profile['habits']:
            self.profile['habits']['active_hours'] = {}
        
        hour_str = str(hour)
        self.profile['habits']['active_hours'][hour_str] = \
            self.profile['habits']['active_hours'].get(hour_str, 0) + 1
        
        # Track common requests
        if 'common_requests' not in self.profile['habits']:
            self.profile['habits']['common_requests'] = {}
        
        # Extract keywords (simplified)
        keywords = message.lower().split()[:3]
        key = ' '.join(keywords)
        self.profile['habits']['common_requests'][key] = \
            self.profile['habits']['common_requests'].get(key, 0) + 1
    
    async def _analyze_communication_style(self, message: str):
        """Analyze user's communication style."""
        style = self.profile['communication_style']
        
        # Message length preference
        length = len(message.split())
        if 'avg_message_length' not in style:
            style['avg_message_length'] = length
        else:
            # Running average
            count = self.profile['interaction_count']
            style['avg_message_length'] = \
                (style['avg_message_length'] * (count - 1) + length) / count
        
        # Formality level (simple heuristic)
        if any(word in message.lower() for word in ['please', 'thank', 'could you']):
            style['formality'] = style.get('formality', 0) + 1
        
        # Emoji usage
        if any(char in message for char in '😀😃😄😁🔥💪'):
            style['uses_emoji'] = True
    
    async def add_context(self, key: str, value: Any):
        """Add context information about the user."""
        self.profile['context'][key] = value
    
    async def get_context(self, key: str) -> Optional[Any]:
        """Get context information."""
        return self.profile['context'].get(key)
    
    async def get_preferences(self) -> Dict[str, Any]:
        """Get user preferences."""
        return self.profile['preferences']
    
    async def get_habits(self) -> Dict[str, Any]:
        """Get user habits."""
        return self.profile['habits']
    
    async def get_communication_style(self) -> Dict[str, Any]:
        """Get user's communication style."""
        return self.profile['communication_style']
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the user model."""
        return {
            'user_id': self.user_id,
            'name': self.profile.get('name'),
            'interaction_count': self.profile['interaction_count'],
            'first_seen': self.profile['first_seen'],
            'last_seen': self.profile['last_seen'],
            'top_preferences': list(self.profile['preferences'].items())[:5],
            'communication_style': self.profile['communication_style'],
            'most_active_hours': self._get_most_active_hours(),
            'common_requests': self._get_common_requests()
        }
    
    def _get_most_active_hours(self) -> List[int]:
        """Get user's most active hours."""
        if 'active_hours' not in self.profile['habits']:
            return []
        
        hours = self.profile['habits']['active_hours']
        sorted_hours = sorted(hours.items(), key=lambda x: x[1], reverse=True)
        return [int(hour) for hour, count in sorted_hours[:3]]
    
    def _get_common_requests(self) -> List[str]:
        """Get user's most common request types."""
        if 'common_requests' not in self.profile['habits']:
            return []
        
        requests = self.profile['habits']['common_requests']
        sorted_requests = sorted(requests.items(), key=lambda x: x[1], reverse=True)
        return [req for req, count in sorted_requests[:5]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Export user model as dictionary."""
        return {
            'profile': self.profile,
            'recent_interactions': self.interaction_history[-10:]
        }
    
    def to_json(self) -> str:
        """Export user model as JSON."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserModel':
        """Load user model from dictionary."""
        user_id = data['profile']['id']
        model = cls(user_id)
        model.profile = data['profile']
        model.interaction_history = data.get('recent_interactions', [])
        return model
