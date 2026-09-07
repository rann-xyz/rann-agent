# RANN Agent Architecture Report

**Repository:** `/home/userland/rann-agent`
**Generated:** 2026-09-07 (updated from 2026-09-06)
**Purpose:** Comprehensive inventory of implemented codebase

---

## EXECUTIVE SUMMARY

RANN Agent is a Python-based autonomous AI agent framework with **substantial core infrastructure fully implemented**. It has two parallel agent implementations:
- `Agent` (legacy) — basic single-turn execution loop
- `RuntimeAgent` (Phase 1) — full state-machine-driven agent with events, budget, verification

The codebase is well-structured with clear separation across: core runtime, tools, orchestration, memory, intelligence, reasoning, and utilities.

**Recent additions (Phase 2-3):**
- Self-healing fix engine with 9 error-type strategies and regex-based classification
- Rollback engine with snapshot-based file restoration and procedure persistence
- Tool permission layer with allowlist/denylist, risk-based gating, and audit logging

---

## MODULE INVENTORY

### 1. CORE RUNTIME (`rann_agent/core/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `agent.py` | Legacy Agent: execute/stream, self-healing, tool orchestration | ⚠️ Legacy |
| `runtime.py` | **RuntimeAgent** (Phase 1): state machine, events, budget, verification | ✅ Production |
| `state.py` | `AgentStateMachine`: 16 states, valid transitions, disk persistence | ✅ Production |
| `context.py` | `Context`: message history, tool results, compression | ✅ Production |
| `events.py` | `EventEmitter`: 30+ event types, structured logging, trace export | ✅ Production |
| `event_bus.py` | `EventBus`: pub/sub singleton pattern | ✅ Production |
| `llm_provider.py` | `LLMProvider`: Groq/DeepSeek/OpenAI/Anthropic/Gemini/Ollama/Custom | ✅ Production |
| `cached_provider.py` | `CachedLLMProvider`: wraps LLMProvider with cache | ✅ Production |
| `budget.py` | `BudgetEngine`: token/time/tool/cost/turn tracking with warnings | ✅ Production |
| `approval.py` | `ApprovalSystem`: dangerous operation approval workflow | ✅ Production |
| `verification.py` | `VerificationEngine`: evidence-based proof-of-completion, check factory | ✅ Production |
| `lifecycle.py` | `AgentLifecycle`: context manager for run lifecycle, checkpoint/recovery | ✅ Production |
| `autonomy.py` | `AutonomyGuard`: 6 autonomy levels (0=OBSERVE to 5=HIGH_AUTONOMY) | ✅ Production |
| `idempotency.py` | `OperationTracker`: duplicate execution prevention | ✅ Production |
| `task_contract.py` | `TaskContract`: immutable binding contract (constraints, acceptance criteria) | ✅ Production |
| `evidence.py` | `EvidenceLedger`: persistent evidence records with search/validation | ✅ Production |
| `schemas.py` | Structured output schemas (TaskStatusSchema, PlanSchema, VerificationResultSchema, etc.) | ✅ Production |
| `exceptions.py` | 30+ exception types in hierarchy (LLMError, ToolError, SecurityError, etc.) | ✅ Production |
| `tool_result.py` | `ToolResult` dataclass with factory methods (success_result, error_result, timeout_result) | ✅ Production |
| `rollback_engine.py` | **RollbackEngine**: snapshot-based file rollback, procedure persistence | ✅ Production |
| `tool_permission.py` | **ToolPermissionLayer**: allowlist/denylist, risk gating, audit log | ✅ Production |

**Key architectural insight:** `RuntimeAgent` is the primary agent implementation. It composes `ThinkingEngine`, `SelfCorrection`, `LearningEngine`, `ConversationMemory`, `AgentLifecycle`, `VerificationEngine`, `RollbackEngine`, and `ToolPermissionLayer` into a cohesive autonomous unit.

---

