"""
Procedural Memory

Stores skills, workflows, and procedures.
As required by MASTER PROMPT Section 26.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
import structlog
import json
import os

logger = structlog.get_logger()


@dataclass
class Skill:
    """A stored skill or procedure"""
    skill_id: str
    name: str
    description: str
    category: str
    code: str
    language: str = "python"
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    author: str = "system"
    tags: List[str] = field(default_factory=list)
    parameters: List[Dict[str, str]] = field(default_factory=list)  # [{name, type, description}]
    success_count: int = 0
    failure_count: int = 0
    avg_execution_time_ms: float = 0
    enabled: bool = True


class ProceduralMemory:
    """
    Stores and retrieves skills, workflows, and procedures.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self._skills: Dict[str, Skill] = {}
        self._storage_path = storage_path
        self._log = structlog.get_logger().bind(component="procedural_memory")
        
        if storage_path:
            self._load_from_disk()
        else:
            self._init_builtin_skills()
    
    def _init_builtin_skills(self) -> None:
        """Initialize built-in skills"""
        builtin = [
            Skill(
                skill_id="code_review",
                name="Code Review",
                description="Review code for bugs, style, and security",
                category="development",
                code="def code_review(code: str) -> dict:\n    # Implementation\n    return {'issues': [], 'score': 10}",
                tags=["code", "review", "quality"]
            ),
            Skill(
                skill_id="write_tests",
                name="Write Tests",
                description="Generate unit tests for a function",
                category="development",
                code="def write_tests(func_code: str) -> str:\n    # Implementation\n    return 'import pytest\\n...'",
                tags=["testing", "pytest", "tdd"]
            ),
            Skill(
                skill_id="explain_error",
                name="Explain Error",
                description="Explain an error message and suggest fixes",
                category="debugging",
                code="def explain_error(error: str, context: str) -> str:\n    # Implementation\n    return 'Explanation...'",
                tags=["error", "debug", "explain"]
            ),
            Skill(
                skill_id="refactor_code",
                name="Refactor Code",
                description="Refactor code for better readability and performance",
                category="development",
                code="def refactor_code(code: str) -> str:\n    # Implementation\n    return code",
                tags=["refactor", "clean", "improve"]
            ),
        ]
        
        for skill in builtin:
            self._skills[skill.skill_id] = skill
    
    def store(self, skill: Skill) -> None:
        """Store a skill"""
        skill.updated_at = datetime.now()
        self._skills[skill.skill_id] = skill
        self._log.info("skill_stored", skill_id=skill.skill_id)
        
        if self._storage_path:
            self._save_to_disk(skill)
    
    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)
    
    def search(self, query: str, category: Optional[str] = None) -> List[Skill]:
        """Search skills by name, description, or tags"""
        results = []
        query_lower = query.lower()
        
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            if category and skill.category != category:
                continue
            
            if (query_lower in skill.name.lower() or
                query_lower in skill.description.lower() or
                any(query_lower in tag.lower() for tag in skill.tags)):
                results.append(skill)
        
        return sorted(results, key=lambda s: s.success_count / max(1, s.success_count + s.failure_count), reverse=True)
    
    def get_by_category(self, category: str) -> List[Skill]:
        return [s for s in self._skills.values() if s.category == category and s.enabled]
    
    def record_execution(self, skill_id: str, success: bool, execution_time_ms: float) -> None:
        """Record skill execution result"""
        skill = self._skills.get(skill_id)
        if not skill:
            return
        
        if success:
            skill.success_count += 1
        else:
            skill.failure_count += 1
        
        # Update rolling average
        n = skill.success_count + skill.failure_count
        skill.avg_execution_time_ms = (
            (skill.avg_execution_time_ms * (n - 1) + execution_time_ms) / n
        )
    
    def get_best_skill(self, task: str, category: Optional[str] = None) -> Optional[Skill]:
        """Get the best performing skill for a task"""
        candidates = self.search(task, category)
        if not candidates:
            return None
        return candidates[0]
    
    def _save_to_disk(self, skill: Skill) -> None:
        if not self._storage_path:
            return
        path = os.path.join(self._storage_path, f"{skill.skill_id}.json")
        with open(path, "w") as f:
            json.dump({
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "code": skill.code,
                "language": skill.language,
                "version": skill.version,
                "tags": skill.tags,
                "success_count": skill.success_count,
                "failure_count": skill.failure_count
            }, f)
    
    def _load_from_disk(self) -> None:
        if not self._storage_path or not os.path.exists(self._storage_path):
            self._init_builtin_skills()
            return
        
        for filename in os.listdir(self._storage_path):
            if filename.endswith(".json"):
                path = os.path.join(self._storage_path, filename)
                with open(path) as f:
                    data = json.load(f)
                    skill = Skill(**data)
                    self._skills[skill.skill_id] = skill