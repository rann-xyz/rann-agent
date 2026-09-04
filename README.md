# RANN Agent V3

> **THE MODEL GENERATES DECISIONS. RANN CONTROLS EXECUTION.**

Autonomous AI engineering platform with 16-state machine, real terminal execution, evidence ledger, and structured memory.

## Status

- **169 tests passing** ✅
- **35% code coverage** (9,170 executable lines)
- **121 Python modules**
- **End-to-end execution verified** — LLM → tool calls → terminal → file system

## Features

### 16-State V3 State Machine
```
QUEUED → ANALYZING → CONTEXT_READY → PLANNING → WAITING_POLICY → EXECUTING → VERIFYING → COMPLETED
                              ↓            ↓              ↓            ↓
                          BLOCKED      FAILED        BLOCKED      FAILED
                                                          ↓
                                      RECOVERING → ROLLED_BACK → TIMED_OUT → CANCELLED → ABORTED
```

### V3 Architecture
- **RuntimeAgent** — Budget + lifecycle-driven execution loop
- **AgentLifecycle** — State machine + event emission + checkpointing
- **ToolRegistry** — OpenAI function-calling compatible tool definitions
- **RealTerminalExecutor** — Actual shell execution (not simulated)
- **CommandPolicy** — Risk classification (SAFE/LOW/MEDIUM/HIGH/CRITICAL)
- **EvidenceLedger** — Timestamped execution proof chain
- **EventBus** — 30+ event types with structured logging

### Memory System
- **ProjectMemoryStore** — Project metadata, dependencies, conventions
- **EpisodicMemoryStore** — Goal/action/observation/outcome/lessons per session
- **SemanticMemoryStore** — Key-value facts with similarity search
- **ConflictResolver** — Merge strategy for concurrent memories

### Storage & Recovery
- **SQLite Database** — 12 tables: runs, tasks, events, evidence, sessions, audit
- **CrashRecovery** — WAL checkpoint + re-execution from last turn
- **DurableQueue** — Persistent job queue with heartbeat
- **ConcurrencyControl** — Workspace/repository/file/database locks (fcntl)

## Installation

```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Quick Start

```bash
# System check
rann doctor

# Run a task (uses xkiro/minimax-m2.7-highspeed:free by default)
rann run "create a file hello.txt with content 'Hello World'"

# Dry run (no execution)
rann run "fix the bug" --dry-run

# Change model
rann config set agent.llm.provider "anthropic"
rann config set agent.llm.model "claude-sonnet-4-20250514"
rann config get
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `rann run "<task>"` | Execute task with V3 agent |
| `rann run "<task>" --dry-run` | Show plan without executing |
| `rann doctor` | System health check |
| `rann status` | Show tasks/runs/handlers |
| `rann task list` | List recent tasks |
| `rann task show <id>` | Show task details |
| `rann memory search <query>` | Search episodic memory |
| `rann audit` | Show audit log |
| `rann config get` | Show current config |
| `rann config set agent.llm.model <model>` | Change model |
| `rann config list-providers` | Show available providers |

## Configuration

Config file: `~/.rann_agent/config.yaml`

```yaml
agent:
  llm:
    provider: xkiro
    model: minimax/minimax-m2.7-highspeed:free
    max_tokens: 8192
    temperature: 0.7
    retry:
      max_attempts: 3
      backoff_multiplier: 2
```

### Available Providers

| Provider | Base URL | Example Model | Notes |
|----------|----------|---------------|-------|
| `xkiro` | https://api.xkiro.com | minimax/minimax-m2.7-highspeed:free | Free tier |
| `anthropic` | api.anthropic.com | claude-sonnet-4-20250514 | Needs ANTHROPIC_API_KEY |
| `openai` | api.openai.com | gpt-4o | Needs OPENAI_API_KEY |
| `custom` | https://seekai.cc | claude-fable-5-1 | Custom endpoint |
| `ollama` | localhost:11434 | llama3.1:8b | Local Ollama |

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
    print(result)

asyncio.run(main())
```

## Architecture

```
rann_agent/
├── core/
│   ├── runtime.py        # RuntimeAgent (budget + lifecycle + execute loop)
│   ├── lifecycle.py      # AgentLifecycle (state machine context manager)
│   ├── state.py          # 16-state machine + VALID_TRANSITIONS
│   ├── event_bus.py      # EventEmitter + EventType + EventStatus
│   ├── config.py         # Config + LLMConfig (pydantic)
│   ├── budget.py         # Budget + BudgetEngine
│   ├── task_contract.py  # TaskContract + TaskCategory + RiskLevel + AutonomyLevel
│   ├── evidence.py       # EvidenceLedger (SHA256 proof chain)
│   ├── tool_result.py    # ToolResult dataclass
│   ├── approval.py       # Approval + AutonomyLevel
│   ├── autonomy.py       # AutonomyGuard
│   ├── idempotency.py    # IdempotencyKey + RetryCache
│   ├── schemas.py        # Pydantic models
│   └── llm_provider.py   # BaseLLMProvider + CustomProvider + AnthropicProvider
├── orchestration/
│   ├── command_policy.py # CommandPolicy (risk classification)
│   └── model_router.py   # ModelRouter
├── tools/
│   ├── registry.py       # ToolRegistry (CRUD + get_definitions)
│   ├── executor.py       # ToolExecutor (async timeout)
│   ├── real_terminal.py  # RealTerminalExecutor (actual shell)
│   └── filesystem.py     # FilesystemEngine
├── planning/
│   ├── planner.py        # Planner (strategy selection)
│   ├── recovery.py       # RecoveryEngine
│   ├── progress.py       # ProgressEngine
│   └── semantic_diff.py  # SemanticDiff (AST-based)
├── storage/
│   ├── database.py       # SQLite (12 tables)
│   ├── recovery.py       # CrashRecovery + WAL
│   ├── queue.py          # DurableQueue
│   └── locks.py          # ConcurrencyControl (fcntl)
├── memory/
│   ├── project_store.py  # ProjectMemoryStore
│   ├── episodic_store.py # EpisodicMemoryStore
│   ├── semantic_store.py # SemanticMemoryStore
│   └── conflict.py       # ConflictResolver
├── intelligence/
│   └── learning.py       # LearningEngine
└── cli/
    └── rann.py           # CLI entry point (click)
```

## Test Results

```
169 passed, 23 warnings (deprecation only)
35.08% coverage (9,170 executable lines)
```

Run tests:
```bash
pytest tests/unit/ -v
```

## GitHub

https://github.com/rann-xyz/rann-agent

## License

MIT