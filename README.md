# RANN Agent

**RANN Agent** — Next-generation autonomous AI engineering platform that outperforms existing solutions through superior architecture, execution reliability, and measurable autonomy.

> "THE MODEL GENERATES DECISIONS. RANN CONTROLS EXECUTION."

## Features

### Core Architecture
- **Explicit State Machine** — 14 defined states (CREATED → COMPLETED/FAILED) with validated transitions
- **Structured Event System** — 25+ event types with full audit trail
- **Budget Engine** — Token, time, tool call, model call, and cost limits with warnings
- **Verification Engine** — Evidence-based task completion proof

### Cognition & Planning
- **Task Graph** — Explicit dependency management with parallel execution support
- **Strategy Selector** — DIRECT / PLANNER / MULTI-AGENT / RESEARCH routing
- **Model Router** — Optimal model selection based on complexity, cost, and capabilities
- **Evaluator** — Rubric-based scoring (correctness, efficiency, style, safety)

### Tool System
- **Tool Executor** — Async execution with timeout, rate limiting, and sandbox support
- **Tool Discovery** — Auto-scan and catalog available tools
- **Tool Policy Engine** — Risk classification (SAFE/LOW/MEDIUM/HIGH/CRITICAL) with enforcement

### Memory & Learning
- **Working Memory** — LRU key-value store with TTL and access tracking
- **Procedural Memory** — Skill storage with categories, success tracking, and persistence
- **Skills System** — Registry, loader, and evaluator for reusable procedures

### Security
- **Sandbox** — NONE / SUBPROCESS / DOCKER isolation modes
- **Secrets Detection** — Regex patterns for API keys, passwords, tokens, certificates
- **Input Validation** — Path traversal, command injection, and dangerous pattern blocking

## Installation

```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
pip install -r requirements.txt
```

Or use the installer:

```bash
chmod +x install.sh && ./install.sh
```

## Quick Start

```python
from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.budget import Budget

agent = RuntimeAgent(
    budget=Budget(max_tokens=10000, max_turns=20),
    verification_level="moderate"
)

result = await agent.execute("Write a hello world program in Python")
print(result["output"])
```

## CLI Usage

```bash
# Chat mode
python terminal_app.py chat --goal "Fix the bug in src/main.py"

# Stream mode
python terminal_app.py chat --goal "Explain this code" --stream

# Serve API
python terminal_app.py serve --port 8000
```

## Architecture

```
TASK / GOAL
    │
    ▼
CONTEXT ENGINE → TASK ANALYSIS → TASK GRAPH
    │
    ▼
STRATEGY SELECTOR (DIRECT / PLANNER / MULTI-AGENT / RESEARCH)
    │
    ▼
MODEL ROUTER → TOOL PLANNER → POLICY CHECK
    │
    ├─ DENY → REPLAN
    └─ ALLOW → EXECUTE → OBSERVE → VERIFICATION
                                │
                    ┌──────────┴──────────┐
                  FAIL                  PASS
                    │                     │
                RECOVERY               RESULT
                    │                     │
                RETRY/REPLAN/ROLLBACK ───┘
                            │
                           LEARN
                            │
                          MEMORY
                            │
                        COMPLETION
```

## Project Structure

```
rann_agent/
├── core/           # State machine, events, budget, verification, runtime
├── cognition/      # Evaluator, strategy selector
├── orchestration/  # Task graph, tool policy, model router
├── tools/          # Executor, discovery, built-in tools
├── memory/         # Working memory, procedural memory
├── skills/         # Registry, loader, evaluator
├── interfaces/     # TUI, API client
├── security/       # Sandbox, secrets, validation
└── ...
```

## Configuration

Copy and edit the config:

```bash
cp config.yaml.example config.yaml
```

Key settings in `config.yaml`:

```yaml
agent:
  llm:
    provider: custom
    model: claude-fable-5-1
    api_base: https://seekai.cc/v1

tools:
  enabled:
    - file_read
    - file_write
    - terminal
    - git
```

## Testing

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=rann_agent --cov-fail-under=15
```

## Documentation

- [ROADMAP.md](ROADMAP.md) — Development phases and progress
- [PROGRESS.md](PROGRESS.md) — Current implementation status
- [docs/AUDIT.md](docs/AUDIT.md) — Forensic audit and architecture analysis
- [docs/FEATURE_MATRIX.md](docs/FEATURE_MATRIX.md) — Feature truth table

## License

MIT