"""
Web localhost application for Rann Agent.
FastAPI + WebSocket for real-time interaction.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import json
from typing import Dict, Any, List
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rann_agent.intelligence import (
    CodebaseContext,
    CodeCompletion,
    AutonomousCoder
)


app = FastAPI(title="Rann Agent Web Interface")

# Store active connections
connections: List[WebSocket] = []

# Initialize modules
codebase_context = CodebaseContext(".")
code_completion = CodeCompletion()
autonomous_coder = AutonomousCoder()


HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rann Agent - AI Coding Assistant</title>
    <style>
        :root {
            --bg-0: #05070C;
            --bg-1: #0A0D12;
            --bg-2: #0F131C;
            --bg-3: #161D2B;
            --bg-4: #1E2636;
            --accent: #38BDF8;
            --accent-muted: #6EE7B7;
            --text: #E2E8F0;
            --text-dim: #94A3B8;
            --success: #6EE7B7;
            --error: #F87171;
            --warning: #FCD34D;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, var(--bg-0) 0%, var(--bg-1) 100%);
            color: var(--text);
            min-height: 100vh;
            display: grid;
            grid-template-rows: auto 1fr auto;
        }
        
        header {
            background: var(--bg-2);
            padding: clamp(1rem, 2vw, 2rem);
            border-bottom: 1px solid var(--bg-3);
        }
        
        h1 {
            font-size: clamp(1.5rem, 4vw, 2.5rem);
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-muted) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        
        .subtitle {
            color: var(--text-dim);
            font-size: clamp(0.875rem, 2vw, 1rem);
        }
        
        main {
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 1.5rem;
            padding: 1.5rem;
            max-width: 1800px;
            margin: 0 auto;
            width: 100%;
        }
        
        .sidebar {
            background: var(--bg-2);
            border-radius: 16px;
            padding: 1.5rem;
            height: fit-content;
        }
        
        .sidebar h3 {
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-dim);
            margin-bottom: 1rem;
        }
        
        .stats {
            display: grid;
            gap: 1rem;
        }
        
        .stat-card {
            background: var(--bg-3);
            padding: 1rem;
            border-radius: 12px;
        }
        
        .stat-value {
            font-size: 1.875rem;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 0.25rem;
        }
        
        .stat-label {
            font-size: 0.875rem;
            color: var(--text-dim);
        }
        
        .chat-container {
            display: grid;
            grid-template-rows: 1fr auto;
            background: var(--bg-2);
            border-radius: 16px;
            overflow: hidden;
            height: calc(100vh - 180px);
        }
        
        #messages {
            padding: 1.5rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        
        #messages::-webkit-scrollbar {
            width: 8px;
        }
        
        #messages::-webkit-scrollbar-track {
            background: var(--bg-1);
        }
        
        #messages::-webkit-scrollbar-thumb {
            background: var(--bg-4);
            border-radius: 999px;
        }
        
        .message {
            padding: 1rem 1.25rem;
            border-radius: 12px;
            max-width: 80%;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            background: var(--bg-4);
            margin-left: auto;
            border-bottom-right-radius: 4px;
        }
        
        .message.agent {
            background: var(--bg-3);
            border-bottom-left-radius: 4px;
            border-left: 3px solid var(--accent);
        }
        
        .message.system {
            background: var(--bg-1);
            border-left: 3px solid var(--warning);
            max-width: 100%;
            font-size: 0.875rem;
            color: var(--text-dim);
        }
        
        .message.error {
            background: rgba(248, 113, 113, 0.1);
            border-left: 3px solid var(--error);
        }
        
        .input-area {
            background: var(--bg-3);
            padding: 1.5rem;
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 1rem;
            align-items: center;
        }
        
        input {
            background: var(--bg-4);
            border: 1px solid transparent;
            color: var(--text);
            padding: 0.875rem 1.25rem;
            border-radius: 999px;
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1);
        }
        
        button {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-muted) 100%);
            color: var(--bg-0);
            border: none;
            padding: 0.875rem 2rem;
            border-radius: 999px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 1rem;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(56, 189, 248, 0.3);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 999px;
            background: var(--success);
            display: inline-block;
            margin-right: 0.5rem;
            animation: pulse 2s ease infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .quick-actions {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        
        .quick-action {
            background: var(--bg-3);
            border: 1px solid var(--bg-4);
            color: var(--accent);
            padding: 0.5rem 1rem;
            border-radius: 999px;
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .quick-action:hover {
            background: var(--bg-4);
            border-color: var(--accent);
        }
        
        @media (max-width: 768px) {
            main {
                grid-template-columns: 1fr;
            }
            .sidebar {
                display: none;
            }
        }
    </style>
</head>
<body>
    <header>
        <h1>🤖 Rann Agent</h1>
        <p class="subtitle">
            <span class="status-indicator"></span>
            The Most Advanced AI Coding Agent
        </p>
    </header>
    
    <main>
        <aside class="sidebar">
            <h3>Statistics</h3>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value" id="tasksCompleted">0</div>
                    <div class="stat-label">Tasks Completed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="filesIndexed">0</div>
                    <div class="stat-label">Files Indexed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="linesOfCode">0</div>
                    <div class="stat-label">Lines of Code</div>
                </div>
            </div>
        </aside>
        
        <div class="chat-container">
            <div id="messages">
                <div class="message agent">
                    👋 Hi! Aku Rann Agent, AI coding assistant paling canggih!<br><br>
                    Aku bisa:
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li>Code autonomous (seperti Devin AI)</li>
                        <li>Understand codebase (seperti Cursor)</li>
                        <li>Smart completions (seperti Copilot)</li>
                        <li>Debug & test otomatis</li>
                    </ul>
                    <br>
                    Ketik perintah atau pilih quick action di bawah! 🚀
                </div>
            </div>
            
            <div class="input-area">
                <div style="grid-column: 1 / -1;">
                    <div class="quick-actions">
                        <button class="quick-action" onclick="sendQuickAction('index')">📚 Index Codebase</button>
                        <button class="quick-action" onclick="sendQuickAction('status')">📊 Show Status</button>
                        <button class="quick-action" onclick="sendQuickAction('help')">❓ Help</button>
                    </div>
                </div>
                <input 
                    type="text" 
                    id="messageInput" 
                    placeholder="Type a command... (e.g., 'code Build REST API')"
                    autofocus
                />
                <button onclick="sendMessage()" id="sendButton">Send</button>
            </div>
        </div>
    </main>
    
    <script>
        let ws;
        
        function connect() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);
            
            ws.onopen = () => {
                console.log('Connected to Rann Agent');
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };
            
            ws.onclose = () => {
                console.log('Disconnected, reconnecting...');
                setTimeout(connect, 1000);
            };
        }
        
        function handleMessage(data) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${data.type}`;
            messageDiv.innerHTML = data.content;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            // Update stats if provided
            if (data.stats) {
                if (data.stats.tasks_completed !== undefined) {
                    document.getElementById('tasksCompleted').textContent = data.stats.tasks_completed;
                }
                if (data.stats.files_indexed !== undefined) {
                    document.getElementById('filesIndexed').textContent = data.stats.files_indexed;
                }
                if (data.stats.lines_of_code !== undefined) {
                    document.getElementById('linesOfCode').textContent = data.stats.lines_of_code;
                }
            }
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Show user message
            handleMessage({
                type: 'user',
                content: message
            });
            
            // Send to server
            ws.send(JSON.stringify({
                command: message
            }));
            
            input.value = '';
        }
        
        function sendQuickAction(action) {
            const input = document.getElementById('messageInput');
            input.value = action;
            sendMessage();
        }
        
        // Enter key to send
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
        
        // Connect on load
        connect();
    </script>
</body>
</html>
"""


