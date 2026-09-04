"""
Task Decomposition System

Breaks complex tasks into smaller, executable subtasks.
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Subtask:
    """A decomposed subtask"""
    id: str
    description: str
    tool_hint: str  # "terminal", "write_file", "read_file", etc.
    depends_on: List[str]  # subtask IDs this depends on
    order: int  # execution order
    estimated_difficulty: str  # "easy", "medium", "hard"


class TaskDecomposer:
    """
    Decompose complex tasks into manageable subtasks.
    """
    
    # Patterns that indicate decomposition needed
    DECOMPOSE_PATTERNS = [
        r"\band\b.*\band\b",  # "do X and do Y and do Z"
        r"\bthen\b",  # "first do X, then do Y"
        r"\bafter that\b",
        r"\bfollowed by\b",
        r"\bsteps?\b",
        r"\bcreate.*and.*also\b",
        r"\bmultiple\b",
        r"\ball\s+\w+\s+files?\b",
        r"\beach\s+\w+\b",
        r"\blist.*\band.*\band\b",
        r"\d+\s+\w+\s+files?",
        r"\bfirst.*second.*third\b",
    ]
    
    # Tool hints based on keywords
    TOOL_HINTS = {
        "create file": "write_file",
        "write file": "write_file",
        "make file": "write_file",
        "delete file": "terminal_rm",
        "remove file": "terminal_rm",
        "list files": "terminal_ls",
        "show files": "terminal_ls",
        "read file": "read_file",
        "view file": "read_file",
        "edit file": "write_file",
        "modify file": "write_file",
        "run": "terminal",
        "execute": "terminal",
        "install": "terminal",
        "git": "git",
        "commit": "git",
        "push": "git",
        "search": "search_files",
        "find": "search_files",
        "grep": "search_files",
        "code": "code_exec",
        "test": "terminal",
        "build": "terminal",
        "compile": "terminal",
    }
    
    def __init__(self):
        self.decomposition_cache: Dict[str, List[Subtask]] = {}
    
    def should_decompose(self, task: str) -> bool:
        """Check if task needs decomposition"""
        task_lower = task.lower()
        
        # Check for decomposition patterns
        for pattern in self.DECOMPOSE_PATTERNS:
            if re.search(pattern, task_lower):
                return True
        
        # Check for multiple verbs (and, or patterns)
        verbs = self._count_action_verbs(task_lower)
        if verbs >= 3:
            return True
        
        return False
    
    def _count_action_verbs(self, text: str) -> int:
        """Count action verbs suggesting multiple tasks"""
        action_verbs = [
            "create", "make", "delete", "remove", "write", "read", "edit",
            "modify", "run", "execute", "install", "build", "test", "check",
            "list", "show", "find", "search", "get", "set", "update", "add"
        ]
        count = sum(1 for verb in action_verbs if verb in text)
        return count
    
    def decompose(self, task: str) -> List[Subtask]:
        """Decompose a complex task into subtasks"""
        # Check cache
        cache_key = task[:100]
        if cache_key in self.decomposition_cache:
            return self.decomposition_cache[cache_key]
        
        subtasks = []
        
        # Split by conjunctions and separators
        parts = self._split_task(task)
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            
            # Determine tool hint
            tool_hint = self._guess_tool(part)
            
            # Determine dependencies
            depends_on = []
            if i > 0:
                # First few can run in parallel, later ones depend on earlier
                if i >= 2:
                    depends_on = [subtasks[i-1].id]
            
            subtask = Subtask(
                id=f"step_{i+1}",
                description=part,
                tool_hint=tool_hint,
                depends_on=depends_on,
                order=i,
                estimated_difficulty=self._estimate_difficulty(part)
            )
            subtasks.append(subtask)
        
        # Cache result
        self.decomposition_cache[cache_key] = subtasks
        return subtasks
    
    def _split_task(self, task: str) -> List[str]:
        """Split task into parts"""
        # Split by common separators
        separators = [
            r"\s+and\s+",
            r"\s+then\s+",
            r"\s*,\s*",
            r"\s+after\s+that\s+",
            r"\s+followed by\s+",
            r";\s*",
            r"\n",
        ]
        
        parts = [task]
        for sep in separators:
            new_parts = []
            for part in parts:
                split = re.split(sep, part, flags=re.IGNORECASE)
                new_parts.extend(split)
            parts = new_parts
        
        # Clean up
        parts = [p.strip() for p in parts if p.strip()]
        
        # If still one part, try splitting by numbered steps
        if len(parts) == 1:
            numbered = re.split(r"\d+[\.\)]\s*", task)
            if len(numbered) > 1:
                parts = [p.strip() for p in numbered if p.strip()]
        
        return parts
    
    def _guess_tool(self, part: str) -> str:
        """Guess which tool to use for this part"""
        part_lower = part.lower()
        
        for keyword, tool in self.TOOL_HINTS.items():
            if keyword in part_lower:
                return tool
        
        return "terminal"  # Default
    
    def _estimate_difficulty(self, part: str) -> str:
        """Estimate difficulty of a subtask"""
        # Simple heuristics
        difficulty_indicators = {
            "hard": ["recursive", "complex", "algorithm", "optimize", "design"],
            "medium": ["create", "modify", "refactor", "test", "debug"],
            "easy": ["list", "show", "read", "check", "simple"]
        }
        
        part_lower = part.lower()
        for level, indicators in difficulty_indicators.items():
            if any(ind in part_lower for ind in indicators):
                return level
        
        return "medium"
    
    def get_execution_order(self, subtasks: List[Subtask]) -> List[List[Subtask]]:
        """Get execution order grouping parallelizable subtasks"""
        if not subtasks:
            return []
        
        # Group by dependency level
        levels = []
        remaining = subtasks.copy()
        
        while remaining:
            # Find subtasks with no unresolved dependencies
            ready = []
            for subtask in remaining:
                deps_resolved = all(
                    dep not in [s.id for s in remaining]
                    for dep in subtask.depends_on
                )
                if deps_resolved:
                    ready.append(subtask)
            
            if not ready:
                # Circular dependency or error - just take remaining
                ready = remaining[:1]
            
            levels.append(ready)
            for subtask in ready:
                remaining.remove(subtask)
        
        return levels


class ErrorRecovery:
    """
    Smart error recovery suggestions.
    """
    
    # Common errors and their fixes
    ERROR_PATTERNS = {
        r"no such file or directory": {
            "type": "file_not_found",
            "fix": "Check if file exists. Use 'ls' to verify path.",
            "retry": True
        },
        r"permission denied": {
            "type": "permission_denied",
            "fix": "Check file permissions. Try using sudo or changing file ownership.",
            "retry": False
        },
        r"syntax error": {
            "type": "syntax_error",
            "fix": "Review code syntax. Check for missing brackets, quotes, or semicolons.",
            "retry": True
        },
        r"import error": {
            "type": "import_error",
            "fix": "Check if module is installed. Try 'pip install <module>'.",
            "retry": True
        },
        r"timeout": {
            "type": "timeout",
            "fix": "Task took too long. Break into smaller steps or increase timeout.",
            "retry": False
        },
        r"connection error": {
            "type": "network_error",
            "fix": "Check internet connection. Retry the request.",
            "retry": True
        },
        r"out of memory": {
            "type": "memory_error",
            "fix": "Reduce task scope or process in smaller chunks.",
            "retry": False
        },
        r"too many requests": {
            "type": "rate_limit",
            "fix": "Rate limited. Wait a moment and retry.",
            "retry": True
        },
        r"invalid.*argument": {
            "type": "invalid_argument",
            "fix": "Check function arguments. Review documentation.",
            "retry": False
        },
        r"not found": {
            "type": "not_found",
            "fix": "Resource not found. Verify the path or URL.",
            "retry": False
        },
    }
    
    @classmethod
    def analyze_error(cls, error_message: str) -> Dict[str, Any]:
        """Analyze error and suggest recovery"""
        error_lower = error_message.lower()
        
        for pattern, info in cls.ERROR_PATTERNS.items():
            if re.search(pattern, error_lower, re.IGNORECASE):
                return {
                    "matched": True,
                    "error_type": info["type"],
                    "fix_suggestion": info["fix"],
                    "can_retry": info["retry"],
                    "original_error": error_message
                }
        
        # Generic fallback
        return {
            "matched": False,
            "error_type": "unknown",
            "fix_suggestion": "An unexpected error occurred. Try again with more specific instructions.",
            "can_retry": True,
            "original_error": error_message
        }
    
    @classmethod
    def get_fix_command(cls, error_type: str) -> Optional[str]:
        """Get a command that might fix the error"""
        fix_commands = {
            "file_not_found": "ls -la",
            "permission_denied": "chmod +x",
            "import_error": "pip install -r requirements.txt",
            "timeout": None,  # No simple fix
            "network_error": "curl -I https://example.com",
            "memory_error": None,  # No simple fix
            "rate_limit": None,  # Just wait
            "invalid_argument": None,  # Need more info
            "not_found": "find . -name",
        }
        return fix_commands.get(error_type)


class SkillRecommender:
    """
    Recommend skills based on task context.
    """
    
    # Task to skill mapping
    TASK_SKILL_MAP = {
        "deploy": ["deploy-static", "github-repo-management"],
        "github": ["github-pr-workflow", "github-issues"],
        "debug": ["systematic-debugging", "python-debugpy"],
        "test": ["test-driven-development"],
        "document": ["documentation-authoring"],
        "api": ["serving-llms-vllm"],
        "llm": ["llama-cpp", "serving-llms-vllm", "huggingface-hub"],
        "database": ["memory-management"],
        "web": ["deploy-static", "debug-deployed-webapp"],
        "bot": ["telegram-bot-aiogram-build-run-manage", "crypto-telegram-bot"],
        "crypto": ["ai-meme-sniper", "crypto-telegram-bot"],
        "smart home": ["openhue"],
        "email": ["himalaya"],
        "notes": ["obsidian"],
    }
    
    @classmethod
    def recommend(cls, task: str) -> List[str]:
        """Recommend skills for a task"""
        task_lower = task.lower()
        recommendations = []
        
        for keywords, skills in cls.TASK_SKILL_MAP.items():
            if keywords in task_lower:
                recommendations.extend(skills)
        
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for skill in recommendations:
            if skill not in seen:
                seen.add(skill)
                unique.append(skill)
        
        return unique[:5]  # Limit to 5 recommendations
    
    @classmethod
    def get_skill_description(cls, skill_name: str) -> str:
        """Get description of a skill"""
        descriptions = {
            "deploy-static": "Deploy static sites to Vercel or GitHub Pages",
            "github-pr-workflow": "GitHub PR lifecycle with branch, commit, CI, merge",
            "systematic-debugging": "4-phase root cause debugging",
            "python-debugpy": "Debug Python with pdb and debugpy",
            "test-driven-development": "TDD with RED-GREEN-REFACTOR cycle",
            "documentation-authoring": "Write bilingual README and tutorials",
            "llama-cpp": "Local GGUF inference and model discovery",
            "serving-llms-vllm": "High-throughput LLM serving with vLLM",
            "huggingface-hub": "HF CLI for model/dataset operations",
            "telegram-bot-aiogram-build-run-manage": "Build aiogram 3.x Telegram bots",
            "ai-meme-sniper": "AI auto-snipe meme coins",
            "openhue": "Control Philips Hue lights and scenes",
            "himalaya": "IMAP/SMTP email from terminal",
            "obsidian": "Read/write/edit Obsidian vault notes",
        }
        return descriptions.get(skill_name, "No description available")