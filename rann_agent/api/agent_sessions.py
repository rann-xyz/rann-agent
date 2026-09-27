"""
Agent Session API Router

Provides:
- Create agent sessions
- List agent sessions
- Get agent session details
- Close agent sessions
- WebSocket for agent streaming
"""

import asyncio
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from rann_agent.auth.router import AuthUser, get_current_user
from rann_agent.core.config import Config
from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.security import WorkspaceGuard
from rann_agent.storage.database import Database
from rann_agent.tools.registry import ToolRegistry

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["agent"])

# In-memory store for agent runs (replace with Redis/DB for production)
_agent_runs: dict[str, dict] = {}
_agent_websockets: dict[str, list[WebSocket]] = {}

# Rate limiting for agent requests
AGENT_MAX_MESSAGES_PER_MINUTE = 10
AGENT_MAX_RUNS_PER_HOUR = 10


class AgentSession:
    """Represents an agent session."""

    def __init__(self, id: str, user_id: str, project_id: str, config: dict):
        self.id = id
        self.user_id = user_id
        self.project_id = project_id
        self.status = "idle"
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.config = config
        self.workspace_path = f"/workspace/{project_id}"


class AgentRun:
    """Represents a single agent run/task."""

    def __init__(self, id: str, session_id: str, message: str):
        self.id = id
        self.session_id = session_id
        self.message = message
        self.status = "created"
        self.created_at = datetime.now(timezone.utc)
        self.finished_at: datetime | None = None
        self.steps: list = []
        self.output: str = ""


class AgentSessionManager:
    """Manages agent sessions and runs."""

    def __init__(self):
        self._sessions: dict[str, AgentSession] = {}
        self._runs: dict[str, AgentRun] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def create_session(self, user_id: str, project_id: str) -> AgentSession:
        """Create a new agent session."""
        session_id = f"agent_{secrets.token_urlsafe(12)}"

        session = AgentSession(
            id=session_id,
            user_id=user_id,
            project_id=project_id,
            config={"workspace_path": f"/workspace/{project_id}"},
        )

        self._sessions[session_id] = session
        return session

    async def get_session(self, session_id: str) -> AgentSession | None:
        """Get session by ID."""
        return self._sessions.get(session_id)

    async def create_run(
        self, session_id: str, message: str, user_id: str, project_id: str
    ) -> AgentRun:
        """Create a new agent run within a session."""
        lock = self._get_lock(session_id)

        async with lock:
            session = self._sessions.get(session_id)
            if not session:
                raise ValueError("Session not found")

            if session.user_id != user_id:
                raise ValueError("Unauthorized")

            if session.project_id != project_id:
                raise ValueError("Unauthorized")

            # Check for active run
            for run in self._runs.values():
                if run.session_id == session_id and run.status in ["running", "waiting"]:
                    raise ValueError("Agent run already active")

            run_id = f"run_{secrets.token_urlsafe(12)}"
            run = AgentRun(id=run_id, session_id=session_id, message=message)

            self._runs[run_id] = run
            session.status = "running"
            session.last_activity = datetime.now(timezone.utc)

            return run


# Global manager
agent_manager = AgentSessionManager()


