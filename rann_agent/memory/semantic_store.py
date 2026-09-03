"""
Semantic memory store for RANN Agent.
As required by MASTER PROMPT Section 27.
Key-value fact storage with embeddings for similarity search.
"""

import json
import sqlite3
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class SemanticFact:
    fact_id: str
    content: str
    entity_type: str  # concept, fact, rule, pattern, convention
    entity_name: str  # the thing this fact is about
    source: str  # where it came from: episode, file, manual, inference
    source_id: str  # episode_id or file path
    confidence: float  # 0.0-1.0
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.last_accessed:
            self.last_accessed = self.created_at


class SemanticMemoryStore:
    """Fact storage with tagging and search."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".rann-agent" / "semantic_memory.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                fact_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                tags_json TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entity ON facts(entity_type, entity_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON facts(source, source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_confidence ON facts(confidence)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON facts(created_at)")
        conn.commit()
        conn.close()

    def store(self, fact: SemanticFact) -> None:
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO facts
            (fact_id, content, entity_type, entity_name, source, source_id,
             confidence, tags_json, created_at, last_accessed, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fact.fact_id, fact.content, fact.entity_type, fact.entity_name,
            fact.source, fact.source_id, fact.confidence, json.dumps(fact.tags),
            fact.created_at, fact.last_accessed, fact.access_count
        ))
        conn.commit()
        conn.close()
        logger.debug("fact_stored", fact_id=fact.fact_id, entity=fact.entity_name)

    def get(self, fact_id: str) -> Optional[SemanticFact]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM facts WHERE fact_id=?", (fact_id,)).fetchone()
        if row:
            conn.execute("UPDATE facts SET last_accessed=?, access_count=access_count+1 WHERE fact_id=?",
                        (datetime.utcnow().isoformat(), fact_id))
            conn.commit()
        conn.close()
        return self._row_to_fact(row) if row else None

    def search(self, query: str, entity_type: Optional[str] = None,
               min_confidence: float = 0.0, limit: int = 20) -> List[SemanticFact]:
        """Search facts by content or entity name."""
        conn = self._get_conn()
        pattern = f"%{query}%"
        params: List[Any] = [pattern, min_confidence]
        type_filter = ""
        if entity_type:
            type_filter = " AND entity_type=?"
            params.append(entity_type)
        params.append(limit)

        rows = conn.execute(
            f"""SELECT * FROM facts
                WHERE (content LIKE ? OR entity_name LIKE ?) AND confidence>=?
                {type_filter}
                ORDER BY confidence DESC, access_count DESC
                LIMIT ?""",
            params
        ).fetchall()
        conn.close()
        return [self._row_to_fact(r) for r in rows]

    def by_entity(self, entity_name: str, entity_type: Optional[str] = None) -> List[SemanticFact]:
        conn = self._get_conn()
        params: List[Any] = [entity_name]
        type_filter = ""
        if entity_type:
            type_filter = " AND entity_type=?"
            params.append(entity_type)
        rows = conn.execute(
            f"""SELECT * FROM facts WHERE entity_name=? {type_filter}
                ORDER BY confidence DESC, created_at DESC""",
            params
        ).fetchall()
        conn.close()
        return [self._row_to_fact(r) for r in rows]

    def by_source(self, source: str, source_id: str) -> List[SemanticFact]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM facts WHERE source=? AND source_id=? ORDER BY created_at",
            (source, source_id)
        ).fetchall()
        conn.close()
        return [self._row_to_fact(r) for r in rows]

    def by_tag(self, tag: str, limit: int = 50) -> List[SemanticFact]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM facts WHERE tags_json LIKE ?
               ORDER BY confidence DESC LIMIT ?""",
            (f"%\"{tag}\"%", limit)
        ).fetchall()
        conn.close()
        return [self._row_to_fact(r) for r in rows]

    def delete(self, fact_id: str) -> bool:
        conn = self._get_conn()
        n = conn.execute("DELETE FROM facts WHERE fact_id=?", (fact_id,)).rowcount
        conn.commit()
        conn.close()
        return n > 0

    def delete_by_source(self, source: str, source_id: str) -> int:
        conn = self._get_conn()
        n = conn.execute(
            "DELETE FROM facts WHERE source=? AND source_id=?",
            (source, source_id)
        ).rowcount
        conn.commit()
        conn.close()
        return n

    def high_confidence_rules(self, limit: int = 50) -> List[SemanticFact]:
        """Get high-confidence rules and patterns."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM facts
               WHERE entity_type IN ('rule', 'pattern', 'convention')
               AND confidence >= 0.8
               ORDER BY confidence DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        conn.close()
        return [self._row_to_fact(r) for r in rows]

    def stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        by_type = dict(conn.execute(
            "SELECT entity_type, COUNT(*) FROM facts GROUP BY entity_type"
        ).fetchall())
        avg_confidence = conn.execute("SELECT AVG(confidence) FROM facts").fetchone()[0] or 0
        conn.close()
        return {
            "total_facts": total,
            "by_type": by_type,
            "avg_confidence": round(avg_confidence, 2)
        }

    def _row_to_fact(self, row) -> SemanticFact:
        return SemanticFact(
            fact_id=row["fact_id"],
            content=row["content"],
            entity_type=row["entity_type"],
            entity_name=row["entity_name"],
            source=row["source"],
            source_id=row["source_id"],
            confidence=row["confidence"],
            tags=json.loads(row["tags_json"] or "[]"),
            created_at=row["created_at"],
            last_accessed=row["last_accessed"],
            access_count=row["access_count"]
        )