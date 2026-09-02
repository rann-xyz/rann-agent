# 🤖 Rann Agent

**Next-generation autonomous AI agent** — more advanced than Hermes, with self-healing, multi-agent orchestration, and enterprise-grade tooling.

## ✨ Features

### 🔥 Advanced over Hermes
- **Self-Healing Error Recovery** — automatic retry with exponential backoff & strategy adaptation
- **Multi-Agent Orchestration** — spawn sub-agents, parallel task execution, agent coordination
- **Extensible Tool System** — plugin-based architecture, hot-reload, custom tool registry
- **Advanced Memory** — persistent context, vector search ready, cross-session memory
- **Background Task Queue** — async execution, progress tracking, cancellation support
- **Web Dashboard** — real-time monitoring, session replay, tool inspection
- **Multi-Provider LLM** — Anthropic, OpenAI, local models (Ollama), with automatic fallback
- **Streaming Responses** — real-time token streaming for better UX
- **Parallel Tool Execution** — concurrent tool calls when dependencies allow
- **Session Management** — persistent sessions, resume, replay, search
- **Production Ready** — structured logging, error tracking, metrics, observability

### 🛠️ Core Tools
- Terminal execution (foreground/background/pty)
- File operations (read/write/patch/search)
- Web scraping & extraction
- Code execution (Python/Node/shell)
- Git operations
- API clients (REST/GraphQL)
- Database connectors
- Custom tool plugins

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
pip install -e .
```

### 2. Configuration
```bash
# Copy example config
cp .env.example .env
cp config.yaml.example config.yaml

# Edit .env and add your API key
nano .env
```

Add your API key:
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
# or
OPENAI_API_KEY=sk-xxxxx
```

### 3. Run
```bash
# CLI mode
rann-agent chat "deploy my app to production"

# Web dashboard
rann-agent serve --port 8000

# Background daemon
rann-agent daemon start
```

## 📚 Architecture

```
┌─────────────────────────────────────────┐
│         User Interface Layer            │
│  (CLI / Web Dashboard / API / Telegram) │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      Agent Orchestration Layer          │
│  • Task Planning & Decomposition        │
│  • Multi-Agent Coordination             │
│  • Self-Healing Error Recovery          │
│  • Context & Memory Management          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         LLM Provider Layer              │
│  • Anthropic Claude (primary)           │
│  • OpenAI GPT (fallback)                │
│  • Ollama (local models)                │
│  • Automatic failover & retry           │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│          Tool Execution Layer           │
│  • Terminal • Files • Web • Code        │
│  • Git • DB • API • Custom Plugins      │
│  • Parallel execution • Sandboxing      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      Persistence & Observability        │
│  • SQLite sessions • Logs • Metrics     │
│  • Error tracking • Audit trail         │
└─────────────────────────────────────────┘
```

## 🎯 Usage Examples

### CLI
```bash
# Simple task
rann-agent "find all TODO comments in this repo"

# Complex multi-step
rann-agent "analyze the codebase, write tests for untested functions, run them, fix failures"

# With context
rann-agent --context "Python project using pytest" "add test coverage reporting"

# Background task
rann-agent --background "train the model and notify me when done"
```

### Python API
```python
from rann_agent import Agent

agent = Agent(
    provider="anthropic",
    model="claude-sonnet-4-20250514",
    tools=["terminal", "files", "web"]
)

# Sync execution
result = agent.execute("deploy to staging")

# Async execution
async def main():
    result = await agent.execute_async("analyze logs for errors")
    async for token in agent.stream("write a comprehensive test suite"):
        print(token, end="")

# Multi-agent orchestration
coordinator = agent.spawn_coordinator()
results = await coordinator.execute_parallel([
    "run tests",
    "build docker image", 
    "update documentation"
])
```

### Web Dashboard
```bash
rann-agent serve --port 8000
# Open http://localhost:8000
```

Features:
- Real-time session monitoring
- Tool execution timeline
- Token usage & cost tracking
- Session replay
- Agent spawning interface
- Log viewer

## 🔧 Configuration

### config.yaml
```yaml
agent:
  name: "Rann Agent"
  model: "claude-sonnet-4-20250514"
  provider: "anthropic"
  temperature: 0.7
  max_tokens: 8192
  
  self_healing:
    enabled: true
    max_retries: 3
    backoff_multiplier: 2.0
    
  orchestration:
    max_concurrent_agents: 5
    task_timeout: 3600
    
  memory:
    persist: true
    vector_search: false  # set true for semantic search
    max_context_length: 100000

tools:
  enabled:
    - terminal
    - files
    - web
    - code_exec
    - git
  
  terminal:
    default_timeout: 300
    allow_background: true
    
  files:
    max_file_size: 10485760  # 10MB
    
logging:
  level: INFO
  file: ~/.rann-agent/logs/agent.log
  
api:
  host: "0.0.0.0"
  port: 8000
  cors_origins: ["*"]
```

## 🧠 Self-Healing Examples

When errors occur, the agent:
1. **Analyzes** the error context
2. **Searches** for similar past resolutions
3. **Proposes** multiple fix strategies
4. **Executes** fixes automatically
5. **Learns** from the outcome

```python
# Example: Package not found
$ rann-agent "run the tests"
❌ ModuleNotFoundError: pytest not found
🔄 Self-healing: Installing missing package...
✅ Installed pytest==8.0.0
✅ Tests passed (47/47)
```

## 🌐 Multi-Agent Coordination

```python
# Spawn specialized agents
coordinator = Agent().spawn_coordinator()

# Define parallel tasks
tasks = [
    {"role": "backend", "goal": "add user authentication"},
    {"role": "frontend", "goal": "create login form"},
    {"role": "devops", "goal": "setup auth0 integration"}
]

# Execute with dependency resolution
results = await coordinator.execute_graph(tasks)
```

## 📊 Monitoring

```bash
# View live sessions
rann-agent sessions list

# Inspect specific session
rann-agent sessions show <session_id>

# Export session transcript
rann-agent sessions export <session_id> --format json

# View metrics
rann-agent metrics --since 24h
```

## 🔌 Plugin Development

```python
from rann_agent.tools.base import Tool, ToolResult

class CustomTool(Tool):
    name = "my_custom_tool"
    description = "Does something amazing"
    
    async def execute(self, **kwargs) -> ToolResult:
        # Your logic here
        return ToolResult(
            success=True,
            output="Result data",
            metadata={"duration": 0.5}
        )

# Register
from rann_agent.tools import registry
registry.register(CustomTool)
```

## 🛡️ Safety

- Input sanitization for all terminal commands
- Sandboxed code execution
- Permission system for destructive operations
- Audit trail for all actions
- Rate limiting on API calls
- Secret detection & redaction

## 📈 Roadmap

- [ ] Vector memory with semantic search
- [ ] Browser automation (Playwright)
- [ ] Voice interface
- [ ] Mobile app
- [ ] Distributed agent swarms
- [ ] Fine-tuning on user patterns
- [ ] Blockchain integration tools
- [ ] Multi-modal inputs (vision, audio)

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 License

MIT License - see [LICENSE](LICENSE)

## 🙏 Credits

Built by [Rann](https://github.com/rann-xyz) — inspired by Hermes, elevated beyond.

---

**Rann Agent** — The autonomous AI that fixes itself, coordinates teams, and gets work done.
