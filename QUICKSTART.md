# 🚀 Quick Start Guide

## Installation

```bash
# Clone repository
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent

# Install dependencies
pip install -e .

# Or with uv (recommended)
uv pip install -e .
```

## Configuration

1. **Copy environment template:**
```bash
cp .env.example .env
```

2. **Add your API key** in `.env`:
```env
# Choose one:
ANTHROPIC_API_KEY=sk-ant-xxxxx
# or
OPENAI_API_KEY=sk-xxxxx
```

3. **Copy config template (optional):**
```bash
cp config.yaml.example config.yaml
# Edit config.yaml to customize
```

## Usage

### CLI Mode

```bash
# Simple task
rann-agent chat "analyze my Python project and suggest improvements"

# With context
rann-agent chat "fix the login bug" --context "User reported timeout after 30s"

# Stream mode
rann-agent chat "write a REST API for user management" --stream

# Different provider
rann-agent chat "deploy to production" --provider openai --model gpt-4-turbo
```

### Web Dashboard

```bash
# Start server
rann-agent serve

# Open browser
open http://localhost:8000/dashboard

# API docs
open http://localhost:8000/docs
```

### Python API

```python
from rann_agent import Agent

# Create agent
agent = Agent(
    provider="anthropic",
    model="claude-sonnet-4-20250514"
)

# Execute task
result = await agent.execute(
    goal="Create a FastAPI app with user authentication",
    context="Use JWT tokens and PostgreSQL"
)

print(result["output"])
```

### Streaming

```python
async def main():
    agent = Agent()
    
    async for token in agent.stream("Build a TODO app with React"):
        print(token, end="", flush=True)
```

### Multi-Agent Orchestration

```python
from rann_agent import Agent

agent = Agent()
coordinator = agent.spawn_coordinator()

# Execute tasks in parallel
results = await coordinator.execute_parallel([
    {"goal": "Run all tests"},
    {"goal": "Build Docker image"},
    {"goal": "Update documentation"},
])

for result in results:
    print(f"✅ {result['task']}: {result['result']}")
```

## Features Demo

### Self-Healing Error Recovery

The agent automatically detects, analyzes, and fixes errors:

```bash
$ rann-agent chat "run the tests"

# Agent tries:
❌ Error: ModuleNotFoundError: No module named 'pytest'

# Self-healing kicks in:
🔄 Analyzing error...
🔄 Installing missing package: pytest
✅ Installed pytest==8.0.0
✅ Tests passed (47/47)
```

### Tool Usage

```python
agent = Agent(tools=["terminal", "files", "web", "code_exec", "git"])

# Agent can:
# - Execute shell commands
# - Read/write files
# - Search web
# - Execute code
# - Git operations
# - And more!
```

## Configuration Examples

### Local Models (No API Key)

```yaml
# config.yaml
agent:
  llm:
    provider: "ollama"
    model: "llama3.1:70b"
```

```bash
# Make sure Ollama is running
ollama serve

# Use it
rann-agent chat "your task"
```

### Multiple Fallbacks

```yaml
agent:
  llm:
    provider: "anthropic"
    model: "claude-sonnet-4-20250514"
    fallback_providers:
      - provider: "openai"
        model: "gpt-4-turbo"
      - provider: "ollama"
        model: "llama3.1:70b"
```

### Custom Tools

```python
from rann_agent.tools import Tool, ToolResult

class CustomTool(Tool):
    name = "my_tool"
    description = "Does something cool"
    
    async def execute(self, **kwargs):
        # Your logic
        return ToolResult(
            tool=self.name,
            success=True,
            output="Done!"
        ).to_dict()

# Register
agent = Agent()
agent.tools.register(CustomTool(agent.config))
```

## Tips

1. **Start with simple tasks** to understand agent behavior
2. **Use streaming mode** for real-time feedback
3. **Check logs** in `~/.rann-agent/logs/` for debugging
4. **Review session history** with memory stats
5. **Customize tools** in `config.yaml` to enable/disable features

## Troubleshooting

### API Key Not Found
```bash
# Check environment
echo $ANTHROPIC_API_KEY

# Or set directly
export ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Module Not Found
```bash
# Reinstall dependencies
pip install -e .

# Or with specific extras
pip install -e ".[all]"
```

### Agent Not Responding
```bash
# Check config
rann-agent config-show

# Validate setup
rann-agent tools-list
```

## Next Steps

- Read [Architecture](ARCHITECTURE.md)
- Explore [Examples](examples/)
- Check [API Reference](https://rann-agent.dev/api)
- Join [Discord](https://discord.gg/rann-agent)

---

**Need help?** Open an issue on [GitHub](https://github.com/rann-xyz/rann-agent/issues)