### 2. INTELLIGENCE (`rann_agent/intelligence/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `fix_strategies.py` | **FixStrategy registry**: 9 error-type handlers with pre-compiled regex | ✅ Production |
| `self_improvement.py` | **SelfCorrection + LearningEngine**: generate_fixes(), SQLite error storage | ✅ Production |
| `learning.py` | `LearningEngine`: tracks error patterns, stores resolutions | ✅ Production |
| `codebase_context.py` | Codebase summarization for LLM context | ⚠️ Partial |
| `code_completion.py` | LLM-based code completion | ⚠️ Partial |
| `autonomous_coder.py` | Autonomous coding agent wrapper | ⚠️ Partial |
| `code_intelligence.py` | AST analysis for code understanding | ⚠️ Partial |

---

### 3. TOOLS (`rann_agent/tools/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `registry.py` | `ToolRegistry`: CRUD + get_definitions for function-calling tools | ✅ Production |
| `executor.py` | `ToolExecutor`: async timeout, error handling, result formatting | ✅ Production |
| `real_terminal.py` | `RealTerminalExecutor`: actual shell execution (not simulated) | ✅ Production |
| `filesystem.py` | `FilesystemEngine`: file read/write/search operations | ✅ Production |
| `terminal.py` | Terminal tool definition | ✅ Production |
| `git.py` | Git tool definition (basic operations) | ⚠️ Partial |

---

### 4. ORCHESTRATION (`rann_agent/orchestration/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `command_policy.py` | `CommandPolicy`: risk classification (SAFE/LOW/MEDIUM/HIGH/CRITICAL) | ✅ Production |
| `model_router.py` | `ModelRouter`: task complexity → model selection | ⚠️ Partial |
| `coordinator.py` | `Coordinator`: multi-agent spawning and coordination | ⚠️ Partial |
| `multi_agent.py` | Multi-agent parallel execution | ⚠️ Partial |

---

### 5. STORAGE (`rann_agent/storage/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `database.py` | SQLite wrapper: 12 tables (runs, tasks, events, evidence, sessions, audit) | ✅ Production |
| `pool.py` | `ConnectionPool`: WAL + mmap + threading-safe, 5 connections | ✅ Production |
| `recovery.py` | `CrashRecovery`: WAL checkpoint + re-execution from last turn | ✅ Production |
| `queue.py` | `DurableQueue`: persistent job queue with heartbeat | ✅ Production |
| `locks.py` | `ConcurrencyControl`: workspace/repository/file/database locks (fcntl) | ✅ Production |

---

### 6. MEMORY (`rann_agent/memory/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `manager.py` | `MemoryManager`: coordinates all memory stores | ✅ Production |
| `project_store.py` | `ProjectMemoryStore`: project metadata, dependencies, conventions | ⚠️ Partial |
| `episodic_store.py` | `EpisodicMemoryStore`: goal/action/observation/outcome/lessons | ✅ Production |
| `semantic_store.py` | `SemanticMemoryStore`: key-value facts with similarity search | ⚠️ Partial |
| `conflict.py` | `ConflictResolver`: merge strategy for concurrent memories | ⚠️ Partial |
| `session_search.py` | `SessionSearch`: FTS5 full-text search over sessions | ✅ Production |
| `vector_memory.py` | Vector embedding storage (ChromaDB optional) | 🔄 Experimental |

---

### 7. PLANNING (`rann_agent/planning/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `planner.py` | `Planner`: strategy selection for task decomposition | ⚠️ Partial |
| `recovery.py` | `RecoveryEngine`: structured recovery procedures | ⚠️ Partial |
| `progress.py` | `ProgressEngine`: milestone tracking and completion detection | ⚠️ Partial |
| `semantic_diff.py` | `SemanticDiff`: AST-based change analysis | ⚠️ Partial |

---

### 8. REASONING (`rann_agent/reasoning/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `thought_process.py` | Chain-of-thought reasoning | ⚠️ Partial |
| `self_reflection.py` | Self-reflection and error analysis | ⚠️ Partial |
| `mcts_planner.py` | Monte Carlo Tree Search planner | ❌ Broken |

---

### 9. UTILITIES (`rann_agent/utils/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `cache.py` | `CacheManager`: Redis + in-memory fallback, TTL-based invalidation | ✅ Production |
| `context_window.py` | `ContextWindowManager`: trim/summarize strategy for 200k token window | ✅ Production |
| `http_pool.py` | Shared httpx connection pool (100 conn, keepalive) | ✅ Production |
| `profiler.py` | cProfile hot-path profiler with PySpy support | ✅ Production |

---

