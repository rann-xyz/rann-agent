"""
Episodic memory store for RANN Agent.
As required by MASTER PROMPT Section 27.
Stores agent experience as episodes (goal → action → result → learning).
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
import structlog

logger = structlog.get_logger()


@dataclass
class EpisodicEpisode:
    episode_id: str
    task_goal: str
    task_category: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    outcome: str = ""  # success, failure, cancelled, partial
    lessons: List[str] = field(default_factory=list)
    turns: int = 0
    tokens_used: int = 0
    duration_seconds: float = 0.0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class EpisodicMemoryStore:
    """Stores agent experiences as searchable episodes."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".rann-agent" / "episodic_memory.db"
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
            CREATE TABLE IF NOT EXISTS episodes (
                episode_id TEXT PRIMARY KEY,
                task_goal TEXT NOT NULL,
                task_category TEXT DEFAULT '',
                actions_json TEXT DEFAULT '[]',
                observations_json TEXT DEFAULT '[]',
                outcome TEXT NOT NULL,
                lessons_json TEXT DEFAULT '[]',
                turns INTEGER DEFAULT 0,
                tokens_used INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_outcome ON episodes(outcome)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON episodes(task_category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON episodes(created_at)")
        conn.commit()
        conn.close()

    def store(self, episode: EpisodicEpisode) -> None:
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO episodes
            (episode_id, task_goal, task_category, actions_json, observations_json,
             outcome, lessons_json, turns, tokens_used, duration_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            episode.episode_id,
            episode.task_goal,
            episode.task_category,
            json.dumps(episode.actions),
            json.dumps(episode.observations),
            episode.outcome,
            json.dumps(episode.lessons),
            episode.turns,
            episode.tokens_used,
            episode.duration_seconds,
            episode.created_at
        ))
        conn.commit()
        conn.close()
        logger.info("episode_stored", episode_id=episode.episode_id, outcome=episode.outcome)

    def get(self, episode_id: str) -> Optional[EpisodicEpisode]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM episodes WHERE episode_id=?", (episode_id,)).fetchone()
        conn.close()
        return self._row_to_episode(row) if row else None

    def search(self, query: str, limit: int = 20) -> List[EpisodicEpisode]:
        """Full-text search over task goals and lessons."""
        conn = self._get_conn()
        pattern = f"%{query}%"
        rows = conn.execute(
            """SELECT * FROM episodes
               WHERE task_goal LIKE ? OR lessons_json LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (pattern, pattern, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_episode(r) for r in rows]

    def by_outcome(self, outcome: str, limit: int = 50) -> List[EpisodicEpisode]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM episodes WHERE outcome=? ORDER BY created_at DESC LIMIT ?",
            (outcome, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_episode(r) for r in rows]

    def by_category(self, category: str, limit: int = 50) -> List[EpisodicEpisode]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM episodes WHERE task_category=? ORDER BY created_at DESC LIMIT ?",
            (category, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_episode(r) for r in rows]

    def recent(self, limit: int = 20) -> List[EpisodicEpisode]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [self._row_to_episode(r) for r in rows]

    def similar_tasks(self, task_goal: str, limit: int = 5) -> List[EpisodicEpisode]:
        """Find episodes with similar task goals."""
        words = task_goal.lower().split()
        if not words:
            return []
        # Simple approach: search by first significant word
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM episodes
               WHERE LOWER(task_goal) LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (f"%{words[0]}%", limit)
        ).fetchall()
        conn.close()
        return [self._row_to_episode(r) for r in rows if r["episode_id"] != task_goal]

    def stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        by_outcome = dict(conn.execute(
            "SELECT outcome, COUNT(*) FROM episodes GROUP BY outcome"
        ).fetchall())
        avg_turns = conn.execute("SELECT AVG(turns) FROM episodes").fetchone()[0] or 0
        avg_tokens = conn.execute("SELECT AVG(tokens_used) FROM episodes").fetchone()[0] or 0
        conn.close()
        return {
            "total_episodes": total,
            "by_outcome": by_outcome,
            "avg_turns": round(avg_turns, 1),
            "avg_tokens": round(avg_tokens, 0)
        }

    def _row_to_episode(self, row) -> EpisodicEpisode:
        return EpisodicEpisode(
            episode_id=row["episode_id"],
            task_goal=row["task_goal"],
            task_category=row["task_category"],
            actions=json.loads(row["actions_json"] or "[]"),
            observations=json.loads(row["observations_json"] or "[]"),
            outcome=row["outcome"],
            lessons=json.loads(row["lessons_json"] or "[]"),
            turns=row["turns"],
            tokens_used=row["tokens_used"],
            duration_seconds=row["duration_seconds"],
            created_at=row["created_at"]
        )