"""
Real PTY Terminal Implementation for RANN Agent

Hardened implementation with proper session lifecycle.

Architecture:
Browser → WebSocket → FastAPI → TerminalSessionManager → Docker SDK → Container PTY → Shell

CRITICAL: TerminalSession is independent from WebSocket connection.
"""

import asyncio
import json
import os
import signal
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

import docker
from docker import errors as docker_errors
from rann_agent.storage.database import Database

logger = structlog.get_logger(__name__)


class TerminalStatus(str, Enum):
    """Terminal session lifecycle states."""

    CREATED = "created"  # Resource allocated, no WebSocket
    ATTACHED = "attached"  # WebSocket connected and active
    DETACHED = "detached"  # WebSocket disconnected, PTY alive
    CLOSED = "closed"  # Session terminated
    FAILED = "failed"  # Error state


class TerminalMessage:
    """WebSocket message types."""

    INPUT = "input"
    OUTPUT = "output"
    EXIT = "exit"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    RESIZE = "resize"
    STATUS = "status"


# Configuration
MAX_MESSAGE_BYTES = int(os.environ.get("TERMINAL_MAX_MESSAGE_BYTES", "1048576"))
MAX_SESSIONS_PER_USER = int(os.environ.get("TERMINAL_MAX_SESSIONS_PER_USER", "5"))
MAX_SESSIONS_PER_PROJECT = int(os.environ.get("TERMINAL_MAX_SESSIONS_PER_PROJECT", "2"))
IDLE_TIMEOUT = int(os.environ.get("TERMINAL_IDLE_TIMEOUT", "3600"))
DETACHED_TIMEOUT = int(os.environ.get("TERMINAL_DETACHED_TIMEOUT", "300"))


@dataclass
class TerminalSession:
    """Active terminal session with proper lifecycle.

    IMPORTANT: This is SESSION STATE, not WebSocket state.
    WebSocket attaches/detaches from this session.
    """

    id: str
    user_id: str
    project_id: str
    container_id: str
    exec_id: str | None = None
    status: TerminalStatus = TerminalStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cols: int = 120
    rows: int = 32
    websocket_active: bool = False


