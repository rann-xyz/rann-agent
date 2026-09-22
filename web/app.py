"""
RANN Web API - Session-based LLM Configuration
Includes rate limiting, workspace isolation, and authentication

SECURITY NOTICE:
- This API ONLY submits execution jobs to a backend
- Direct code execution in the API process is PROHIBITED
- ContainerExecutionBackend required for production
- LocalExecutionBackend is DEVELOPMENT_ONLY
"""

import asyncio
import os
import sys
import time
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import structlog
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rann_agent.auth.router import (
    router as auth_router,
    get_current_user,
    require_auth,
    generate_session_id,
    hash_session_token,
    check_rate_limit,
)
from rann_agent.core.security import WorkspaceGuard
from rann_agent.storage.database import Database
from rann_agent.execution import (
    ExecutionJob,
    ExecutionStatus,
    ExecutionPolicy,
    ExecutionBackend,
    LocalExecutionBackend,
    ContainerExecutionBackend,
)

app = FastAPI(
    title="RANN Public AI Coding Agent",
    version="2.0.0",
    docs_url="/docs" if os.environ.get("RANN_ENABLE_DOCS") == "true" else None,
)

# Include authentication router
app.include_router(auth_router)

# CORS - specific Vercel domain only
ALLOWED_ORIGINS = [
    "https://rann-agent-mlp3p2jj6-rann2.vercel.app",
    "http://localhost:3000",
    "http://localhost:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE = os.environ.get("WORKSPACE", "/workspace")
VALID_PROVIDERS = ["anthropic", "openai", "custom"]
EXECUTION_BACKEND = os.environ.get("RANN_EXECUTION_BACKEND", "local")  # or "container"

logger = structlog.get_logger()


# Get execution backend - FAIL CLOSED if not configured
def get_execution_backend() -> ExecutionBackend:
    """Get the configured execution backend."""
    if EXECUTION_BACKEND == "container":
        backend = ContainerExecutionBackend()
        if not backend.is_available():
            raise RuntimeError(
                "ContainerExecutionBackend requested but runtime unavailable. "
                "Set RANN_EXECUTION_BACKEND=local for development only."
            )
        return backend
    else:
        # Local backend for development ONLY
        logger.warning(
            "using_local_execution_backend",
            message="LocalExecutionBackend is DEVELOPMENT ONLY. "
            "Do not use for public-facing deployment.",
        )
        return LocalExecutionBackend()


# Initialize execution backend
execution_backend = get_execution_backend()

# Rest of the original file content...
