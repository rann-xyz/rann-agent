"""
Enhanced Agent Brain - Thinking, Search, and Context Management

This module provides the cognitive layer for RANN Agent:
- Thinking phase before execution
- Web search integration for real-time data
- Context management across conversations
- Response formatting with evidence
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class ThoughtPhase(Enum):
    """Phases of agent thinking"""
    RECEIVE = "receive"           # Task received
    UNDERSTAND = "understand"     # Parse and understand intent
    RESEARCH = "research"         # Search for relevant info
    PLAN = "plan"                 # Create execution plan
    EXECUTE = "execute"           # Execute plan
    VERIFY = "verify"             # Verify results
    REFLECT = "reflect"           # Self-reflection on outcome
    RESPOND = "respond"           # Format response


@dataclass
class Thought:
    """A single thought in the agent's reasoning chain"""
    phase: ThoughtPhase
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    sources: List[str] = field(default_factory=list)


@dataclass
class AgentContext:
    """Conversation context maintained across interactions"""
    conversation_id: str
    user_id: Optional[str] = None
    project_path: Optional[str] = None
    task_history: List[Dict[str, Any]] = field(default_factory=list)
    facts: Dict[str, str] = field(default_factory=dict)  # semantic facts
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ThinkingEngine:
    """
    The thinking brain of RANN Agent.
    Before any execution, the agent thinks through the task.
    """
    
    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider
        self.thought_chain: List[Thought] = []
        self.context: Optional[AgentContext] = None
    
    async def think(self, task: str, enable_web_search: bool = True) -> Dict[str, Any]:
        """
        Main thinking loop - processes task through all phases.
        Returns structured thinking trace and execution plan.
        """
        self.thought_chain.clear()
        
        # Phase 1: RECEIVE
        await self._phase_receive(task)
        
        # Phase 2: UNDERSTAND
        await self._phase_understand(task)
        
        # Phase 3: RESEARCH (web search if needed)
        if enable_web_search:
            await self._phase_research(task)
        
        # Phase 4: PLAN
        execution_plan = await self._phase_plan(task)
        
        return {
            "thinking_trace": [t.__dict__ for t in self.thought_chain],
            "execution_plan": execution_plan,
            "context": self.context.__dict__ if self.context else None,
        }
    
    async def _phase_receive(self, task: str):
        """Record task receipt"""
        thought = Thought(
            phase=ThoughtPhase.RECEIVE,
            content=f"Task received: {task[:100]}...",
            metadata={"task_length": len(task)}
        )
        self.thought_chain.append(thought)
    
    async def _phase_understand(self, task: str):
        """Understand the task intent"""
        # Analyze task type
        task_type = self._classify_task(task)
        
        # Extract key entities
        entities = self._extract_entities(task)
        
        thought = Thought(
            phase=ThoughtPhase.UNDERSTAND,
            content=f"Task classified as '{task_type}' with entities: {entities}",
            metadata={
                "task_type": task_type,
                "entities": entities,
                "requires_search": self._needs_research(task),
            },
            confidence=0.9
        )
        self.thought_chain.append(thought)
    
    async def _phase_research(self, task: str):
        """Research phase - search web for relevant info"""
        if not self._needs_research(task):
            thought = Thought(
                phase=ThoughtPhase.RESEARCH,
                content="No web research needed for this task",
                metadata={"search_results": None}
            )
            self.thought_chain.append(thought)
            return
        
        # This will be connected to web search tool
        thought = Thought(
            phase=ThoughtPhase.RESEARCH,
            content="Web search would be performed here for real-time data",
            metadata={"search_needed": True, "query_suggestions": self._suggest_search_queries(task)},
        )
        self.thought_chain.append(thought)
    
    async def _phase_plan(self, task: str):
        """Create execution plan"""
        task_type = self._classify_task(task)
        
        # Generate steps based on task type
        steps = self._generate_steps(task_type, task)
        
        thought = Thought(
            phase=ThoughtPhase.PLAN,
            content=f"Generated {len(steps)} execution steps",
            metadata={"steps": steps, "estimated_turns": len(steps)},
            confidence=0.85
        )
        self.thought_chain.append(thought)
        
        return {"steps": steps, "task_type": task_type}
    
    def _classify_task(self, task: str) -> str:
        """Classify the type of task"""
        task_lower = task.lower()
        
        if any(k in task_lower for k in ["create", "write", "make", "generate"]):
            if any(ext in task_lower for ext in [".py", ".js", ".html", ".css", ".md"]):
                return "code_generation"
            return "file_creation"
        
        if any(k in task_lower for k in ["fix", "bug", "error", "crash"]):
            return "bug_fixing"
        
        if any(k in task_lower for k in ["search", "find", "look up", "apa", "siapa", "dimana"]):
            return "information_query"
        
        if any(k in task_lower for k in ["explain", "jelaskan", "terangkan"]):
            return "explanation"
        
        if any(k in task_lower for k in ["list", "show", "display", "tampilkan"]):
            return "listing"
        
        if any(k in task_lower for k in ["calculate", "hitung", "compute"]):
            return "calculation"
        
        return "general"
    
    def _extract_entities(self, task: str) -> List[str]:
        """Extract key entities from task"""
        entities = []
        
        # File names
        import re
        file_pattern = r'\b[\w]+\.(py|js|ts|html|css|md|txt|json|yaml|yml)\b'
        files = re.findall(file_pattern, task)
        entities.extend(files)
        
        # Commands
        cmd_pattern = r'\b(git|pip|npm|docker|kubectl|make)\b'
        cmds = re.findall(cmd_pattern, task)
        entities.extend(cmds)
        
        return list(set(entities))
    
    def _needs_research(self, task: str) -> bool:
        """Check if task needs web research"""
        research_keywords = [
            "latest", "recent", "current", "newest",
            "version", "release", "update", "news",
            "price", "stock", "weather", "score",
            "apa itu", "siapa", "dimana", "kapan",
            "what is", "who is", "where is", "when"
        ]
        return any(k in task.lower() for k in research_keywords)
    
    def _suggest_search_queries(self, task: str) -> List[str]:
        """Suggest search queries for the task"""
        queries = []
        
        # Indonesian
        if "apa" in task.lower():
            queries.append(task.lower().replace("apa", "").strip())
        if "siapa" in task.lower():
            queries.append(task.lower().replace("siapa", "").strip())
        
        # English
        if "what is" in task.lower():
            queries.append(task.lower().replace("what is", "").strip())
        if "who is" in task.lower():
            queries.append(task.lower().replace("who is", "").strip())
        
        if not queries:
            queries.append(task[:50])
        
        return queries[:3]
    
    def _generate_steps(self, task_type: str, task: str) -> List[Dict[str, str]]:
        """Generate execution steps based on task type"""
        base_steps = [
            {"action": "think", "description": "Analyze task requirements"},
            {"action": "plan", "description": "Determine execution approach"},
        ]
        
        if task_type == "code_generation":
            return base_steps + [
                {"action": "search", "description": "Check existing code patterns"},
                {"action": "write", "description": "Generate code"},
                {"action": "verify", "description": "Test code correctness"},
            ]
        
        if task_type == "information_query":
            return base_steps + [
                {"action": "web_search", "description": "Search for current information"},
                {"action": "extract", "description": "Extract relevant data"},
                {"action": "summarize", "description": "Format response"},
            ]
        
        if task_type == "file_creation":
            return base_steps + [
                {"action": "check_directory", "description": "Verify target directory"},
                {"action": "create", "description": "Create file with content"},
                {"action": "verify", "description": "Confirm file created"},
            ]
        
        return base_steps + [
            {"action": "execute", "description": "Perform task"},
            {"action": "verify", "description": "Verify outcome"},
        ]


