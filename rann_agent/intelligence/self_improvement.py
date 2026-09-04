"""
Self-Correction and Learning System

RANN Agent can:
- Identify when it makes mistakes
- Self-correct based on feedback
- Learn from successful task completions
- Remember solutions to similar problems
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Correction:
    """A correction made by or to the agent"""
    task_id: str
    original_output: str
    corrected_output: str
    correction_type: str  # "feedback", "error", "retry"
    source: str  # "self", "user", "verification"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    lessons: List[str] = field(default_factory=list)


@dataclass
class LearnedSolution:
    """A learned solution to a type of problem"""
    problem_type: str
    problem_pattern: str  # regex or keyword pattern
    solution: str
    verification: str
    success_count: int = 0
    failure_count: int = 0
    last_used: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class SelfCorrection:
    """
    Self-correction engine - identifies and fixes mistakes.
    """
    
    def __init__(self):
        self.corrections: List[Correction] = []
        self.failed_attempts: Dict[str, int] = {}
    
    def record_attempt(self, task: str, success: bool):
        """Record attempt count for a task pattern"""
        key = task[:50].lower()
        if success:
            self.failed_attempts[key] = 0
        else:
            self.failed_attempts[key] = self.failed_attempts.get(key, 0) + 1
    
    def needs_retry(self, task: str) -> bool:
        """Check if task should be retried based on past failures"""
        key = task[:50].lower()
        return self.failed_attempts.get(key, 0) >= 2
    
    def get_retry_strategy(self, task: str, failure_reason: str) -> str:
        """Suggest a retry strategy based on failure"""
        strategies = {
            "file_not_found": "Check if file exists before modifying. Use 'ls' to verify path.",
            "syntax_error": "Review code syntax. Check for missing brackets, quotes, or semicolons.",
            "permission_denied": "Check file permissions. Try changing to writable directory.",
            "timeout": "Reduce scope of task. Break into smaller steps.",
            "tool_not_found": "Verify tool is enabled in config. Use 'rann doctor' to check.",
            "verification_failed": "Review task requirements. Ensure output matches spec exactly.",
        }
        
        for key, strategy in strategies.items():
            if key in failure_reason.lower():
                return strategy
        
        return "Re-analyze task requirements and try a different approach."
    
    def create_correction(
        self,
        task_id: str,
        original: str,
        corrected: str,
        correction_type: str,
        source: str = "self"
    ) -> Correction:
        """Record a correction"""
        correction = Correction(
            task_id=task_id,
            original_output=original,
            corrected_output=corrected,
            correction_type=correction_type,
            source=source
        )
        self.corrections.append(correction)
        return correction


class LearningEngine:
    """
    Learning from task outcomes - builds solution library.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.solutions: Dict[str, LearnedSolution] = {}
        self.lesson_history: List[Dict[str, Any]] = []
    
    def learn_from_success(
        self,
        task: str,
        task_type: str,
        solution: str,
        verification: str
    ):
        """Learn from successful task completion"""
        # Create or update solution
        solution_key = f"{task_type}:{task[:30].lower()}"
        
        if solution_key in self.solutions:
            sol = self.solutions[solution_key]
            sol.success_count += 1
            sol.solution = solution  # Update with best solution
            sol.verification = verification
            sol.last_used = datetime.utcnow().isoformat()
        else:
            self.solutions[solution_key] = LearnedSolution(
                problem_type=task_type,
                problem_pattern=task[:50].lower(),
                solution=solution,
                verification=verification,
                success_count=1
            )
        
        # Record lesson
        lesson = {
            "type": "success",
            "task_type": task_type,
            "timestamp": datetime.utcnow().isoformat(),
            "lesson": f"Solved {task_type} task successfully"
        }
        self.lesson_history.append(lesson)
    
    def learn_from_failure(
        self,
        task: str,
        task_type: str,
        error: str,
        recovery: str
    ):
        """Learn from failed task"""
        solution_key = f"{task_type}:{task[:30].lower()}"
        
        if solution_key in self.solutions:
            sol = self.solutions[solution_key]
            sol.failure_count += 1
        else:
            self.solutions[solution_key] = LearnedSolution(
                problem_type=task_type,
                problem_pattern=task[:50].lower(),
                solution=f"ERROR: {error}",
                verification=f"RECOVERED: {recovery}",
                failure_count=1
            )
        
        lesson = {
            "type": "failure",
            "task_type": task_type,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error,
            "recovery": recovery,
            "lesson": f"Failed {task_type}: {recovery}"
        }
        self.lesson_history.append(lesson)
    
    def get_similar_solution(self, task: str, task_type: str) -> Optional[LearnedSolution]:
        """Find similar solved problem"""
        search_key = f"{task_type}:{task[:30].lower()}"
        
        # Exact match
        if search_key in self.solutions:
            return self.solutions[search_key]
        
        # Partial match
        for key, sol in self.solutions.items():
            if sol.problem_type == task_type:
                if any(word in task.lower() for word in sol.problem_pattern.split()):
                    return sol
        
        return None
    
    def get_lessons(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent lessons"""
        return self.lesson_history[-limit:]
    
    def get_solution_stats(self) -> Dict[str, Any]:
        """Get learning statistics"""
        total = len(self.solutions)
        successful = sum(1 for s in self.solutions.values() if s.success_count > 0)
        failed = sum(1 for s in self.solutions.values() if s.failure_count > 0)
        
        return {
            "total_solutions": total,
            "successful": successful,
            "failed": failed,
            "total_lessons": len(self.lesson_history)
        }


class ConversationMemory:
    """
    Maintains conversation history within a session.
    """
    
    def __init__(self):
        self.messages: List[Dict[str, str]] = []
        self.context_window = 10  # Keep last 10 messages
    
    def add_user_message(self, content: str):
        """Add user message"""
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self._trim()
    
    def add_assistant_message(self, content: str, metadata: Dict = None):
        """Add assistant message"""
        self.messages.append({
            "role": "assistant",
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        })
        self._trim()
    
    def _trim(self):
        """Keep only recent messages"""
        if len(self.messages) > self.context_window * 2:
            self.messages = self.messages[-self.context_window * 2:]
    
    def get_context_for_llm(self) -> str:
        """Get formatted context for LLM"""
        if not self.messages:
            return ""
        
        context = "## Conversation History\n\n"
        for msg in self.messages[-self.context_window:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            context += f"**{role}:** {msg['content'][:200]}\n\n"
        
        return context
    
    def get_last_user_message(self) -> Optional[str]:
        """Get last user message"""
        for msg in reversed(self.messages):
            if msg["role"] == "user":
                return msg["content"]
        return None
    
    def clear(self):
        """Clear conversation history"""
        self.messages.clear()
    
    def export(self) -> List[Dict[str, str]]:
        """Export conversation"""
        return self.messages.copy()