"""
DB Connection Pool for RANN Agent.

Provides thread-safe connection pooling for SQLite.
Falls back to single connection if pool unavailable.
"""

import contextlib
import queue
import sqlite3
import threading
from pathlib import Path

import structlog

logger = structlog.get_logger()

DB_PATH = Path.home() / ".rann-agent" / "rann.db"

# Default pool size - 5 connections
DEFAULT_POOL_SIZE = 5


def get_db_path() -> Path:
    db_dir = Path.home() / ".rann-agent"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "rann.db"


class ConnectionPool:
    """
    Thread-safe SQLite connection pool.

    Uses a queue of pre-created connections.
    Connections are checked for liveness before dispensing.
    """

    def __init__(self, db_path: Path | None = None, pool_size: int = DEFAULT_POOL_SIZE):
        self.db_path = db_path or get_db_path()
        self.pool_size = pool_size
        self._pool: queue.Queue[sqlite3.Connection | None] = queue.Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._init_lock = threading.Lock()
        self._initialized = False

    def _create_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Performance pragmas
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        return conn

    def _initialize(self):
        with self._init_lock:
            if self._initialized:
                return
            # Pre-create connections
            for _ in range(self.pool_size):
                try:
                    conn = self._create_conn()
                    self._pool.put_nowait(conn)
                except Exception as e:
                    logger.warning("pool_init_failed", error=str(e))
            self._initialized = True
            logger.info(
                "db_pool_initialized",
                pool_size=self.pool_size,
                db_path=str(self.db_path),
            )

    @contextlib.contextmanager
    def get_connection(self):
        """Get a connection from the pool. Auto-returns on exit."""
        self._initialize()
        conn = self._pool.get(timeout=30.0)
        try:
            # Verify connection is alive
            conn.execute("SELECT 1")
            yield conn
        except Exception:
            # Replace dead connection
            try:
                conn.close()
            except Exception:
                pass
            conn = self._create_conn()
        finally:
            self._pool.put_nowait(conn)

    def close_all(self):
        """Close all connections in the pool."""
        while True:
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except queue.Empty:
                break
        self._initialized = False
        logger.info("db_pool_closed")


# Global pool instance
_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ConnectionPool()
        return _pool


@contextlib.contextmanager
def get_db_connection():
    """Context manager: get a pooled DB connection."""
    pool = get_pool()
    with pool.get_connection() as conn:
        yield conn
