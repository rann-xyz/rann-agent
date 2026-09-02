"""
FastAPI server with WebSocket support
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import structlog

from rann_agent import Agent, Config

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Rann Agent API",
    description="Next-generation autonomous AI agent",
    version="1.0.0",
)

# Load config
config = Config.load()

# CORS
if config.api.cors.get("enabled", True):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors.get("origins", ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Active agents
active_agents: Dict[str, Agent] = {}


class TaskRequest(BaseModel):
    goal: str
    context: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    stream: bool = False


class TaskResponse(BaseModel):
    session_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


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
        }
    }


@app.post("/api/execute", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    """Execute a task"""
    
    try:
        # Create agent
        agent = Agent(
            config=config,
            provider=request.provider,
            model=request.model,
        )
        
        # Execute
        result = await agent.execute(
            goal=request.goal,
            context=request.context,
        )
        
        return TaskResponse(
            session_id=agent.session_id,
            success=result.get("done", False),
            output=result.get("output"),
            error=result.get("error"),
            metadata=result.get("metadata", {}),
        )
    
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
        await websocket.send_json({
            "type": "session_started",
            "session_id": agent.session_id,
        })
        
        # Stream execution
        async for token in agent.stream(goal, context):
            await websocket.send_json({
                "type": "token",
                "data": token,
            })
        
        # Done
        await websocket.send_json({
            "type": "complete",
            "session_id": agent.session_id,
        })
    
    except WebSocketDisconnect:
        logger.info("websocket_disconnected")
    
    except Exception as e:
        logger.error("stream_failed", error=str(e))
        await websocket.send_json({
            "type": "error",
            "error": str(e),
        })


@app.get("/api/agents")
async def list_agents():
    """List active agents"""
    return {
        "count": len(active_agents),
        "agents": [
            {"session_id": sid, "status": "active"}
            for sid in active_agents.keys()
        ]
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
        }
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
