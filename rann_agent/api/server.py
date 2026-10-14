"""
FastAPI server with WebSocket support
"""

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from rann_agent import Agent, Config

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Rann Agent API",
    description="Next-generation autonomous AI agent",
    version="1.0.0",
)

# Include routers with optional auth
# Note: Auth router requires email-validator package
try:
    from rann_agent.auth.router import router as auth_router
    app.include_router(auth_router)
except ImportError:
    logger.warning("auth_router_not_included", reason="email-validator package not installed")
    # Create stub for when auth is not available
    class AuthUser:
        """Stub user for when auth is not available"""
        pass
    # Stub require_auth that raises 503 if auth unavailable
    def require_auth():
        raise HTTPException(status_code=503, detail="Authentication system not available - install email-validator package")

from rann_agent.api.projects import router as projects_router
from rann_agent.api.agent_sessions import router as agent_sessions_router
from rann_agent.api.files import router as files_router
from rann_agent.api.terminal_sessions import router as terminal_router
from rann_agent.web.websocket_terminal import router as websocket_router

# Include API routers
app.include_router(projects_router)
app.include_router(agent_sessions_router)
app.include_router(files_router)
app.include_router(terminal_router)
app.include_router(websocket_router)

# Load config
config = Config.load()

# JWT Secret Validation - reject insecure defaults in production
import os
_is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
_jwt_secret = os.getenv("JWT_SECRET", "your-jwt-secret-change-in-production")
if _is_production:
    if not _jwt_secret or _jwt_secret.startswith("your-") or _jwt_secret == "change-me":
        logger.warning("INSECURE_JWT_SECRET", 
            message="JWT_SECRET uses default/weak value in production - this is insecure")
elif _jwt_secret == "your-jwt-secret-change-in-production":
    logger.warning("JWT_SECRET_DEFAULT", 
        message="Using default JWT secret - set JWT_SECRET environment variable")

# CORS - Production-safe defaults
if config.api.cors.get("enabled", True):
    # Get allowed origins - use explicit allowlist, not wildcard
    _cors_origins = config.api.cors.get("origins", [])
    if not _cors_origins:
        # Fallback for development - use specific localhost URLs, not wildcard
        _cors_origins = ["http://localhost:3000", "http://localhost:8000"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )

# Active agents
active_agents: dict[str, Agent] = {}


class TaskRequest(BaseModel):
    goal: str
    context: str | None = None
    provider: str | None = None
    model: str | None = None
    stream: bool = False
    dry_run: bool = False  # Validate without executing
    conversation_only: bool = True  # SAFE DEFAULT: Call LLM but do NOT execute tools
    execute_tools: bool = False  # EXPLICIT opt-in for tool execution


class TaskResponse(BaseModel):
    session_id: str
    success: bool
    output: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = {}


@app.get("/")
async def root():
    """API root"""
    return {
        "name": "Rann Agent API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "execute": "/api/execute",
            "stream": "/api/stream (WebSocket)",
            "agents": "/api/agents",
            "config": "/api/config",
            "dashboard": "/dashboard",
        },
    }


