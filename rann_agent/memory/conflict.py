"""
Memory conflict detection for RANN Agent.
As required by MASTER PROMPT Section 28.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import structlog

logger = structlog.get_logger()


class ConflictType(Enum):
    CONTRADICTORY = "contradictory"
    OUTDATED = "outdated"
    PARTIAL = "partial"


class ConflictResolution(Enum):
    KEEP_BOTH = "keep_both"
    PREFER_NEWER = "prefer_newer"
    PREFER_VALIDATED = "prefer_validated"
    PREFER_PROJECT = "prefer_project"
    INVALIDATE = "invalidate"
    REQUEST_REVIEW = "request_review"


@dataclass
class MemoryConflict:
    conflict_id: str
    memory_a_id: str
    memory_b_id: str
    conflict_type: ConflictType
    evidence_a: str
    evidence_b: str
    resolution: Optional[ConflictResolution] = None
    confidence: float = 0.5
    timestamp: str = ""


@dataclass
class ResolutionResult:
    resolved: bool
    action: ConflictResolution
    winner_id: Optional[str] = None
    loser_id: Optional[str] = None


class ConflictResolver:
    """
    Detects and resolves memory conflicts.

    Memory conflicts occur when:
    - Two memories contain contradictory information
    - One memory is outdated (superseded by newer)
    - One memory is partial (incomplete version of another)
    """

    def __init__(self) -> None:
        self._conflicts: Dict[str, MemoryConflict] = {}

    def detect(
        self,
        new_memory: Dict[str, Any],
        existing_memories: List[Dict[str, Any]],
    ) -> Optional[MemoryConflict]:
        """
        Check if new_memory conflicts with any existing memory.
        Returns a MemoryConflict if detected.
        """
        new_content = new_memory.get("content", "").lower()
        new_id = new_memory.get("memory_id", "")
        new_confidence = new_memory.get("confidence", 0.5)

        for existing in existing_memories:
            existing_id = existing.get("memory_id", "")
            if existing_id == new_id:
                continue

            existing_content = existing.get("content", "").lower()

            # Check for contradiction (direct negation)
            if self._is_contradiction(new_content, existing_content):
                conflict = MemoryConflict(
                    conflict_id=f"conflict_{new_id[:8]}_{existing_id[:8]}",
                    memory_a_id=new_id,
                    memory_b_id=existing_id,
                    conflict_type=ConflictType.CONTRADICTORY,
                    evidence_a=new_memory.get("content", "")[:200],
                    evidence_b=existing.get("content", "")[:200],
                    confidence=min(new_confidence, existing.get("confidence", 0.5)),
                )
                self._conflicts[conflict.conflict_id] = conflict
                logger.warning(
                    "memory_conflict_detected",
                    conflict_id=conflict.conflict_id,
                    type="contradictory",
                    memory_a=new_id,
                    memory_b=existing_id,
                )
                return conflict

            # Check for outdated (same topic, older timestamp)
            if self._is_same_topic(new_content, existing_content):
                new_time = new_memory.get("created_at", "")
                existing_time = existing.get("created_at", "")
                if existing_time > new_time:
                    conflict = MemoryConflict(
                        conflict_id=f"conflict_{new_id[:8]}_{existing_id[:8]}",
                        memory_a_id=new_id,
                        memory_b_id=existing_id,
                        conflict_type=ConflictType.OUTDATED,
                        evidence_a=new_memory.get("content", "")[:200],
                        evidence_b=existing.get("content", "")[:200],
                        confidence=new_confidence * 0.5,
                    )
                    self._conflicts[conflict.conflict_id] = conflict
                    logger.info(
                        "memory_conflict_detected",
                        conflict_id=conflict.conflict_id,
                        type="outdated",
                        memory_a=new_id,
                        memory_b=existing_id,
                    )
                    return conflict

        return None

    def resolve(self, conflict: MemoryConflict) -> ResolutionResult:
        """
        Automatically resolve a memory conflict.
        """
        if conflict.conflict_type == ConflictType.CONTRADICTORY:
            # For contradictions, prefer validated evidence
            if conflict.confidence >= 0.7:
                return ResolutionResult(
                    resolved=True,
                    action=ConflictResolution.PREFER_VALIDATED,
                    winner_id=conflict.memory_a_id,
                    loser_id=conflict.memory_b_id,
                )
            else:
                return ResolutionResult(
                    resolved=False,
                    action=ConflictResolution.REQUEST_REVIEW,
                )

        elif conflict.conflict_type == ConflictType.OUTDATED:
            return ResolutionResult(
                resolved=True,
                action=ConflictResolution.PREFER_NEWER,
                winner_id=conflict.memory_a_id,
                loser_id=conflict.memory_b_id,
            )

        return ResolutionResult(
            resolved=False,
            action=ConflictResolution.KEEP_BOTH,
        )

    def _is_contradiction(self, text_a: str, text_b: str) -> bool:
        """Check if two texts are contradictory."""
        # Simple negation detection
        negations_a = {"not", "no", "never", "doesn't", "doesn't", "isn't", "aren't", "wasn't", "weren't", "won't", "wouldn't", "can't", "couldn't", "shouldn't"}
        negations_b = {"not", "no", "never", "doesn't", "isn't", "aren't", "wasn't", "weren't", "won't", "wouldn't", "can't", "couldn't", "shouldn't"}

        words_a = set(text_a.split())
        words_b = set(text_b.split())

        # Check if one has negation the other doesn't for same subject
        for neg in negations_a:
            if neg in words_a and neg not in words_b:
                # Check if they share significant content
                shared = words_a & words_b
                if len(shared) > 5:
                    return True
        return False

    def _is_same_topic(self, text_a: str, text_b: str) -> bool:
        """Check if two texts are about the same topic."""
        words_a = set(text_a.split())
        words_b = set(text_b.split())
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "shall", "can", "need", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "during", "before", "after", "above", "below", "between", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "each", "few", "more", "most", "other", "some", "such", "only", "own", "same", "so", "than", "too", "very"}

        content_a = words_a - stopwords
        content_b = words_b - stopwords

        if not content_a or not content_b:
            return False

        overlap = len(content_a & content_b)
        union = len(content_a | content_b)
        jaccard = overlap / union if union > 0 else 0

        return jaccard > 0.5

    def get_conflicts(self) -> List[MemoryConflict]:
        """Get all detected conflicts."""
        return list(self._conflicts.values())