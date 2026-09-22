"""
SQLite-based persistent storage for RANN Agent.
Extended with user authentication, sessions, and run ownership.
"""

import sqlite3
from pathlib import Path
from typing import Any, Optional

import structlog
from typing_extensions import Self

logger = structlog.get_logger()

DB_PATH = Path.home() / ".rann-agent" / "rann.db"


def get_db_path() -> Path:
    db_dir = Path.home() / ".rann-agent"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "rann.db"


class Database:
    """SQLite database with migrations and transactions."""

    _instance: Optional["Database"] = None

    def __new__(cls) -> Self:
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
        """Create all tables if they don't exist, with migrations."""
        with self._get_conn() as conn:
            # Create tables if they don't exist
            conn.executescript("""
                -- Users table
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    disabled_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

                -- Sessions table (including csrf_token_hash)
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    ip_hash TEXT,
                    token_hash TEXT,
                    csrf_token_hash TEXT,
                    last_seen_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

                -- IP bindings table
                CREATE TABLE IF NOT EXISTS ip_bindings (
                    ip_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_ip_bindings_expires ON ip_bindings(expires_at);

                -- Tasks table with user_id
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    contract_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                -- Runs table with user_id
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    task_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    result TEXT,
                    verification_level INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
                CREATE INDEX IF NOT EXISTS idx_runs_user ON runs(user_id);
                CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);

                -- State transitions with user_id
                CREATE TABLE IF NOT EXISTS state_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    reason TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_transitions_run ON state_transitions(run_id);
                CREATE INDEX IF NOT EXISTS idx_transitions_user ON state_transitions(user_id);

                -- Tool calls with user_id
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_json TEXT,
                    duration_ms REAL,
                    success INTEGER,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_user ON tool_calls(user_id);

                -- Evidence with user_id
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    run_id TEXT,
                    user_id TEXT,
                    claim TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    validated INTEGER DEFAULT 0,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_user ON evidence(user_id);

                -- Episodes with user_id
                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    run_id TEXT,
                    user_id TEXT,
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
                    confidence REAL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                -- Memories with user_id
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
                    user_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_verified TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);

                -- Lessons table
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

                -- Skills table
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

                -- Benchmarks table
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

                -- Audit log with user_id
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor TEXT,
                    actor_type TEXT,
                    run_id TEXT,
                    user_id TEXT,
                    task_id TEXT,
                    session_id TEXT,
                    operation TEXT NOT NULL,
                    arguments_json TEXT,
                    policy_result TEXT,
                    result TEXT,
                    timestamp TEXT NOT NULL,
                    affected_resources TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
                CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);

                -- Operations table
                CREATE TABLE IF NOT EXISTS operations (
                    operation_id TEXT PRIMARY KEY,
                    result_json TEXT,
                    created_at TEXT NOT NULL
                );

                -- Approval requests table
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
            """)
            
            # Migration: Add csrf_token_hash column to sessions if missing
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN csrf_token_hash TEXT")
                logger.info("migration_added", table="sessions", column="csrf_token_hash")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Migration: Add last_seen_at column to sessions if missing
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN last_seen_at TEXT")
                logger.info("migration_added", table="sessions", column="last_seen_at")
            except sqlite3.OperationalError:
                pass  # Column already exists

            logger.info("schema_ensured", path=str(self.db_path))