@app.get("/")
async def get_home():
    """Serve web interface."""
    return HTMLResponse(content=HTML_CONTENT)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
    connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            command = message.get('command', '')
            
            # Process command
            response = await process_command(command)
            
            # Send response
            await websocket.send_text(json.dumps(response))
    
    except WebSocketDisconnect:
        connections.remove(websocket)


async def process_command(command: str) -> Dict[str, Any]:
    """Process command and return response."""
    parts = command.strip().split(maxsplit=1)
    if not parts:
        return {
            'type': 'error',
            'content': '❌ Empty command'
        }
    
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    try:
        if cmd == "help":
            return {
                'type': 'agent',
                'content': """
                <strong>📚 Available Commands:</strong><br><br>
                <strong>Coding:</strong><br>
                • <code>code &lt;description&gt;</code> - Autonomous coding<br>
                • <code>debug &lt;error&gt;</code> - Debug issue<br>
                • <code>test &lt;function&gt;</code> - Generate tests<br><br>
                <strong>Codebase:</strong><br>
                • <code>index</code> - Index codebase<br>
                • <code>find &lt;symbol&gt;</code> - Find symbol<br>
                • <code>search &lt;query&gt;</code> - Search code<br>
                • <code>summary</code> - Codebase summary<br><br>
                <strong>Other:</strong><br>
                • <code>status</code> - Show status<br>
                • <code>help</code> - This help
                """
            }
        
        elif cmd == "status":
            summary = await codebase_context.get_codebase_summary()
            task_summary = await autonomous_coder.get_task_summary()
            
            return {
                'type': 'agent',
                'content': f"""
                <strong>📊 Agent Status</strong><br><br>
                <strong>Codebase:</strong><br>
                • Files: {summary['total_files']}<br>
                • Symbols: {summary['total_symbols']}<br><br>
                <strong>Tasks:</strong><br>
                • Completed: {task_summary['completed']}<br>
                • Success Rate: {task_summary['success_rate']*100:.1f}%
                """,
                'stats': {
                    'tasks_completed': task_summary['completed'],
                    'files_indexed': summary['total_files'],
                    'lines_of_code': 0
                }
            }
        
        elif cmd == "index":
            stats = await codebase_context.index_codebase()
            
            return {
                'type': 'agent',
                'content': f"""
                <strong>✅ Codebase Indexed!</strong><br><br>
                • Total Files: {stats['total_files']}<br>
                • Total Lines: {stats['total_lines']}<br>
                • Languages: {', '.join(stats['languages'].keys())}
                """,
                'stats': {
                    'files_indexed': stats['total_files'],
                    'lines_of_code': stats['total_lines']
                }
            }
        
        elif cmd == "code":
            if not args:
                return {
                    'type': 'error',
                    'content': '❌ Usage: code &lt;description&gt;'
                }
            
            requirements = [req.strip() for req in args.split(',')] if ',' in args else [args]
            
            task = await autonomous_coder.implement_feature(
                task_description=args,
                requirements=requirements
            )
            
            return {
                'type': 'agent',
                'content': f"""
                <strong>✅ Task Completed!</strong><br><br>
                • Status: {task.status.value}<br>
                • Files Modified: {len(task.files_modified)}<br>
                • Tests Written: {task.tests_written}<br>
                • Bugs Fixed: {task.bugs_fixed}
                """
            }
        
        elif cmd == "find":
            if not args:
                return {
                    'type': 'error',
                    'content': '❌ Usage: find &lt;symbol&gt;'
                }
            
            results = await codebase_context.find_symbol(args)
            
            if not results:
                return {
                    'type': 'agent',
                    'content': f'⚠️ No results found for "{args}"'
                }
            
            content = f'<strong>🔍 Found {len(results)} result(s) for "{args}":</strong><br><br>'
            for r in results:
                content += f'• {r["file"]} ({r["type"]}) at line {r["line"]}<br>'
            
            return {
                'type': 'agent',
                'content': content
            }
        
        elif cmd == "search":
            results = await codebase_context.search_code(args, limit=5)
            
            if not results:
                return {
                    'type': 'agent',
                    'content': f'⚠️ No results found for "{args}"'
                }
            
            content = f'<strong>🔍 Search results for "{args}":</strong><br><br>'
            for r in results:
                content += f'• {r["name"]} in {r["file"]}<br>'
            
            return {
                'type': 'agent',
                'content': content
            }
        
        elif cmd == "summary":
            summary = await codebase_context.get_codebase_summary()
            
            content = '<strong>📊 Codebase Summary:</strong><br><br>'
            content += f'• Total Files: {summary["total_files"]}<br>'
            content += f'• Total Symbols: {summary["total_symbols"]}<br>'
            content += f'• Indexed Files: {summary["indexed_files"]}<br><br>'
            content += '<strong>Languages:</strong><br>'
            for lang, count in summary['languages'].items():
                content += f'• {lang}: {count}<br>'
            
            return {
                'type': 'agent',
                'content': content
            }
        
        else:
            return {
                'type': 'error',
                'content': f'❌ Unknown command: {cmd}<br>Type "help" for available commands'
            }
    
    except Exception as e:
        return {
            'type': 'error',
            'content': f'❌ Error: {str(e)}'
        }


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Rann Agent Web Interface...")
    print("📍 Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000)
