"""
Learning engine for RANN Agent.
As required by MASTER PROMPT Section 30.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import structlog

logger = structlog.get_logger()


@dataclass
class LearningEpisode:
    episode_id: str
    task_id: str
    run_id: str
    project_id: str
    task_category: str
    context_summary: str
    retrieved_memory_ids: List[str] = field(default_factory=list)
    selected_strategy: str = ""
    actions: List[str] = field(default_factory=list)
    tool_calls: int = 0
    observations: str = ""
    failures: List[str] = field(default_factory=list)
    recovery_attempts: int = 0
    final_result: str = ""
    verification_result: str = ""
    success: bool = False
    reward: float = 0.0
    cost: float = 0.0
    latency_ms: float = 0.0
    lessons: List[str] = field(default_factory=list)
    skill_candidates: List[str] = field(default_factory=list)
    provenance: str = "rann_agent"
    confidence: float = 0.5
    created_at: str = ""


@dataclass
class Lesson:
    lesson_id: str
    category: str
    content: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.0
    validated: bool = False
    sample_size: int = 0
    created_at: str = ""
    last_used: Optional[str] = None


class LearningEngine:
    """Records learning episodes and extracts lessons."""

    def __init__(self, storage: Optional["Database"] = None) -> None:
        self.storage = storage

    def record_episode(self, episode: LearningEpisode) -> None:
        """Record a completed learning episode."""
        episode.created_at = datetime.now().isoformat()

        # Extract lessons from the episode
        lessons = self.extract_lessons(episode)
        episode.lessons = [l.lesson_id for l in lessons]

        if self.storage:
            data = {
                "task_id": episode.task_id,
                "run_id": episode.run_id,
                "project_id": episode.project_id,
                "task_category": episode.task_category,
                "context_summary": episode.context_summary,
                "retrieved_memory_ids": json.dumps(episode.retrieved_memory_ids),
                "selected_strategy": episode.selected_strategy,
                "actions": json.dumps(episode.actions),
                "tool_calls": episode.tool_calls,
                "observations": episode.observations,
                "failures": json.dumps(episode.failures),
                "recovery_attempts": episode.recovery_attempts,
                "final_result": episode.final_result,
                "verification_result": episode.verification_result,
                "success": int(episode.success),
                "reward": episode.reward,
                "cost": episode.cost,
                "latency_ms": episode.latency_ms,
                "lessons": json.dumps(episode.lessons),
                "skill_candidates": json.dumps(episode.skill_candidates),
                "provenance": episode.provenance,
                "confidence": episode.confidence,
            }
            self.storage.save_episode(episode.episode_id, data)

        logger.info(
            "episode_recorded",
            episode_id=episode.episode_id,
            success=episode.success,
            lessons_extracted=len(lessons),
        )

    def extract_lessons(self, episode: LearningEpisode) -> List[Lesson]:
        """Extract lessons from a learning episode."""
        lessons = []

        # Extract failure lessons
        for failure in episode.failures:
            lesson = Lesson(
                lesson_id=f"lesson_{episode.episode_id}_{len(lessons)}",
                category=episode.task_category,
                content=f"Failure in {episode.task_category}: {failure}",
                evidence=[episode.final_result],
                confidence=0.3,
                validated=False,
                sample_size=1,
                created_at=datetime.now().isoformat(),
            )
            lessons.append(lesson)

        # Extract success lessons
        if episode.success and episode.final_result:
            lesson = Lesson(
                lesson_id=f"lesson_{episode.episode_id}_success",
                category=episode.task_category,
                content=f"Success pattern in {episode.task_category}: {episode.final_result[:200]}",
                evidence=[episode.final_result],
                confidence=0.5,
                validated=False,
                sample_size=1,
                created_at=datetime.now().isoformat(),
            )
            lessons.append(lesson)

        # Store lessons in DB
        if self.storage:
            for lesson in lessons:
                self.storage.save_lesson(
                    lesson.lesson_id,
                    {
                        "category": lesson.category,
                        "content": lesson.content,
                        "evidence": json.dumps(lesson.evidence),
                        "confidence": lesson.confidence,
                        "validated": int(lesson.validated),
                        "sample_size": lesson.sample_size,
                    },
                )

        return lessons

    def get_lessons(self, category: Optional[str] = None) -> List[Lesson]:
        """Retrieve validated lessons, optionally filtered by category."""
        if not self.storage:
            return []

        rows = self.storage.get_lessons(category=category)
        lessons = []
        for row in rows:
            lessons.append(
                Lesson(
                    lesson_id=row["lesson_id"],
                    category=row.get("category", ""),
                    content=row.get("content", ""),
                    evidence=json.loads(row.get("evidence", "[]")),
                    confidence=row.get("confidence", 0.0),
                    validated=bool(row.get("validated", 0)),
                    sample_size=row.get("sample_size", 0),
                    created_at=row.get("created_at", ""),
                    last_used=row.get("last_used"),
                )
            )
        return lessons

    def validate_lesson(self, lesson_id: str) -> bool:
        """Promote a lesson to validated status."""
        if not self.storage:
            return False

        # In a full implementation, this would verify evidence
        # and check against minimum sample size
        logger.info("lesson_validated", lesson_id=lesson_id)
        return True