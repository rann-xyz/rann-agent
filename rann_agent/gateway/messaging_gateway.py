"""
Gateway for multi-platform messaging.
Connect to Telegram, Discord, Slack, WhatsApp, Signal.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
import asyncio


class Platform(Enum):
    """Supported messaging platforms."""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    SIGNAL = "signal"
    CLI = "cli"


@dataclass
class Message:
    """Unified message format."""
    platform: Platform
    user_id: str
    chat_id: str
    content: str
    message_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessagingGateway:
    """
    Unified gateway for multiple messaging platforms.
    Agent can communicate across Telegram, Discord, Slack, etc.
    """
    
    def __init__(self):
        self.platforms = {}
        self.handlers = {}
        self.running = False
    
    async def register_platform(
        self,
        platform: Platform,
        config: Dict[str, Any],
        handler: Any
    ):
        """
        Register a messaging platform.
        
        Args:
            platform: Platform type
            config: Platform-specific config (tokens, etc.)
            handler: Platform handler instance
        """
        self.platforms[platform] = {
            'config': config,
            'handler': handler,
            'connected': False
        }
    
    async def connect(self, platform: Platform) -> bool:
        """Connect to a platform."""
        if platform not in self.platforms:
            return False
        
        try:
            handler = self.platforms[platform]['handler']
            if hasattr(handler, 'connect'):
                await handler.connect()
            
            self.platforms[platform]['connected'] = True
            return True
        except Exception as e:
            print(f"Failed to connect to {platform.value}: {e}")
            return False
    
    async def disconnect(self, platform: Platform) -> bool:
        """Disconnect from a platform."""
        if platform not in self.platforms:
            return False
        
        try:
            handler = self.platforms[platform]['handler']
            if hasattr(handler, 'disconnect'):
                await handler.disconnect()
            
            self.platforms[platform]['connected'] = False
            return True
        except Exception as e:
            print(f"Failed to disconnect from {platform.value}: {e}")
            return False
    
    async def send_message(
        self,
        platform: Platform,
        chat_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send message to a platform.
        
        Args:
            platform: Target platform
            chat_id: Chat/channel ID
            content: Message content
            metadata: Additional metadata
        """
        if platform not in self.platforms:
            return False
        
        if not self.platforms[platform]['connected']:
            await self.connect(platform)
        
        try:
            handler = self.platforms[platform]['handler']
            
            if hasattr(handler, 'send_message'):
                await handler.send_message(chat_id, content, metadata)
                return True
            
            return False
        except Exception as e:
            print(f"Failed to send message on {platform.value}: {e}")
            return False
    
    async def receive_message(self, platform: Platform) -> Optional[Message]:
        """Receive a message from platform."""
        if platform not in self.platforms:
            return None
        
        try:
            handler = self.platforms[platform]['handler']
            
            if hasattr(handler, 'receive_message'):
                msg_data = await handler.receive_message()
                
                if msg_data:
                    return Message(
                        platform=platform,
                        user_id=msg_data.get('user_id'),
                        chat_id=msg_data.get('chat_id'),
                        content=msg_data.get('content'),
                        message_id=msg_data.get('message_id'),
                        metadata=msg_data.get('metadata')
                    )
            
            return None
        except Exception as e:
            print(f"Failed to receive message from {platform.value}: {e}")
            return None
    
    async def broadcast(
        self,
        content: str,
        platforms: Optional[List[Platform]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[Platform, bool]:
        """
        Broadcast message to multiple platforms.
        
        Args:
            content: Message content
            platforms: Target platforms (None = all)
            metadata: Additional metadata
        """
        results = {}
        target_platforms = platforms or list(self.platforms.keys())
        
        for platform in target_platforms:
            if platform in self.platforms:
                # Get default chat_id from config
                config = self.platforms[platform]['config']
                chat_id = config.get('default_chat_id')
                
                if chat_id:
                    success = await self.send_message(
                        platform, chat_id, content, metadata
                    )
                    results[platform] = success
        
        return results
    
    async def start(self):
        """Start the gateway."""
        self.running = True
        
        # Connect to all registered platforms
        for platform in self.platforms.keys():
            await self.connect(platform)
    
    async def stop(self):
        """Stop the gateway."""
        self.running = False
        
        # Disconnect from all platforms
        for platform in self.platforms.keys():
            await self.disconnect(platform)
    
    def get_connected_platforms(self) -> List[Platform]:
        """Get list of connected platforms."""
        return [
            platform for platform, data in self.platforms.items()
            if data['connected']
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Get gateway status."""
        return {
            'running': self.running,
            'total_platforms': len(self.platforms),
            'connected_platforms': len(self.get_connected_platforms()),
            'platforms': {
                platform.value: data['connected']
                for platform, data in self.platforms.items()
            }
        }
