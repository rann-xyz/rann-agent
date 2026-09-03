"""
Concurrency control for RANN Agent.
As required by MASTER PROMPT Section 25.
"""

import fcntl
import os
import contextlib
from pathlib import Path
from typing import Optional, Callable, Any
from enum import Enum
import structlog

logger = structlog.get_logger()


class LockType(Enum):
    WORKSPACE = "workspace"
    REPOSITORY = "repository"
    FILE = "file"
    DATABASE = "database"


class FileLock:
    """File-based lock using fcntl (Linux)."""

    def __init__(self, path: str, timeout: float = 30.0):
        self.path = Path(path)
        self.timeout = timeout
        self._fd: Optional[int] = None
        self._lock_file: Optional[int] = None

    def acquire(self, blocking: bool = True) -> bool:
        """Acquire the lock. Returns True if acquired."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR)
        try:
            if blocking:
                fcntl.flock(self._fd, fcntl.LOCK_EX)
                logger.debug("lock_acquired", path=str(self.path))
                return True
            else:
                try:
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logger.debug("lock_acquired", path=str(self.path))
                    return True
                except BlockingIOError:
                    return False
        except Exception as e:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
            raise

    def release(self) -> None:
        """Release the lock."""
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
            logger.debug("lock_released", path=str(self.path))

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


class WorkspaceLock:
    """Workspace-level lock — prevents concurrent modifications to same workspace."""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self.lock_dir = Path.home() / ".rann-agent" / "locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def _lock_path(self) -> Path:
        safe = self.workspace_root.as_posix().replace("/", "_").replace(".", "_")
        return self.lock_dir / f"workspace_{safe}.lock"

    @contextlib.contextmanager
    def hold(self, timeout: float = 60.0):
        """Context manager to hold workspace lock."""
        lock = FileLock(str(self._lock_path()), timeout=timeout)
        if not lock.acquire():
            raise RuntimeError(f"Could not acquire workspace lock: {self.workspace_root}")
        try:
            yield
        finally:
            lock.release()

    def is_locked(self) -> bool:
        lock = FileLock(str(self._lock_path()), timeout=0.1)
        return not lock.acquire(blocking=False)


class LockManager:
    """Central lock manager for all RANN Agent locks."""

    def __init__(self, workspace_root: str):
        self.workspace = WorkspaceLock(workspace_root)
        self._repo_locks: dict[str, FileLock] = {}
        self._file_locks: dict[str, FileLock] = {}
        self.lock_dir = Path.home() / ".rann-agent" / "locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def workspace_lock(self) -> contextlib.AbstractContextManager:
        """Get workspace lock context manager."""
        return self.workspace.hold()

    def repo_lock(self, repo_path: str) -> contextlib.AbstractContextManager:
        """Get repository-level lock."""
        safe = Path(repo_path).resolve().as_posix().replace("/", "_").replace(".", "_")
        lock_path = self.lock_dir / f"repo_{safe}.lock"
        lock = FileLock(str(lock_path))
        return _FileLockContext(lock)

    def file_lock(self, file_path: str) -> contextlib.AbstractContextManager:
        """Get file-level lock."""
        safe = Path(file_path).resolve().as_posix().replace("/", "_").replace(".", "_")
        lock_path = self.lock_dir / f"file_{safe}.lock"
        lock = FileLock(str(lock_path))
        return _FileLockContext(lock)


class _FileLockContext:
    """Context manager adapter for FileLock."""
    def __init__(self, lock: FileLock):
        self._lock = lock

    def __enter__(self):
        if not self._lock.acquire():
            raise RuntimeError(f"Could not acquire lock: {self._lock.path}")
        return self

    def __exit__(self, *args):
        self._lock.release()


def with_lock(lock_type: str = "workspace", path: str = None, workspace: str = None):
    """Decorator to hold a lock during a function call.

    Usage:
        @with_lock(lock_type="workspace", workspace="/path/to/workspace")
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            if lock_type == "workspace":
                if not workspace:
                    raise ValueError("workspace path required for workspace lock")
                manager = LockManager(workspace)
                with manager.workspace_lock():
                    return func(*args, **kwargs)
            elif lock_type == "file":
                if not path:
                    raise ValueError("file path required for file lock")
                manager = LockManager(workspace or os.getcwd())
                with manager.file_lock(path):
                    return func(*args, **kwargs)
            else:
                raise ValueError(f"Unknown lock type: {lock_type}")
        return wrapper
    return decorator