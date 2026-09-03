"""
SQLite-based persistent storage for RANN Agent.
As required by MASTER PROMPT Section 22.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import structlog

logger = structlog.get_logger()

DB_PATH = Path.home() / ".rann-agent" / "rann.db"


def get_db_path() -> Path:
    db_dir = Path.home() / ".rann-agent"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "rann.db"


class Database:
    """SQLite database with migrations and transactions."""

    _instance: Optional["Database"] = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.db_path = get_db_path()
        self._ensure_schema()
        logger.info("database_initialized", path=str(self.db_path))

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create all tables if they don't exist."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    contract_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    result TEXT,
                    verification_level INTEGER DEFAULT 0,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS state_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    reason TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_json TEXT,
                    duration_ms REAL,
                    success INTEGER,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    run_id TEXT,
                    claim TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    validated INTEGER DEFAULT 0,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    run_id TEXT,
                    project_id TEXT,
                    task_category TEXT,
                    context_summary TEXT,
                    retrieved_memory_ids TEXT,
                    selected_strategy TEXT,
                    actions TEXT,
                    tool_calls INTEGER,
                    observations TEXT,
                    failures TEXT,
                    recovery_attempts INTEGER,
                    final_result TEXT,
                    verification_result TEXT,
                    success INTEGER,
                    reward REAL,
                    cost REAL,
                    latency_ms REAL,
                    lessons TEXT,
                    skill_candidates TEXT,
                    provenance TEXT,
                    confidence REAL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    provenance TEXT,
                    scope TEXT,
                    confidence REAL DEFAULT 0.5,
                    evidence TEXT,
                    validation_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    usage_count INTEGER DEFAULT 0,
                    importance REAL DEFAULT 0.5,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_verified TEXT
                );

                CREATE TABLE IF NOT EXISTS lessons (
                    lesson_id TEXT PRIMARY KEY,
                    category TEXT,
                    content TEXT NOT NULL,
                    evidence TEXT,
                    confidence REAL DEFAULT 0.0,
                    validated INTEGER DEFAULT 0,
                    sample_size INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_used TEXT
                );

                CREATE TABLE IF NOT EXISTS skills (
                    skill_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    version TEXT,
                    category TEXT,
                    triggers TEXT,
                    procedure TEXT,
                    tools TEXT,
                    permissions TEXT,
                    expected_outcome TEXT,
                    validation_evidence TEXT,
                    success_rate REAL DEFAULT 0.0,
                    failure_rate REAL DEFAULT 0.0,
                    provenance TEXT,
                    status TEXT DEFAULT 'candidate',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS benchmarks (
                    benchmark_id TEXT PRIMARY KEY,
                    task_category TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    baseline_value REAL,
                    candidate_value REAL,
                    result TEXT,
                    artifacts TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor TEXT,
                    run_id TEXT,
                    task_id TEXT,
                    operation TEXT NOT NULL,
                    arguments_json TEXT,
                    policy_result TEXT,
                    result TEXT,
                    timestamp TEXT NOT NULL,
                    affected_resources TEXT
                );

                CREATE TABLE IF NOT EXISTS operations (
                    operation_id TEXT PRIMARY KEY,
                    result_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    approval_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    requested_by TEXT,
                    timestamp TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    rejection_reason TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);
                CREATE INDEX IF NOT EXISTS idx_transitions_run ON state_transitions(run_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id);
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_lessons_category ON lessons(category);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
            """)
            logger.info("schema_ensured", path=str(self.db_path))

    # ---- Tasks ----
    def save_task(self, task_id: str, contract_json: str, state: str) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tasks (task_id, contract_json, state, created_at, updated_at)
                   VALUES (?, ?, ?, COALESCE((SELECT created_at FROM tasks WHERE task_id = ?), ?), ?)""",
                (task_id, contract_json, state, task_id, now, now)
            )

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Runs ----
    def save_run(
        self,
        run_id: str,
        task_id: str,
        start_time: str,
        end_time: Optional[str] = None,
        result: Optional[str] = None,
        verification_level: int = 0,
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO runs (run_id, task_id, start_time, end_time, result, verification_level)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, task_id, start_time, end_time, result, verification_level)
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            return dict(row) if row else None

    def get_incomplete_runs(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE end_time IS NULL ORDER BY start_time DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- State Transitions ----
    def record_transition(
        self,
        run_id: str,
        from_state: Optional[str],
        to_state: str,
        reason: Optional[str] = None,
    ) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO state_transitions (run_id, from_state, to_state, timestamp, reason) VALUES (?, ?, ?, ?, ?)",
                (run_id, from_state, to_state, now, reason)
            )

    def get_transitions(self, run_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM state_transitions WHERE run_id = ? ORDER BY timestamp ASC",
                (run_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Tool Calls ----
    def record_tool_call(
        self,
        run_id: str,
        tool_name: str,
        arguments_json: str,
        result_json: Optional[str] = None,
        duration_ms: Optional[float] = None,
        success: Optional[bool] = None,
    ) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO tool_calls (run_id, tool_name, arguments_json, result_json, duration_ms, success)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, tool_name, arguments_json, result_json, duration_ms, int(success) if success is not None else None)
            )
            return cursor.lastrowid or 0

    def get_tool_calls(self, run_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tool_calls WHERE run_id = ? ORDER BY id ASC", (run_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Evidence ----
    def save_evidence(
        self,
        evidence_id: str,
        claim: str,
        evidence_type: str,
        source: str,
        data_json: str,
        run_id: Optional[str] = None,
        validated: bool = False,
    ) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO evidence (id, run_id, claim, evidence_type, source, data_json, timestamp, validated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (evidence_id, run_id, claim, evidence_type, source, data_json, now, int(validated))
            )

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
            return dict(row) if row else None

    def search_evidence(self, claim_substring: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence WHERE claim LIKE ? ORDER BY timestamp DESC",
                (f"%{claim_substring}%",)
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- Episodes ----
    def save_episode(self, episode_id: str, data: Dict[str, Any]) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        fields = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        data["created_at"] = now
        conn = self._get_conn()
        conn.execute(
            f"INSERT OR REPLACE INTO episodes (episode_id, {fields}) VALUES (?, {placeholders})",
            [episode_id] + list(data.values())
        )
        conn.commit()

    # ---- Memories ----
    def save_memory(self, memory_id: str, data: Dict[str, Any]) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        data["updated_at"] = now
        if "created_at" not in data:
            data["created_at"] = now
        fields = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        conn = self._get_conn()
        conn.execute(
            f"INSERT OR REPLACE INTO memories (memory_id, {fields}) VALUES (?, {placeholders})",
            [memory_id] + list(data.values())
        )
        conn.commit()

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM memories WHERE memory_id = ?", (memory_id,)).fetchone()
            return dict(row) if row else None

    def search_memories(self, content_substring: str, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE content LIKE ? AND memory_type = ? ORDER BY updated_at DESC",
                    (f"%{content_substring}%", memory_type)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE content LIKE ? ORDER BY updated_at DESC",
                    (f"%{content_substring}%",)
                ).fetchall()
            return [dict(r) for r in rows]

    # ---- Lessons ----
    def save_lesson(self, lesson_id: str, data: Dict[str, Any]) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        data["created_at"] = now
        fields = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        conn = self._get_conn()
        conn.execute(
            f"INSERT OR REPLACE INTO lessons (lesson_id, {fields}) VALUES (?, {placeholders})",
            [lesson_id] + list(data.values())
        )
        conn.commit()

    def get_lessons(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM lessons WHERE category = ? AND validated = 1 ORDER BY confidence DESC",
                    (category,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM lessons WHERE validated = 1 ORDER BY confidence DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    # ---- Audit Log ----
    def record_audit(
        self,
        operation: str,
        actor: Optional[str] = None,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        arguments_json: Optional[str] = None,
        policy_result: Optional[str] = None,
        result: Optional[str] = None,
        affected_resources: Optional[str] = None,
    ) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO audit_log (actor, run_id, task_id, operation, arguments_json, policy_result, result, timestamp, affected_resources)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (actor, run_id, task_id, operation, arguments_json, policy_result, result, now, affected_resources)
            )

    # ---- Operations (idempotency) ----
    def is_duplicate_operation(self, operation_id: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT operation_id FROM operations WHERE operation_id = ?",
                (operation_id,)
            ).fetchone()
            return row is not None

    def record_operation(self, operation_id: str, result_json: Optional[str] = None) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO operations (operation_id, result_json, created_at) VALUES (?, ?, ?)",
                (operation_id, result_json, now)
            )

    def clear_old_operations(self, older_than_hours: int = 24) -> int:
        import datetime
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=older_than_hours)
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM operations WHERE created_at < ?",
                (cutoff.isoformat(),)
            )
            conn.commit()
            return cursor.rowcount

    # ---- Approvals ----
    def save_approval_request(self, request_id: str, data: Dict[str, Any]) -> None:
        with self._get_conn() as conn:
            fields = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            conn.execute(
                f"INSERT OR REPLACE INTO approval_requests (request_id, {fields}) VALUES (?, {placeholders})",
                [request_id] + list(data.values())
            )

    def get_approval_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM approval_requests WHERE request_id = ?", (request_id,)).fetchone()
            return dict(row) if row else None

    def list_pending_approvals(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM approval_requests WHERE status = 'pending' ORDER BY timestamp DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_approval_status(
        self,
        request_id: str,
        status: str,
        reviewed_by: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> None:
        import datetime
        now = datetime.datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE approval_requests SET status = ?, reviewed_by = ?, reviewed_at = ?, rejection_reason = ?
                   WHERE request_id = ?""",
                (status, reviewed_by, now, rejection_reason, request_id)
            )

    def close(self) -> None:
        """Close the singleton instance."""
        Database._instance = None