class ResponseFormatter:
    """
    Formats agent responses with proper structure and evidence.
    """
    
    @staticmethod
    def format_thinking_response(thinking: Dict[str, Any], final_output: str) -> str:
        """Format response showing thinking trace"""
        trace = thinking.get("thinking_trace", [])
        
        output = "## Thinking Process\n\n"
        for thought in trace:
            phase = thought["phase"].upper()
            content = thought["content"]
            output += f"**[{phase}]** {content}\n\n"
        
        output += "---\n\n"
        output += f"## Response\n\n{final_output}"
        
        return output
    
    @staticmethod
    def format_structured_response(
        output: str,
        sources: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Format response as structured data"""
        return {
            "output": output,
            "sources": sources or [],
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    @staticmethod
    def format_error_response(error: str, context: str = None) -> Dict[str, Any]:
        """Format error response"""
        return {
            "success": False,
            "error": error,
            "context": context,
            "timestamp": datetime.utcnow().isoformat(),
        }


class ContextManager:
    """
    Manages conversation context across interactions.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.current_context: Optional[AgentContext] = None
    
    def create_context(self, conversation_id: str, **kwargs) -> AgentContext:
        """Create new conversation context"""
        self.current_context = AgentContext(
            conversation_id=conversation_id,
            **{k: v for k, v in kwargs.items() if k in AgentContext.__dataclass_fields__}
        )
        return self.current_context
    
    def load_context(self, conversation_id: str) -> Optional[AgentContext]:
        """Load existing context"""
        # Would load from database
        return self.current_context
    
    def update_context(self, **updates):
        """Update current context"""
        if self.current_context:
            for key, value in updates.items():
                if hasattr(self.current_context, key):
                    setattr(self.current_context, key, value)
            self.current_context.last_updated = datetime.utcnow().isoformat()
    
    def add_fact(self, key: str, value: str):
        """Add semantic fact to context"""
        if self.current_context:
            self.current_context.facts[key] = value
            self.current_context.last_updated = datetime.utcnow().isoformat()
    
    def get_fact(self, key: str) -> Optional[str]:
        """Get semantic fact from context"""
        if self.current_context:
            return self.current_context.facts.get(key)
        return None
    
    def add_task(self, task_data: Dict[str, Any]):
        """Add task to history"""
        if self.current_context:
            self.current_context.task_history.append({
                **task_data,
                "timestamp": datetime.utcnow().isoformat()
            })
            self.current_context.last_updated = datetime.utcnow().isoformat()