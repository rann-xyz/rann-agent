# RANN Agent V3

[![CI](https://github.com/rann-xyz/rann-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/rann-xyz/rann-agent/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/rann-xyz/rann-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/rann-xyz/rann-agent)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **THE MODEL GENERATES DECISIONS. RANN CONTROLS EXECUTION.**

Autonomous AI engineering platform with 16-state machine, real terminal execution, evidence ledger, structured memory, and multi-provider LLM support.

## Status

- **317 tests passing** ✅ (19 test files across unit/integration/security/benchmarks)
- **37.15% code coverage** (4,345 of 11,695 executable lines)
- **Phase 1 complete** ✅ — Foundation & Stability
- **Phase 2 in progress** ✅ — Self-healing, rollback, permissions, caching
- **Phase 3 in progress** ✅ — Tool execution, terminal, memory, context
- **7 LLM providers** ✅ — Groq, DeepSeek, OpenAI, Anthropic, Gemini, Ollama, Custom
- **Vercel deployment** ✅ — SPA + API functions, streaming SSE chat

## Features

### 12-State V3 State Machine
```
QUEUED → ANALYZING → CONTEXT_READY → PLANNING → WAITING_POLICY → EXECUTING → VERIFYING → ACCEPTANCE_CHECK → LEARNING → COMPLETED
                              ↓            ↓              ↓            ↓            ↓
                          BLOCKED      FAILED        BLOCKED      FAILED      ROLLED_BACK
                                                          ↓
                                      RECOVERING → TIMED_OUT → CANCELLED → ROLLED_BACK
```

### V3 Architecture
- **RuntimeAgent** — Budget + lifecycle-driven execution loop
- **AgentLifecycle** — State machine + event emission + checkpointing
- **ToolRegistry** — OpenAI function-calling compatible tool definitions
- **RealTerminalExecutor** — Actual shell execution (not simulated)
- **CommandPolicy** — Risk classification (SAFE/LOW/MEDIUM/HIGH/CRITICAL)
- **EvidenceLedger** — SHA256 proof chain for every action
- **EventBus** — 30+ event types with structured logging via structlog

### Memory System
- **ProjectMemoryStore** — Project metadata, dependencies, conventions
- **EpisodicMemoryStore** — Goal/action/observation/outcome/lessons per session
- **SemanticMemoryStore** — Key-value facts with similarity search
- **ConflictResolver** — Merge strategy for concurrent memories

### Storage & Recovery
- **SQLite Database** — 12 tables: runs, tasks, events, evidence, sessions, audit
- **Connection Pooling** — WAL mode, mmap, threading-safe pooled connections
- **CrashRecovery** — WAL checkpoint + re-execution from last turn
- **DurableQueue** — Persistent job queue with heartbeat
- **ConcurrencyControl** — Workspace/repository/file/database locks (fcntl)

### Self-Healing & Recovery
- **RecoveryEngine** — Automatic error classification and fix strategy selection
- **RollbackEngine** — File-level rollback with atomic operations
- **PermissionManager** — Elevated permission acquisition and verification

### Performance
- **CacheManager** — Redis + in-memory LRU fallback
- **ContextWindowManager** — Trim + summarize strategies for large contexts
- **HotPathProfiler** — cProfile/py-spy profiling with flamegraph output
- **SLO Benchmarks** — Contractual p50/p95/p99 latency SLOs

## Installation

```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
./setup.sh
# or manual:
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Quick Start

```bash
# System check
rann doctor

# Run a task (uses Groq llama-3.1-70b-versatile by default)
rann run "create a file hello.txt with content 'Hello World'"

# Dry run (no execution)
rann run "fix the bug" --dry-run

# Change provider/model
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
    provider: groq
    model: llama-3.1-70b-versatile
    max_tokens: 8192
    temperature: 0.7
    retry:
      max_attempts: 3
      backoff_multiplier: 2
```

### Available Providers

| Provider | Base URL | Default Model | Free Tier |
|----------|----------|---------------|-----------|
| `groq` | https://api.groq.com/openai/v1 | llama-3.1-70b-versatile | ✅ |
| `deepseek` | https://api.deepseek.com/v1 | deepseek-chat | ✅ |
| `openai` | https://api.openai.com/v1 | gpt-4o | ❌ |
| `anthropic` | https://api.anthropic.com/v1 | claude-sonnet-4-20250514 | ❌ |
| `gemini` | https://generativelanguage.googleapis.com/v1beta | gemini-1.5-flash | ✅ |
| `ollama` | http://localhost:11434/v1 | llama3.2 | ✅ |
| `custom` | configurable | configurable | ✅ |

## Web UI & API

Start the web server:
```bash
python web_api.py
```

Then open `index.html` in your browser. The web UI features:
- Streaming SSE chat with provider selection
- Real-time token usage tracking
- Session history

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/providers` | List all providers and models |
| `GET` | `/api/config` | Default provider & model |
| `GET` | `/api/status` | System status |
| `POST` | `/api/chat` | Streaming chat (SSE) |
| `POST` | `/api/clear` | Clear session |

### Vercel Deployment

```bash
vercel          # preview deploy
vercel --prod   # production deploy
```

Vercel-configured endpoints:
- `GET /api/providers` → `api/index.js`
- `GET /api/config` → `api/index.js`
- `GET /api/status` → `api/index.js`
- `POST /api/chat` → `api/index.js` (streaming SSE)
- `POST /api/clear` → `api/index.js`
- `/*` → `index.html` (SPA)

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
│   ├── state.py          # 12-state machine + VALID_TRANSITIONS
│   ├── event_bus.py      # EventEmitter + EventType + EventStatus
│   ├── config.py         # Config + LLMConfig (pydantic)
│   ├── budget.py         # Budget + BudgetEngine
│   ├── task_contract.py  # TaskContract + TaskCategory + RiskLevel + AutonomyLevel
│   ├── evidence.py       # EvidenceLedger (SHA256 proof chain)
│   ├── tool_result.py    # ToolResult dataclass
│   ├── approval.py       # Approval + AutonomyLevel
│   ├── autonomy.py       # AutonomyGuard
│   ├── idempotency.py    # IdempotencyKey + RetryCache
│   └── llm_provider.py   # BaseLLMProvider + all 7 providers
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
│   ├── pool.py           # Connection pool (WAL, mmap, threading-safe)
│   ├── recovery.py       # CrashRecovery + WAL
│   ├── queue.py          # DurableQueue
│   └── locks.py          # ConcurrencyControl (fcntl)
├── utils/
│   ├── cache.py          # Redis + in-memory caching layer
│   ├── context_window.py # Context window management (trim/summarize)
│   ├── http_pool.py      # Shared httpx connection pool
│   └── profiler.py       # cProfile hot-path profiler
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
tests/unit/              15 files, 283 tests
tests/integration/       1 file,   8 tests  (E2E, multi-agent, memory)
tests/security/          1 file,   7 tests  (security audit)
tests/benchmarks/        3 files, 19 tests  (SLO, performance, benchmark)
─────────────────────────────────────────────────
Total:                   20 files, 317 tests
37.15% coverage (4,345 of 11,695 lines covered)
```

Run tests:
```bash
pytest tests/ -v
pytest tests/unit/ -v
pytest tests/benchmarks/ -v --benchmark-only
```

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Foundation & Stability — state machine, events, budget, tools, DB, cache |
| **Phase 2** | ✅ In Progress | Advanced features — self-healing, rollback, permissions, memory, context |
| **Phase 3** | ✅ In Progress | Capabilities — tool execution, terminal, planner, evidence ledger |
| **Phase 4+** | 🔄 Planned | Platform integrations, distributed, observability |

See [ROADMAP.md](ROADMAP.md) for full 8-phase plan.

## GitHub

https://github.com/rann-xyz/rann-agent

## License

MIT