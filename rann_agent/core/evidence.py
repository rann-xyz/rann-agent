"""
Evidence Ledger

Records and manages evidence for task verification.
Implements V3 Section 12 specification.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import uuid
import json
import structlog
from pathlib import Path

logger = structlog.get_logger()

EVIDENCE_DIR = Path.home() / ".rann_agent" / "evidence"


class EvidenceType(Enum):
    """Types of evidence that can be recorded"""
    COMMAND = "command"
    TEST = "test"
    FILE_DIFF = "file_diff"
    GIT_DIFF = "git_diff"
    HTTP = "http"
    BROWSER = "browser"
    BENCHMARK = "benchmark"
    STATIC_ANALYSIS = "static_analysis"
    SECURITY_SCAN = "security_scan"
    ARTIFACT = "artifact"


@dataclass
class Evidence:
    """
    Immutable evidence record.

    Attributes:
        evidence_id: Unique identifier for this evidence
        claim: The claim this evidence supports
        evidence_type: Type of evidence
        source: Source of the evidence (tool name, file path, etc.)
        data: Evidence data dictionary
        timestamp: ISO format timestamp
        validated: Whether this evidence has been validated
    """
    evidence_id: str
    claim: str
    evidence_type: EvidenceType
    source: str
    data: Dict[str, Any]
    timestamp: str
    validated: bool = False

    def __post_init__(self):
        """Validate evidence after initialization"""
        if not self.evidence_id:
            self.evidence_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "evidence_id": self.evidence_id,
            "claim": self.claim,
            "evidence_type": self.evidence_type.value,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp,
            "validated": self.validated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evidence":
        """Deserialize from dictionary"""
        return cls(
            evidence_id=data["evidence_id"],
            claim=data["claim"],
            evidence_type=EvidenceType(data["evidence_type"]),
            source=data["source"],
            data=data["data"],
            timestamp=data["timestamp"],
            validated=data.get("validated", False),
        )


class EvidenceLedger:
    """
    Persistent evidence ledger for recording and searching evidence.

    Evidence is stored in memory and persisted to disk for auditability.
    """

    def __init__(self, ledger_id: Optional[str] = None):
        self.ledger_id = ledger_id or str(uuid.uuid4())
        self._evidence: Dict[str, Evidence] = {}
        self._evidence_dir = EVIDENCE_DIR / self.ledger_id
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("evidence_ledger_init", ledger_id=self.ledger_id)

    def record(
        self,
        claim: str,
        evidence_type: EvidenceType,
        source: str,
        data: Dict[str, Any],
    ) -> Evidence:
        """
        Record new evidence.

        Args:
            claim: The claim this evidence supports
            evidence_type: Type of evidence
            source: Source of the evidence
            data: Evidence data

        Returns:
            The created Evidence object
        """
        evidence = Evidence(
            evidence_id=str(uuid.uuid4()),
            claim=claim,
            evidence_type=evidence_type,
            source=source,
            data=data,
            timestamp=datetime.now().isoformat(),
            validated=False,
        )

        self._evidence[evidence.evidence_id] = evidence
        self._persist_evidence(evidence)

        logger.info(
            "evidence_recorded",
            evidence_id=evidence.evidence_id,
            claim=claim,
            evidence_type=evidence_type.value,
            source=source,
        )

        return evidence

    def get(self, evidence_id: str) -> Optional[Evidence]:
        """
        Get evidence by ID.

        Args:
            evidence_id: The evidence ID to look up

        Returns:
            Evidence if found, None otherwise
        """
        return self._evidence.get(evidence_id)

    def search(self, claim_substring: str) -> List[Evidence]:
        """
        Search for evidence by claim substring.

        Args:
            claim_substring: Substring to search for in claims

        Returns:
            List of matching Evidence objects
        """
        substring_lower = claim_substring.lower()
        matches = [
            evidence
            for evidence in self._evidence.values()
            if substring_lower in evidence.claim.lower()
        ]

        logger.debug(
            "evidence_search",
            query=claim_substring,
            result_count=len(matches)
        )

        return matches

    def search_by_type(self, evidence_type: EvidenceType) -> List[Evidence]:
        """
        Search for evidence by type.

        Args:
            evidence_type: Type of evidence to search for

        Returns:
            List of matching Evidence objects
        """
        return [
            evidence
            for evidence in self._evidence.values()
            if evidence.evidence_type == evidence_type
        ]

    def validate(self, evidence_id: str) -> bool:
        """
        Mark evidence as validated.

        Args:
            evidence_id: The evidence ID to validate

        Returns:
            True if evidence was found and validated, False otherwise
        """
        evidence = self._evidence.get(evidence_id)
        if evidence is None:
            logger.warning("evidence_not_found_for_validation", evidence_id=evidence_id)
            return False

        evidence.validated = True
        self._persist_evidence(evidence)

        logger.info("evidence_validated", evidence_id=evidence_id)
        return True

    def invalidate(self, evidence_id: str) -> bool:
        """
        Mark evidence as invalidated.

        Args:
            evidence_id: The evidence ID to invalidate

        Returns:
            True if evidence was found and invalidated, False otherwise
        """
        evidence = self._evidence.get(evidence_id)
        if evidence is None:
            return False

        evidence.validated = False
        self._persist_evidence(evidence)

        logger.info("evidence_invalidated", evidence_id=evidence_id)
        return True

    def export(self) -> List[Dict[str, Any]]:
        """
        Export all evidence as list of dictionaries.

        Returns:
            List of evidence dictionaries
        """
        return [e.to_dict() for e in self._evidence.values()]

    def export_validated(self) -> List[Dict[str, Any]]:
        """
        Export only validated evidence.

        Returns:
            List of validated evidence dictionaries
        """
        return [
            e.to_dict()
            for e in self._evidence.values()
            if e.validated
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about recorded evidence"""
        type_counts: Dict[str, int] = {}
        validated_count = 0

        for evidence in self._evidence.values():
            type_key = evidence.evidence_type.value
            type_counts[type_key] = type_counts.get(type_key, 0) + 1
            if evidence.validated:
                validated_count += 1

        return {
            "total_count": len(self._evidence),
            "validated_count": validated_count,
            "unvalidated_count": len(self._evidence) - validated_count,
            "by_type": type_counts,
            "ledger_id": self.ledger_id,
        }

    def _persist_evidence(self, evidence: Evidence) -> None:
        """Persist single evidence to disk"""
        try:
            evidence_file = self._evidence_dir / f"{evidence.evidence_id}.json"
            evidence_file.write_text(json.dumps(evidence.to_dict(), indent=2))
        except Exception as e:
            logger.warning(
                "evidence_persist_failed",
                evidence_id=evidence.evidence_id,
                error=str(e)
            )

    def load_all(self) -> int:
        """
        Load all evidence from disk.

        Returns:
            Number of evidence records loaded
        """
        if not self._evidence_dir.exists():
            return 0

        loaded = 0
        for evidence_file in self._evidence_dir.glob("*.json"):
            try:
                data = json.loads(evidence_file.read_text())
                evidence = Evidence.from_dict(data)
                self._evidence[evidence.evidence_id] = evidence
                loaded += 1
            except Exception as e:
                logger.warning(
                    "evidence_load_failed",
                    file=str(evidence_file),
                    error=str(e)
                )

        logger.info("evidence_loaded", count=loaded, ledger_id=self.ledger_id)
        return loaded

    def clear(self) -> None:
        """Clear all evidence from memory and disk"""
        self._evidence.clear()
        try:
            for evidence_file in self._evidence_dir.glob("*.json"):
                evidence_file.unlink()
            logger.info("evidence_cleared", ledger_id=self.ledger_id)
        except Exception as e:
            logger.warning("evidence_clear_failed", error=str(e))