class TerminalSessionManager:
    """Manages terminal sessions with proper limits and locking."""

    def __init__(self):
        self._sessions: dict[str, TerminalSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        """Get atomic lock for session operations."""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def create_session(
        self, user_id: str, project_id: str, container_id: str, cols: int = 120, rows: int = 32
    ) -> TerminalSession:
        """Create terminal session with per-user/project limits.

        Does NOT check websocket_active - that's for attach operations.
        """
        # Per-user limit
        user_sessions = [s for s in self._sessions.values() if s.user_id == user_id]
        if len(user_sessions) >= MAX_SESSIONS_PER_USER:
            raise ValueError("Maximum terminal sessions per user exceeded")

        # Per-project limit
        proj_sessions = [s for s in self._sessions.values() if s.project_id == project_id]
        if len(proj_sessions) >= MAX_SESSIONS_PER_PROJECT:
            raise ValueError("Maximum terminal sessions per project exceeded")

        session = TerminalSession(
            id=f"term_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            project_id=project_id,
            container_id=container_id,
            cols=cols,
            rows=rows,
            status=TerminalStatus.CREATED,
        )
        self._sessions[session.id] = session
        logger.info("terminal_session_created", session_id=session.id)
        return session

    async def find_session(self, session_id: str) -> TerminalSession | None:
        """Find existing session by ID (for reconnect)."""
        session = self._sessions.get(session_id)
        if session:
            # Check idle timeout only for detached sessions
            if session.status == TerminalStatus.DETACHED:
                idle = (datetime.now(timezone.utc) - session.last_activity).total_seconds()
                if idle > DETACHED_TIMEOUT:
                    await self.close_session(session_id)
                    return None
        return session

    async def close_session(self, session_id: str):
        """Properly close a session."""
        session = self._sessions.get(session_id)
        if session:
            session.status = TerminalStatus.CLOSED
            self._sessions.pop(session_id, None)
            self._locks.pop(session_id, None)

    async def attach_websocket(self, session_id: str, websocket: Any) -> TerminalSession:
        """Atomically attach WebSocket to session.

        Returns session if attach succeeds.
        Raises ValueError if already attached.
        """
        lock = self._get_lock(session_id)
        async with lock:
            session = self._sessions.get(session_id)
            if not session:
                raise ValueError("Session not found")

            if session.websocket_active:
                raise ValueError("Terminal already attached")

            if session.status == TerminalStatus.CLOSED:
                raise ValueError("Session closed")

            session.websocket_active = True
            session.status = TerminalStatus.ATTACHED
            session.last_activity = datetime.now(timezone.utc)
            return session

    async def detach_websocket(self, session_id: str):
        """Detach WebSocket from session (on disconnect)."""
        lock = self._get_lock(session_id)
        async with lock:
            session = self._sessions.get(session_id)
            if session:
                session.websocket_active = False
                session.status = TerminalStatus.DETACHED
                session.last_activity = datetime.now(timezone.utc)

    async def update_activity(self, session_id: str):
        """Update last activity timestamp."""
        if session_id in self._sessions:
            self._sessions[session_id].last_activity = datetime.now(timezone.utc)


# Global manager
terminal_manager = TerminalSessionManager()


class RealPTYTerminal:
    """PTY terminal with WebSocket independence."""

    def __init__(self, project_id: str, websocket: Any, user_id: str, container_id: str):
        self.project_id = project_id
        self.websocket = websocket
        self.user_id = user_id
        self.container_id = container_id
        self.session: TerminalSession | None = None
        self._running = False
        self._docker_client = None
        self._exec_id = None
        self._socket = None

    async def connect(self) -> bool:
        """Connect to terminal session."""
        return await self._start_pty()

    async def _start_pty(self) -> bool:
        """Start PTY shell in Docker container."""
        try:
            self._docker_client = docker.from_env()

            exec_resp = self._docker_client.api.exec_create(
                self.container_id,
                cmd="/bin/bash -i",
                stdin=True,
                stdout=True,
                stderr=True,
                tty=True,
                attach_stdin=True,
                attach_stdout=True,
                attach_stderr=True,
            )

            self._exec_id = exec_resp.get("Id")

            # Initial resize
            if self.session and self._docker_client and self._exec_id:
                self._docker_client.api.exec_resize(
                    self._exec_id, self.session.rows, self.session.cols
                )

            # Attach socket
            self._socket = self._docker_client.api.exec_attach(
                self._exec_id,
                detach_keys=False,
                stream=True,
                tty=True,
            )

            return True

        except Exception as e:
            self.session.status = TerminalStatus.FAILED
            await self._send_error("PTY_START_FAILED", str(e))
            return False

    async def _send_message(self, msg_type: str, data: Any | None = None) -> bool:
        """Send JSON message to WebSocket."""
        if not self.session or not self.websocket:
            return False

        if self.websocket.client_state != WebSocketState.CONNECTED:
            return False

        message = {"type": msg_type}
        if data is not None:
            if isinstance(data, str) and len(data.encode("utf-8")) > MAX_MESSAGE_BYTES:
                data = data[:MAX_MESSAGE_BYTES]
            message["data"] = data

        try:
            await self.websocket.send_text(json.dumps(message))
            return True
        except Exception:
            return False

    async def _send_error(self, code: str, message: str):
        """Send error message."""
        await self._send_message(TerminalMessage.ERROR, {"code": code, "message": message})

    async def handle_input(self, data: str):
        """Write input to PTY."""
        if not self._running or not self._socket:
            return

        try:
            sock = self._socket._sock
            if hasattr(sock, "send"):
                sock.send(data.encode("utf-8", errors="replace"))
        except Exception:
            pass

    async def handle_resize(self, cols: int, rows: int):
        """Resize PTY via Docker API."""
        if not self.session or not self._docker_client or not self._exec_id:
            return

        self.session.cols = cols
        self.session.rows = rows

        try:
            self._docker_client.api.exec_resize(self._exec_id, rows, cols)
            await self._send_message(TerminalMessage.STATUS, {"cols": cols, "rows": rows})
        except Exception:
            pass

    async def handle_ping(self):
        """Handle ping."""
        await self._send_message(TerminalMessage.PONG)

    async def stream_output(self):
        """Stream PTY output to WebSocket."""
        if not self._socket:
            return

        try:
            sock = self._socket._sock
            while self._running:
                try:
                    data = sock.recv(4096)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        await self._send_message(TerminalMessage.OUTPUT, text)
                    else:
                        break
                except BlockingIOError:
                    await asyncio.sleep(0.01)
                    continue
                except OSError:
                    break

            await self._send_message(TerminalMessage.EXIT, {"code": 0})

        except Exception:
            pass

    async def handle_messages(self):
        """Main message handler loop."""
        reader_task = asyncio.create_task(self.stream_output())

        try:
            async for msg in self.websocket:
                if not self._running:
                    break

                await terminal_manager.update_activity(self.session.id)

                try:
                    data = json.loads(msg)
                    mtype = data.get("type")

                    if mtype == TerminalMessage.INPUT:
                        await self.handle_input(data.get("data", ""))
                    elif mtype == TerminalMessage.RESIZE:
                        await self.handle_resize(data.get("cols", 120), data.get("rows", 32))
                    elif mtype == TerminalMessage.PING:
                        await self.handle_ping()

                except json.JSONDecodeError:
                    await self._send_error("INVALID_MESSAGE", "Invalid JSON")

        except WebSocketDisconnect:
            pass
        finally:
            self._running = False
            if reader_task:
                reader_task.cancel()
                try:
                    await reader_task
                except asyncio.CancelledError:
                    pass
            await self.cleanup()

    async def cleanup(self):
        """Clean up terminal resources."""
        self._running = False

        if self._docker_client and self._exec_id:
            try:
                self._docker_client.api.exec_kill(self._exec_id, signal.SIGTERM)
            except Exception:
                pass

        if self.session:
            # Don't remove session - let detach_websocket handle status
            # Only close if this was the last connection
            if not self.session.websocket_active:
                self.session.status = TerminalStatus.CLOSED
                await terminal_manager.remove_session(self.session.id)

        if self.websocket and self.websocket.client_state == WebSocketState.CONNECTED:
            try:
                await self.websocket.close()
            except Exception:
                pass


# Router
router = APIRouter(prefix="/ws", tags=["websocket"])


async def get_user_id(websocket: WebSocket) -> str | None:
    """Extract and validate user from session."""
    session_id = websocket.cookies.get("session")
    if not session_id:
        return None

    try:
        db = Database()
        row = (
            db._get_conn()
            .execute(
                """SELECT u.id, s.revoked_at, s.expires_at
               FROM sessions s
               JOIN users u ON s.user_id = u.id
               WHERE s.session_id = ?""",
                (session_id,),
            )
            .fetchone()
        )

        if not row or row["revoked_at"]:
            return None

        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return None

        return row["id"]

    except Exception as e:
        logger.error("auth_failed", error=str(e))
        return None


@router.websocket("/projects/{project_id}/terminal")
async def terminal_endpoint(
    websocket: WebSocket, project_id: str, user_id: str | None = Depends(get_user_id)
):
    """
    Real PTY WebSocket terminal.

    URL: ws://api.rann.xyz/ws/projects/{project_id}/terminal

    Protocol:
    - Input: {"type": "input", "data": "..."}
    - Resize: {"type": "resize", "cols": 120, "rows": 40}
    - Ping: {"type": "ping"}
    - Output: {"type": "output", "data": "..."}
    - Error: {"type": "error", "code": "...", "message": "..."}
    - Exit: {"type": "exit", "code": 0}
    """
    await websocket.accept()

    if not user_id:
        return await websocket.close()

    # Verify project ownership
    try:
        db = Database()
        project = (
            db._get_conn()
            .execute("SELECT owner_id, sandbox_id FROM projects WHERE id = ?", (project_id,))
            .fetchone()
        )

        if not project or project["owner_id"] != user_id:
            return await websocket.close()

        container_id = project.get("sandbox_id") or project_id

    except Exception:
        return await websocket.close()

    terminal = RealPTYTerminal(project_id, websocket, user_id, container_id)

    try:
        if await terminal.connect():
            await terminal.handle_messages()
    except Exception as e:
        logger.error("terminal_error", error=str(e))
    finally:
        await terminal.cleanup()
