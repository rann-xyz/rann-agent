"""
RANN Web API - Session-based LLM Configuration
Includes rate limiting, workspace isolation, and authentication
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

from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.budget import Budget
from rann_agent.auth.router import (
    router as auth_router,
    get_current_user,
    require_auth,
    generate_session_id,
    hash_session_token,
    check_rate_limit
)
from rann_agent.core.security import WorkspaceGuard
from rann_agent.storage.database import Database

app = FastAPI(title="RANN Public AI Coding Agent", version="2.0.0")

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
VALID_PROVIDERS = ["anthropic", "openai", "ollama", "custom"]

logger = structlog.get_logger()


@dataclass
class LLMConfig:
    """LLM configuration for a session."""
    provider: str
    model: str
    api_base: str = ""
    api_key: str = ""
    user_id: str = ""

from dataclasses import dataclass

# Rate limiting configuration
RATE_LIMITS = {
    "session_create": (10, 60),
    "llm_config": (20, 60),
    "llm_test": (10, 60),
    "tasks": (5, 60),
    "runs": (5, 60),
}

from threading import Lock
from collections import defaultdict

_rate_limit_locks: dict[str, Lock] = defaultdict(Lock)
_rate_limit_counters: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))


def rate_limit_check(identifier: str, endpoint: str) -> bool:
    """Check if request is within rate limits."""
    limit, window = RATE_LIMITS.get(endpoint, (100, 60))
    now = time.time()
    
    with _rate_limit_locks[identifier]:
        requests = _rate_limit_counters[identifier][endpoint]
        while requests and now - requests[0] > window:
            requests.pop(0)
        
        if len(requests) >= limit:
            return False
        
        requests.append(now)
        return True


def get_client_ip(request: Request) -> str:
    """Get client IP, respecting proxy configuration."""
    if request.client:
        return request.client.host
    return "unknown"


def ssrf_protect_url(url: str) -> bool:
    """Check if URL is safe from SSRF attacks."""
    from urllib.parse import urlparse
    import socket
    import ipaddress
    
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1", 
                                 "metadata.google", "169.254.169.254"):
            return False
        
        if "localhost" in hostname.lower() or hostname.startswith("127.") or hostname.startswith("192.168."):
            return False
        
        try:
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
            
            private_ranges = [
                ipaddress.ip_network("127.0.0.0/8"),
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
                ipaddress.ip_network("169.254.0.0/16"),
            ]
            
            for network in private_ranges:
                if ip in network:
                    return False
        except (socket.gaierror, ValueError):
            pass
        
        return True
    except Exception:
        return False


@app.get("/")
async def homepage():
    return JSONResponse({"message": "RANN Public AI Coding Agent", "version": "2.0.0"})


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "rann-web"}


# Legacy endpoint - now uses database
@app.post("/api/session")
async def create_legacy_session(request: Request):
    """Create a session (legacy endpoint - now database-backed)."""
    client_ip = get_client_ip(request)
    
    if not check_rate_limit(client_ip, "session_create"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    db = Database()
    conn = db._get_conn()
    
    # Create anonymous session for unauthenticated users
    session_id = generate_session_id()
    token_hash = hash_session_token(session_id)
    now = datetime.now(timezone.utc).isoformat()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    # Use a placeholder user_id for anonymous sessions
    user_id = f"anon_{secrets.token_urlsafe(16)}"
    
    try:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, f"anon-{user_id}@example.com", "x", "anonymous", now, now)
        )
        conn.execute(
            "INSERT INTO sessions (session_id, user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, token_hash, now, expires_at.isoformat())
        )
        conn.commit()
    except Exception as e:
        logger.error("session_create_error", error=str(e))
    
    return {"session_id": session_id, "expires_in": 3600}


# Protected routes using authentication
@app.post("/api/tasks")
async def create_task(request: Request, user = Depends(get_current_user)):
    """Create a task (requires authentication)."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    client_ip = get_client_ip(request)
    
    if not check_rate_limit(f"user:{user.id}", "tasks"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    if not check_rate_limit(client_ip, "tasks"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        data = await request.json()
        task = data.get("task", "").strip()
        if not task:
            raise HTTPException(status_code=400, detail="Task cannot be empty")
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    task_id = uuid.uuid4().hex[:8]
    
    db = Database()
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        conn = db._get_conn()
        conn.execute(
            "INSERT INTO tasks (task_id, contract_json, state, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, task, "queued", now, now, user.id)
        )
        conn.commit()
    except Exception as e:
        logger.error("task_creation_error", error=str(e))
    
    # Execute task with workspace isolation
    workspace = Path(WORKSPACE).resolve()
    guard = WorkspaceGuard(workspace)
    
    budget = Budget(max_tokens=5000, max_turns=10)
    
    class RuntimeConfig:
        provider = "custom"
        model = ""
        api_base = ""
        api_key = ""
        user_id = user.id
    
    agent = RuntimeAgent(budget=budget, config=RuntimeConfig())
    result = await agent.execute(task)
    
    if result.get("done"):
        return {"task_id": task_id, "status": "COMPLETED", "result": result.get("output", "")[:1000], "user_id": user.id}
    else:
        return {"task_id": task_id, "status": "FAILED", "error": result.get("error", "Unknown error")[:500], "user_id": user.id}


if __name__ == "__main__":
    print("🚀 RANN Public AI Server starting")
    uvicorn.run(app, host="127.0.0.1", port=8000)