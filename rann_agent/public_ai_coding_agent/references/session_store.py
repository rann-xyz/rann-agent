"""
Session store with workspace isolation for public AI coding agent.
"""
import os
import time
import secrets
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set, Any

@dataclass
class SessionSecurity:
    """Security wrapper for session operations"""
    session_id: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

class WorkspaceIsolator:
    """
    Ensures session operations cannot escape their workspace:
    - Path traversal protection (../)
    - Absolute path prevention
    - Symlink escape prevention
    - Cross-session access prevention
    """
    _session_workspaces: dict[str, Path] = {}
    
    @classmethod
    def create_session_workspace(cls, session_id: str, base_workspace: str = "/workspace") -> Path:
        hash_suffix = hashlib.sha256(session_id.encode()).hexdigest()[:8]
        session_workspace = Path(base_workspace) / ".workspace" / hash_suffix
        session_workspace.mkdir(parents=True, exist_ok=True)
        cls._session_workspaces[session_id] = session_workspace
        return session_workspace
    
    @classmethod
    def validate_path(cls, session_id: str, path: str) -> Path:
        """Validate path stays within session workspace"""
        if session_id not in cls._session_workspaces:
            raise ValueError("Invalid session")
        
        session_workspace = cls._session_workspaces[session_id]
        resolved_path = (session_workspace / path).resolve()
        
        try:
            resolved_path.relative_to(session_workspace)
        except ValueError:
            raise ValueError("Path traversal detected")
        
        if not str(resolved_path).startswith(str(session_workspace)):
            raise ValueError("Path escape attempt detected")
        
        return resolved_path

@dataclass
class Session:
    session_id: str
    llm_config: Optional[dict[str, Any]] = None
    security: Optional[SessionSecurity] = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)
    task_ids: Set[str] = field(default_factory=set)
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def refresh(self):
        self.expires_at = time.time() + 3600

class SessionStore:
    """Thread-safe session store with isolation"""
    
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = __import__('threading').Lock()
    
    def create_session(self) -> str:
        session_id = secrets.token_urlsafe(32)
        security = SessionSecurity(session_id)
        workspace = WorkspaceIsolator.create_session_workspace(session_id)
        
        session = Session(
            session_id=session_id,
            security=security,
            created_at=time.time(),
            expires_at=time.time() + 3600,
            task_ids=set()
        )
        
        with self._lock:
            self._sessions[session_id] = session
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_expired():
                del self._sessions[session_id]
                return None
            return session
    
    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                if session_id in WorkspaceIsolator._session_workspaces:
                    del WorkspaceIsolator._session_workspaces[session_id]
                return True
        return False
    
    def add_task(self, session_id: str, task_id: str):
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].task_ids.add(task_id)

session_store = SessionStore()