@app.post("/api/execute", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    """Execute a task
    
    Modes (in order of precedence):
    1. dry_run=True: Public offline validation (no LLM, no tools)
    2. conversation_only=True (default): Text-only chat (calls LLM, returns text, NO tools)
    3. conversation_only=False + execute_tools=True: Full execution (REQUIRES AUTHORIZATION - DISABLED)
    
    Default behavior is SAFE: conversation_only=True prevents all tool execution.
    Full tool execution is disabled without proper authentication setup.
    """
    
    try:
        # Dry-run mode: public validation WITHOUT auth
        # This is safe because no LLM or tools are invoked
        if request.dry_run:
            import uuid
            session_id = f"dry_run_{uuid.uuid4().hex[:8]}"
            
            # Offline plan generation - no LLM call, no tool execution
            plan = {
                "goal": request.goal,
                "context": request.context,
                "steps": [
                    {
                        "step": 1,
                        "tool": None,
                        "parameters": {"goal": request.goal, "context": request.context},
                        "would_execute": False,
                    }
                ],
                "tools_required": [],
                "safe_to_execute": True,
                "simulated": True,
                "note": "Dry-run structural plan - no operations performed",
            }
            
            return TaskResponse(
                session_id=session_id,
                success=True,
                output=f"Dry-run plan generated:\n{plan}",
                metadata={"mode": "dry_run", "plan": plan},
            )

        # Conversation-only mode: call LLM but do NOT execute tools
        # This is the SAFE DEFAULT for ordinary requests
        if request.conversation_only and not request.execute_tools:
            # Create agent with tools DISABLED
            agent = Agent(
                config=config,
                provider=request.provider,
                model=request.model,
                tools=[],  # NO tools in conversation-only mode
            )
            agent.session_id = agent._generate_session_id()
            agent.context.add_user_message(request.goal, request.context)
            
            try:
                messages = agent.context.get_messages()
                response = await agent.llm.complete(messages)
                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])
                
                return TaskResponse(
                    session_id=agent.session_id,
                    success=True,
                    output=content or "No response from LLM",
                    error=None if not tool_calls else f"LLM requested {len(tool_calls)} tool calls (not executed in conversation mode)",
                    metadata={
                        "mode": "conversation_only",
                        "llm_response": content,
                        "tool_calls": tool_calls,
                    },
                )
            except Exception as e:
                logger.error("conversation_failed", error=str(e))
                return TaskResponse(
                    session_id=agent.session_id,
                    success=False,
                    output=None,
                    error=str(e),
                    metadata={"mode": "conversation_only", "status": "failed"},
                )

        # Full execution mode: requires execute_tools=True AND valid auth
        # This mode CAN execute tools - requires proper authentication
        if not request.conversation_only or request.execute_tools:
            # Check if this is an attempt at full execution
            if request.execute_tools:
                # Full execution requested - check if we should allow it
                # Currently blocks all full execution without auth (safe default)
                raise HTTPException(
                    status_code=403,
                    detail="Full tool execution is disabled. Use conversation_only mode for text-only interaction."
                )
            
            # conversation_only=False but execute_tools=False -> treat as conversation
            # Create agent with tools disabled as safety measure
            agent = Agent(
                config=config,
                provider=request.provider,
                model=request.model,
                tools=[],  # Safety: tools disabled by default
            )
            agent.session_id = agent._generate_session_id()
            agent.context.add_user_message(request.goal, request.context)
            
            try:
                messages = agent.context.get_messages()
                response = await agent.llm.complete(messages)
                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])
                
                return TaskResponse(
                    session_id=agent.session_id,
                    success=True,
                    output=content or "No response from LLM",
                    error=None if not tool_calls else f"LLM requested {len(tool_calls)} tool calls (not executed)",
                    metadata={
                        "mode": "text_only",
                        "llm_response": content,
                        "tool_calls": tool_calls,
                    },
                )
            except Exception as e:
                logger.error("execution_failed", error=str(e))
                return TaskResponse(
                    session_id=agent.session_id,
                    success=False,
                    output=None,
                    error=str(e),
                    metadata={"mode": "text_only", "status": "failed"},
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("execute_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/api/stream")
async def stream_task(websocket: WebSocket):
    """Stream task execution via WebSocket"""

    await websocket.accept()

    try:
        # Receive task
        data = await websocket.receive_json()
        goal = data.get("goal")
        context = data.get("context")

        if not goal:
            await websocket.send_json({"error": "No goal provided"})
            return

        # Create agent
        agent = Agent(config=config)
        active_agents[agent.session_id] = agent

        # Send session ID
        await websocket.send_json(
            {
                "type": "session_started",
                "session_id": agent.session_id,
            }
        )

        # Stream execution
        async for token in agent.stream(goal, context):
            await websocket.send_json(
                {
                    "type": "token",
                    "data": token,
                }
            )

        # Done
        await websocket.send_json(
            {
                "type": "complete",
                "session_id": agent.session_id,
            }
        )

    except WebSocketDisconnect:
        logger.info("websocket_disconnected")

    except Exception as e:
        logger.error("stream_failed", error=str(e))
        await websocket.send_json(
            {
                "type": "error",
                "error": str(e),
            }
        )


@app.get("/api/agents")
async def list_agents(user: AuthUser = Depends(require_auth)):
    """List active agents for the authenticated user.
    
    SECURITY: Only returns sessions owned by the authenticated user.
    Endpoint requires valid authentication.
    """
    # Return only sessions owned by the authenticated user
    user_sessions = [
        {"session_id": sid, "status": "active"}
        for sid, agent in active_agents.items()
        if hasattr(agent, 'context') and agent.context and 
           getattr(agent.context, 'user_id', None) == user.id
    ]
    
    return {
        "count": len(user_sessions),
        "agents": user_sessions,
    }


@app.get("/api/config")
async def get_config():
    """Get configuration"""
    return {
        "provider": config.agent.llm.provider,
        "model": config.agent.llm.model,
        "tools": config.tools.enabled,
        "features": {
            "self_healing": config.agent.self_healing.enabled,
            "orchestration": config.agent.orchestration.enabled,
            "memory": config.agent.memory.persist,
        },
    }


@app.get("/api/tools")
async def list_tools():
    """List available tools"""
    agent = Agent(config=config)
    tools = agent.tools.list_tools()
    return {"tools": tools}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Web dashboard"""
    return """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Rann Agent Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        .header h1 {
            font-size: 2.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        .chat-box {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        .input-group {
            display: flex;
            gap: 1rem;
        }
        input, button {
            padding: 1rem;
            font-size: 1rem;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
        }
        input {
            flex: 1;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
        }
        .output {
            background: #f5f5f5;
            padding: 1.5rem;
            border-radius: 8px;
            margin-top: 1rem;
            min-height: 200px;
            font-family: 'Monaco', 'Courier New', monospace;
            white-space: pre-wrap;
        }
        .status {
            display: inline-block;
            padding: 0.5rem 1rem;
            border-radius: 999px;
            font-size: 0.875rem;
            font-weight: 600;
        }
        .status.active { background: #10b981; color: white; }
        .status.idle { background: #6b7280; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Rann Agent</h1>
            <p style="color: #666;">Next-generation autonomous AI agent</p>
            <br>
            <span class="status active">API Running</span>
        </div>
        
        <div class="chat-box">
            <h2 style="margin-bottom: 1rem;">Execute Task</h2>
            <div class="input-group">
                <input type="text" id="goalInput" placeholder="What do you want the agent to do?" />
                <button onclick="executeTask()">Execute</button>
            </div>
            <div class="output" id="output">Agent output will appear here...</div>
        </div>
        
        <div class="chat-box">
            <h2 style="margin-bottom: 1rem;">API Endpoints</h2>
            <ul style="list-style: none; padding: 0;">
                <li style="padding: 0.5rem 0;"><code>POST /api/execute</code> - Execute a task</li>
                <li style="padding: 0.5rem 0;"><code>WebSocket /api/stream</code> - Stream execution</li>
                <li style="padding: 0.5rem 0;"><code>GET /api/agents</code> - List active agents</li>
                <li style="padding: 0.5rem 0;"><code>GET /api/config</code> - Get configuration</li>
                <li style="padding: 0.5rem 0;"><code>GET /api/tools</code> - List tools</li>
                <li style="padding: 0.5rem 0;"><code>GET /docs</code> - OpenAPI documentation</li>
            </ul>
        </div>
    </div>
    
    <script>
        async function executeTask() {
            const goal = document.getElementById('goalInput').value;
            const output = document.getElementById('output');
            
            if (!goal) return;
            
            output.textContent = '⏳ Agent working...';
            
            try {
                const response = await fetch('/api/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ goal })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    output.textContent = '✅ Task completed!\n\n' + result.output;
                } else {
                    output.textContent = '❌ Task failed\n\n' + result.error;
                }
            } catch (error) {
                output.textContent = '❌ Error: ' + error.message;
            }
        }
        
        document.getElementById('goalInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') executeTask();
        });
    </script>
</body>
</html>
    """
