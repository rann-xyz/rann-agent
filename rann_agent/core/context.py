"""
Context manager for conversation state
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # user | assistant | system | tool
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class Context:
    """
    Manages conversation context and message history
    """
    
    def __init__(self, max_length: int = 100000):
        self.messages: List[Message] = []
        self.max_length = max_length
        self.tool_results: List[Dict] = []
    
    def add_user_message(self, content: str, additional_context: Optional[str] = None):
        """Add user message"""
        full_content = content
        if additional_context:
            full_content = f"{content}\n\nContext:\n{additional_context}"
        
        self.messages.append(Message(role="user", content=full_content))
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None):
        """Add assistant message"""
        self.messages.append(
            Message(role="assistant", content=content, metadata=metadata or {})
        )
    
    def add_system_message(self, content: str):
        """Add system message"""
        self.messages.append(Message(role="system", content=content))
    
    def add_tool_results(self, results: List[Dict]):
        """Add tool execution results"""
        self.tool_results.extend(results)
        
        # Format tool results as assistant message
        formatted = self._format_tool_results(results)
        self.add_assistant_message(formatted, metadata={"tool_results": results})
    
    def _format_tool_results(self, results: List[Dict]) -> str:
        """Format tool results for LLM consumption"""
        formatted = []
        for r in results:
            tool_name = r.get("tool", "unknown")
            success = r.get("success", False)
            output = r.get("output", "")
            error = r.get("error", "")
            
            if success:
                formatted.append(f"✅ {tool_name}:\n{output}")
            else:
                formatted.append(f"❌ {tool_name} failed:\n{error}")
        
        return "\n\n".join(formatted)
    
    def get_messages(self) -> List[Dict[str, str]]:
        """Get messages in LLM API format"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
    
    def get_context_length(self) -> int:
        """Estimate context length in characters"""
        return sum(len(msg.content) for msg in self.messages)
    
    def compress(self):
        """Compress context if needed"""
        if self.get_context_length() > self.max_length:
            # Keep system messages + last N messages
            system_msgs = [m for m in self.messages if m.role == "system"]
            recent_msgs = self.messages[-20:]  # Keep last 20
            self.messages = system_msgs + recent_msgs
    
    def clear(self):
        """Clear all messages"""
        self.messages = []
        self.tool_results = []