### 10. CLI (`rann_agent/cli/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `rann.py` | CLI entry point (Click): run, doctor, status, task, config, memory, audit | ✅ Production |

---

### 11. API / WEB (`rann_agent/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `web_api.py` | FastAPI backend on port 5555: Groq/DeepSeek/OpenAI/Anthropic/Gemini/Ollama/Custom | ✅ Production |
| `api/index.js` | Vercel serverless function: rewrite routing, pathname normalization | ✅ Production |
| `api/chat.js` | Vercel chat handler: SSE streaming for OpenAI-compatible, non-streaming for others | ✅ Production |
| `api/providers.js` | Vercel providers endpoint | ✅ Production |
| `index.html` | Dark-themed AI chat SPA (1688+ lines): chat, sidebar history, settings modal | ✅ Production |
| `dashboard.html` | Dark theme stats dashboard (913 lines): stat cards, quick actions, system checks | ✅ Production |
| `providers.js` | Provider configs for Vercel deployment | ✅ Production |

---

### 12. WEB_APP (`rann_agent/web_app/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `server.py` | FastAPI + WebSocket server for web interface | ⚠️ Partial |

---

### 13. AUTOMATION (`rann_agent/automation/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `browser.py` | Playwright wrapper for browser automation | ⚠️ Partial |
| `cron_scheduler.py` | Cron-based task scheduling | ⚠️ Partial |

---

### 14. MULTIMODAL (`rann_agent/multimodal/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `vision.py` | Image analysis and OCR (Tesseract wrapper) | ⚠️ Partial |
| `voice.py` | Text-to-speech (gTTS wrapper) | ⚠️ Partial |

---

### 15. LEARNING (`rann_agent/learning/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `skill_curator.py` | Skill curation and management | ❌ Broken |

---

### 16. PLUGINS (`rann_agent/plugins/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `manager.py` | Plugin manager for extensibility | ❌ Broken |

---

## TEST INVENTORY

| Suite | Tests | Status |
|-------|-------|--------|
| `tests/unit/test_agent.py` | Core agent tests | ✅ |
| `tests/unit/test_tools.py` | Tool registry and execution | ✅ |
| `tests/unit/test_config.py` | Config management | ✅ |
| `tests/unit/test_runtime.py` | RuntimeAgent state/events/budget | ✅ |
| `tests/unit/test_self_healing.py` | 30 fix strategy tests | ✅ |
| `tests/unit/test_rollback_and_permission.py` | 31 rollback + permission tests | ✅ |
| `tests/benchmarks/` | Performance benchmarks | ✅ |
| **Total** | **283 passed** | ✅ |

---

## CI PIPELINE

| Job | Steps | Status |
|-----|-------|--------|
| Quality | `ruff check .` + `black --check .` | ✅ GREEN |
| Tests | `pytest tests/ -v --cov --cov-fail-under=15` | ✅ GREEN |
| Benchmarks | `pytest benchmarks/ -v` | ✅ GREEN |

**Note:** mypy skipped in CI — ruff + black provide sufficient quality gates. `follow_imports = "skip"` in pyproject.toml avoids numpy stubs issue on Python 3.12.

---

## DEPLOYMENT

- **Vercel SPA**: https://rann-agent-mlp3p2jj6-rann2.vercel.app/
- **Local**: `python web_api.py` → http://localhost:5555
- **CLI**: `rann run "<task>"` or `rann doctor`

---

## KEY ARCHITECTURAL DECISIONS

1. **State Machine**: Explicit 16-state machine (not implicit) with valid transitions enforced
2. **Self-Healing**: Regex-based error classification with 9 pre-compiled strategies, not LLM-dependent
3. **Rollback**: Snapshot-before-modify pattern, procedure persisted to disk for audit
4. **Tool Permissions**: Denylist-first with risk-based approval gating, full audit trail
5. **LLM Providers**: Factory pattern with Groq/DeepSeek/OpenAI/Anthropic/Gemini/Ollama/Custom
6. **Storage**: SQLite with WAL mode + connection pooling + mmap for performance
7. **Caching**: Redis-first with in-memory fallback, TTL-based invalidation
8. **Context**: 200k token window with trim/summarize strategy (system + recent kept)

---

*Generated: 2026-09-07*
*Previous: 2026-09-06*