@router.post("/projects/{project_id}/agent/sessions")
async def create_agent_session(
    project_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Create a new agent session."""
    # Verify project ownership
    db = Database()
    project = (
        db._get_conn()
        .execute("SELECT id, owner_id FROM projects WHERE id = ?", (project_id,))
        .fetchone()
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    session = await agent_manager.create_session(user_id=user.id, project_id=project_id)

    return {
        "id": session.id,
        "project_id": session.project_id,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "config": {
            "workspace_path": session.config.get("workspace_path"),
        },
    }


@router.get("/projects/{project_id}/agent/sessions")
async def list_agent_sessions(
    project_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """List agent sessions for a project."""
    # Verify project ownership
    db = Database()
    project = (
        db._get_conn()
        .execute("SELECT id, owner_id FROM projects WHERE id = ?", (project_id,))
        .fetchone()
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get sessions for this project
    sessions = [s for s in agent_manager._sessions.values() if s.project_id == project_id]

    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "project_id": s.project_id,
            "status": s.status,
            "created_at": s.created_at.isoformat(),
            "last_activity": s.last_activity.isoformat(),
        }
        for s in sessions
    ]


@router.get("/projects/{project_id}/agent/sessions/{session_id}")
async def get_agent_session(
    project_id: str,
    session_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Get agent session details."""
    session = await agent_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.project_id != project_id:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get runs for this session
    runs = [r for r in agent_manager._runs.values() if r.session_id == session_id]

    return {
        "id": session.id,
        "user_id": session.user_id,
        "project_id": session.project_id,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat(),
        "runs": [
            {
                "id": r.id,
                "message": r.message,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "output": r.output[:500] if r.output else None,
            }
            for r in runs
        ],
    }


@router.delete("/projects/{project_id}/agent/sessions/{session_id}")
async def close_agent_session(
    project_id: str,
    session_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Close an agent session."""
    # Verify project ownership
    db = Database()
    project = (
        db._get_conn()
        .execute("SELECT owner_id FROM projects WHERE id = ?", (project_id,))
        .fetchone()
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    session = await agent_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Close any active runs
    for run in agent_manager._runs.values():
        if run.session_id == session_id and run.status not in ["completed", "failed", "cancelled"]:
            run.status = "cancelled"
            run.finished_at = datetime.now(timezone.utc)

    # Remove session
    del agent_manager._sessions[session_id]

    return {"success": True, "message": "Session closed"}


# Agent WebSocket for streaming
@router.websocket("/ws/projects/{project_id}/agent/{session_id}")
async def agent_websocket(
    websocket: WebSocket,
    project_id: str,
    session_id: str,
):
    """WebSocket for agent streaming."""
    # Get session cookie
    session_id_cookie = websocket.cookies.get("session")
    if not session_id_cookie:
        await websocket.close()
        return

    # Verify session and ownership (simplified for demo)
    db = Database()
    user_row = (
        db._get_conn()
        .execute(
            """SELECT u.id, p.owner_id
           FROM sessions s
           JOIN users u ON s.user_id = u.id
           JOIN projects p ON p.id = ?
           WHERE s.session_id = ?""",
            (project_id, session_id_cookie),
        )
        .fetchone()
    )

    if not user_row:
        await websocket.close()
        return

    if user_row["owner_id"] != user_row["id"]:
        await websocket.close(code=1008)  # Policy violation
        return

    await websocket.accept()

    # Track WebSocket
    if session_id not in _agent_websockets:
        _agent_websockets[session_id] = []
    _agent_websockets[session_id].append(websocket)

    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "message":
                text = data.get("message", "")

                # Create run
                run = await agent_manager.create_run(
                    session_id=session_id,
                    message=text,
                    user_id=user_row["id"],
                    project_id=project_id,
                )

                # Send run started event
                await _send_to_websockets(
                    session_id, {"type": "run_started", "run_id": run.id, "message": text}
                )

                # Execute agent
                asyncio.create_task(_execute_agent_run(run, session_id, user_row["id"], project_id))

            elif msg_type == "cancel":
                run_id = data.get("run_id")
                if run_id and run_id in agent_manager._runs:
                    agent_manager._runs[run_id].status = "cancelled"
                    agent_manager._runs[run_id].finished_at = datetime.now(timezone.utc)
                    await _send_to_websockets(
                        session_id, {"type": "run_cancelled", "run_id": run_id}
                    )

    except WebSocketDisconnect:
        if session_id in _agent_websockets:
            _agent_websockets[session_id].remove(websocket)

    except Exception as e:
        logger.error("agent_websocket_error", error=str(e))
        await websocket.close()


async def _execute_agent_run(run: AgentRun, session_id: str, user_id: str, project_id: str):
    """Execute an agent run."""
    try:
        # Create RuntimeAgent with project context
        config = Config.load()

        # Create RuntimeAgent instance
        agent = RuntimeAgent(
            config=config,
            memory=True,
            verification_level=1,  # MODERATE
        )

        # Send thinking event
        await _send_to_websockets(
            session_id, {"type": "agent_state", "run_id": run.id, "status": "thinking"}
        )

        # Execute with streaming
        result = await agent.execute(run.message)

        # Send output
        if "output" in result:
            await _send_to_websockets(
                session_id, {"type": "agent_message", "run_id": run.id, "data": result["output"]}
            )

        # Mark completed
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.output = result.get("output", "")

        await _send_to_websockets(session_id, {"type": "run_completed", "run_id": run.id})

    except Exception as e:
        logger.error("agent_run_failed", run_id=run.id, error=str(e))

        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)

        await _send_to_websockets(
            session_id, {"type": "run_failed", "run_id": run.id, "error": str(e)}
        )


async def _send_to_websockets(session_id: str, message: dict):
    """Send message to all WebSockets for a session."""
    if session_id in _agent_websockets:
        dead_sockets = []
        for ws in _agent_websockets[session_id]:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead_sockets.append(ws)

        # Remove dead sockets
        for dead in dead_sockets:
            _agent_websockets[session_id].remove(dead)
