# Quick Start

Get RANN Agent running in 3 minutes.

## Installation

```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
chmod +x install.sh && ./install.sh
```

## CLI Usage

```bash
# Interactive chat mode
python terminal_app.py chat

# Single task
python terminal_app.py chat --goal "Write a hello world program"

# With streaming
python terminal_app.py chat --goal "Explain this code" --stream
```

## API Server

```bash
python terminal_app.py serve --port 8000
```

Then open http://localhost:8000 in your browser.

## Python API

```python
from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.budget import Budget

agent = RuntimeAgent(
    budget=Budget(max_tokens=10000, max_turns=20)
)

result = await agent.execute("Fix the bug in src/main.py")
print(result["output"])
```

## Configuration

```bash
cp config.yaml.example config.yaml
```

Set your API key in `config.yaml` or as environment variable:

```bash
export RANN_API_KEY=your-key
```

## Testing

```bash
source venv/bin/activate
pytest tests/ -v
```

## Next Steps

- Read [ROADMAP.md](ROADMAP.md) for development phases
- Check [docs/AUDIT.md](docs/AUDIT.md) for architecture details
- See [examples/](examples/) for more use cases