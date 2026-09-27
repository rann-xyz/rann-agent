"""
RANN Agent Web API

FastAPI application with WebSocket terminal and REST APIs for projects, files, terminals, agents.

Architecture:
Browser → WebSocket → FastAPI → Auth → Project Auth → Sandbox → Docker
       → REST API → FastAPI → Auth → Project → Files/Sessions/Agents
"""

from datetime import datetime, timezone

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rann_agent.auth.router import router as auth_router
from rann_agent.api.projects import router as projects_router
from rann_agent.api.files import router as files_router
from rann_agent.api.terminal_sessions import router as terminal_sessions_router
from rann_agent.api.agent_sessions import router as agent_sessions_router
from rann_agent.storage.database import Database
from rann_agent.web.websocket_terminal import router as websocket_router

logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="RANN Agent API",
    description="Autonomous AI engineering platform",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(files_router)
app.include_router(terminal_sessions_router)
app.include_router(agent_sessions_router)
app.include_router(websocket_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    db = Database()
    logger.info("api_started", db_path=str(db.db_path))


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "rann-agent"}


@app.get("/health")
async def health():
    """Health check with detailed status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "rann-agent",
    }