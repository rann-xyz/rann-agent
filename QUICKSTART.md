# Quick Start — RANN Agent V3

Get RANN Agent running in 3 minutes.

## Installation

```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
python -m venv venv && source venv/bin/activate
pip install -e .
```

## System Check

```bash
rann doctor
```

## Run Your First Task

```bash
rann run "create a file hello.txt with content 'Hello World'"
```

## Dry Run (no execution)

```bash
rann run "fix the bug in main.py" --dry-run
```

## Change Model

```bash
# See available providers
rann config list-providers

# Switch to Anthropic
rann config set agent.llm.provider anthropic
rann config set agent.llm.model claude-sonnet-4-20250514

# Back to free tier
rann config set agent.llm.provider xkiro
rann config set agent.llm.model minimax/minimax-m2.7-highspeed:free
```

## Python API

```python
import asyncio
from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.budget import Budget
from rann_agent.core.config import Config

async def main():
    config = Config()
    budget = Budget(max_tokens=10000, max_turns=20)
    agent = RuntimeAgent(budget=budget, config=config)
    
    result = await agent.execute("Write a hello world program in Python")
    print(result["output"])

asyncio.run(main())
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `rann run "<task>"` | Execute task |
| `rann run "<task>" --dry-run` | Plan without executing |
| `rann doctor` | System health check |
| `rann status` | Show status |
| `rann task list` | List tasks |
| `rann config get` | Show config |
| `rann config set <key> <value>` | Set config |
| `rann memory search <query>` | Search memory |
| `rann audit` | Audit log |

## Testing

```bash
source venv/bin/activate
pytest tests/unit/ -v
```

## Web Interface

```bash
python web_app.py
# Then open http://localhost:8000
```

## Next Steps

- Read [ROADMAP.md](ROADMAP.md) for development phases
- Check [docs/AUDIT.md](docs/AUDIT.md) for architecture details
- See [examples/](examples/) for more use cases