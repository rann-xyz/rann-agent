"""
Durable job queue for RANN Agent.
As required by MASTER PROMPT Section 24.
"""

import sqlite3
import json
import uuid
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import structlog

logger = structlog.get_logger()


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    job_id: str
    task_id: str
    task_json: str
    worker_id: Optional[str]
    status: JobStatus
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    heartbeat_at: Optional[str]
    error: Optional[str]
    retry_count: int
    priority: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DurableQueue:
    """SQLite-backed durable job queue with heartbeat."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from pathlib import Path
            db_path = Path.home() / ".rann-agent" / "queue.db"
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
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_json TEXT NOT NULL,
                worker_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                heartbeat_at TEXT,
                error TEXT,
                retry_count INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 0,
                result_json TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_worker ON jobs(worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON jobs(priority DESC, created_at)")
        conn.commit()
        conn.close()

    def enqueue(self, task_contract, priority: int = 0) -> str:
        """Add a job to the queue. Returns job_id."""
        job_id = str(uuid.uuid4())
        task_json = json.dumps(task_contract.to_dict() if hasattr(task_contract, 'to_dict') else task_contract)
        now = datetime.utcnow().isoformat()

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO jobs (job_id, task_id, task_json, status, created_at, priority)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (job_id, job_id, task_json, now, priority)
        )
        conn.commit()
        conn.close()

        logger.info("job_enqueued", job_id=job_id, priority=priority)
        return job_id

    def dequeue(self, worker_id: str, timeout_seconds: int = 5) -> Optional[Job]:
        """Claim a pending job. Returns Job or None."""
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()

        # Find oldest pending job
        row = conn.execute(
            """SELECT * FROM jobs
               WHERE status = 'pending'
               ORDER BY priority DESC, created_at ASC
               LIMIT 1""",
        ).fetchone()

        if not row:
            conn.close()
            return None

        # Claim it
        conn.execute(
            """UPDATE jobs SET status='running', worker_id=?, started_at=?, heartbeat_at=?
               WHERE job_id=? AND status='pending'""",
            (worker_id, now, now, row["job_id"])
        )
        conn.commit()
        conn.close()

        job = Job(
            job_id=row["job_id"],
            task_id=row["task_id"],
            task_json=row["task_json"],
            worker_id=worker_id,
            status=JobStatus.RUNNING,
            created_at=row["created_at"],
            started_at=now,
            completed_at=None,
            heartbeat_at=now,
            error=None,
            retry_count=row["retry_count"],
            priority=row["priority"]
        )

        logger.info("job_dequeued", job_id=job.job_id, worker_id=worker_id)
        return job

    def heartbeat(self, job_id: str, worker_id: str) -> bool:
        """Update heartbeat timestamp. Returns True if job is still ours."""
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        n = conn.execute(
            "UPDATE jobs SET heartbeat_at=? WHERE job_id=? AND worker_id=? AND status='running'",
            (now, job_id, worker_id)
        ).rowcount
        conn.commit()
        conn.close()
        return n > 0

    def complete(self, job_id: str, worker_id: str, result: Optional[Dict] = None) -> bool:
        """Mark job as completed."""
        now = datetime.utcnow().isoformat()
        result_json = json.dumps(result) if result else None
        conn = self._get_conn()
        n = conn.execute(
            """UPDATE jobs SET status='completed', completed_at=?, result_json=?
               WHERE job_id=? AND worker_id=? AND status='running'""",
            (now, result_json, job_id, worker_id)
        ).rowcount
        conn.commit()
        conn.close()
        logger.info("job_completed", job_id=job_id)
        return n > 0

    def fail(self, job_id: str, worker_id: str, error: str, retry: bool = False) -> bool:
        """Mark job as failed. Optionally increment retry count."""
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()

        if retry:
            conn.execute(
                """UPDATE jobs SET status='pending', error=?, retry_count=retry_count+1, worker_id=NULL
                   WHERE job_id=? AND worker_id=? AND status='running'""",
                (error, job_id, worker_id)
            )
        else:
            conn.execute(
                """UPDATE jobs SET status='failed', error=?, completed_at=?
                   WHERE job_id=? AND worker_id=? AND status='running'""",
                (error, now, job_id, worker_id)
            )
        conn.commit()
        conn.close()
        logger.warning("job_failed", job_id=job_id, error=error, retry=retry)
        return True

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        n = conn.execute(
            "UPDATE jobs SET status='cancelled', completed_at=? WHERE job_id=? AND status IN ('pending','running')",
            (now, job_id)
        ).rowcount
        conn.commit()
        conn.close()
        return n > 0

    def get_status(self, job_id: str) -> Optional[Job]:
        """Get job status."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return Job(
            job_id=row["job_id"],
            task_id=row["task_id"],
            task_json=row["task_json"],
            worker_id=row["worker_id"],
            status=JobStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            heartbeat_at=row["heartbeat_at"],
            error=row["error"],
            retry_count=row["retry_count"],
            priority=row["priority"]
        )

    def list_pending(self, limit: int = 50) -> List[Job]:
        """List pending jobs."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status='pending' ORDER BY priority DESC, created_at LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [self._row_to_job(r) for r in rows]

    def list_running(self) -> List[Job]:
        """List running jobs."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status='running' ORDER BY started_at"
        ).fetchall()
        conn.close()
        return [self._row_to_job(r) for r in rows]

    def _row_to_job(self, row) -> Job:
        return Job(
            job_id=row["job_id"],
            task_id=row["task_id"],
            task_json=row["task_json"],
            worker_id=row["worker_id"],
            status=JobStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            heartbeat_at=row["heartbeat_at"],
            error=row["error"],
            retry_count=row["retry_count"],
            priority=row["priority"]
        )

    def cleanup_stale(self, stale_seconds: int = 300) -> int:
        """Reset stale running jobs back to pending. Returns count."""
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(seconds=stale_seconds)).isoformat()
        conn = self._get_conn()
        n = conn.execute(
            """UPDATE jobs SET status='pending', worker_id=NULL
               WHERE status='running' AND heartbeat_at < ?""",
            (cutoff,)
        ).rowcount
        conn.commit()
        conn.close()
        if n:
            logger.warning("stale_jobs_reset", count=n)
        return n