# RANN Agent Architecture Report

**Repository:** `/home/userland/rann-agent`
**Generated:** 2026-09-06
**Purpose:** Comprehensive inventory driving full autonomous agent implementation

---

## EXECUTIVE SUMMARY

RANN Agent is a Python-based autonomous AI agent framework with **substantial core infrastructure already implemented**. It has two parallel agent implementations:
- `Agent` (legacy) — basic single-turn execution loop
- `RuntimeAgent` (Phase 1) — full state-machine-driven agent with events, budget, verification

The codebase is well-structured with clear separation across: core runtime, tools, orchestration, memory, intelligence, reasoning, and utilities.

---

## MODULE INVENTORY

### 1. CORE RUNTIME (`rann_agent/core/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `agent.py` | Legacy Agent: execute/stream, self-healing, tool orchestration | ⚠️ Legacy |
| `runtime.py` | **RuntimeAgent** (Phase 1): state machine, events, budget, verification | ✅ Production |
| `state.py` | `AgentStateMachine`: 14 states, valid transitions, disk persistence for resume | ✅ Production |
| `context.py` | `Context`: message history, tool results, compression | ✅ Production |
| `events.py` | `EventEmitter`: 25+ event types, structured logging, trace export | ✅ Production |
| `event_bus.py` | `EventBus`: pub/sub singleton pattern | ✅ Production |
| `llm_provider.py` | `LLMProvider`: Anthropic/OpenAI/Ollama/Custom with retry, fallback | ✅ Production |
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

**Key architectural insight:** `RuntimeAgent` is the primary agent implementation. It composes `ThinkingEngine`, `SelfCorrection`, `LearningEngine`, `ConversationMemory`, `AgentLifecycle`, and `VerificationEngine` into a cohesive unit.

---

### 2. TOOLS (`rann_agent/tools/`)

#### 2.1 Tool Infrastructure

| File | Responsibility | Status |
|------|---------------|--------|
| `registry.py` | `Tool` ABC, `ToolRegistry`: tool execution, OpenAI function-calling definitions | ✅ Production |
| `tool_registry.py` | Full CRUD registry with `ToolMetadata`, persistence, usage stats | ✅ Production |
| `executor.py` | `ToolExecutor`: isolation, timeout, rate limiting, sanitized logging | ✅ Production |
| `tool_factory.py` | Dynamic tool creation from Python code at runtime | ✅ Production |

#### 2.2 Built-in Tools

| Tool | File | Capabilities | Status |
|------|------|-------------|--------|
| `terminal` | `terminal.py` | Shell command execution, background processes, dangerous command detection | ✅ Production |
| `read_file` | `files.py` | Line-offset file reading with pagination | ✅ Production |
| `write_file` | `files.py` | File write with parent dir creation | ✅ Production |
| `search_files` | `files.py` | Content/filename grep via subprocess | ✅ Production |
| `web_search` | `web.py` | Pluggable providers: DuckDuckGo, Brave, SearXNG, Tavily, GoogleCSE | ✅ Production |
| `web_extract` | `web.py` | Pluggable extractors: aiohttp, trafilatura, playwright | ✅ Production |
| `code_exec` | `code_exec.py` | Python/JS/bash in temp files with timeout | ✅ Production |
| `git` | `git.py` | status/add/commit/push/pull/diff/log/branch | ✅ Production |

#### 2.3 Advanced Tools (not yet inspected)
- `advanced_tools.py`, `testing_tools.py`, `memory_tool.py`, `intelligence_tools.py`
- `automation_tool.py`, `reasoning_tool.py`, `orchestration_tool.py`, `multimodal_tool.py`
- `discovery.py`, `real_terminal.py`, `filesystem.py`

---

### 3. ORCHESTRATION (`rann_agent/orchestration/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `coordinator.py` | `Coordinator`: spawns sub-agents, parallel/graph execution | ✅ Production |
| `multi_agent.py` | `AgentOrchestrator`: spawn/assign/delegate with idle agent tracking | ✅ Production |
| `task_graph.py` | `TaskGraph`: explicit DAG with dependencies, priority, retry, progress tracking | ✅ Production |
| `model_router.py` | (not inspected) | 🔶 TODO |
| `tool_policy.py` | (not inspected) | 🔶 TODO |
| `command_policy.py` | (not inspected) | 🔶 TODO |

---

### 4. MEMORY (`rann_agent/memory/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `manager.py` | `MemoryManager`: SQLite sessions, error resolutions, learned patterns | ✅ Production |
| `semantic_memory.py` | `SemanticMemory`: key-value facts, concepts, relationships | ✅ Production |
| `episodic_memory.py` | `EpisodicMemory`: chronological episodes with trim | ✅ Production |
| `working.py` | `WorkingMemory`: LRU, TTL, access tracking, key-value store | ✅ Production |
| `vector_memory.py` | (not inspected) | 🔶 TODO |
| `session_search.py` | (not inspected) | 🔶 TODO |
| `user_model.py` | (not inspected) | 🔶 TODO |
| `episodic_store.py` | (not inspected) | 🔶 TODO |
| `procedural.py` | (not inspected) | 🔶 TODO |
| `conflict.py` | (not inspected) | 🔶 TODO |
| `project_store.py` | (not inspected) | 🔶 TODO |
| `context_trim.py` | (not inspected) | 🔶 TODO |
| `semantic_store.py` | (not inspected) | 🔶 TODO |

---

### 5. INTELLIGENCE (`rann_agent/intelligence/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `enhanced_brain.py` | `ThinkingEngine` (7-phase think loop), `ResponseFormatter`, `ContextManager` | ✅ Production |
| `self_improvement.py` | `SelfCorrection`, `LearningEngine`, `ConversationMemory` | ✅ Production |
| `code_intelligence.py` | (not inspected) | 🔶 TODO |
| `codebase_context.py` | (not inspected) | 🔶 TODO |
| `code_completion.py` | (not inspected) | 🔶 TODO |
| `autonomous_coder.py` | (not inspected) | 🔶 TODO |
| `task_decomposer.py` | (not inspected) | 🔶 TODO |

---

### 6. REASONING (`rann_agent/reasoning/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `thought_process.py` | `ChainOfThought`, `TreeOfThought` with `ThoughtNode` | ✅ Production |
| `mcts_planner.py` | `MCTSPlanner`: Monte Carlo Tree Search with UCB1 | ✅ Production |
| `self_reflection.py` | (not inspected) | 🔶 TODO |

---

### 7. UTILITIES (`rann_agent/utils/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `cache.py` | `CacheManager`: Redis + in-memory fallback for LLM/tool results | ✅ Production |
| `context_window.py` | (not inspected) | 🔶 TODO |
| `profiler.py` | (not inspected) | 🔶 TODO |
| `http_pool.py` | (not inspected) | 🔶 TODO |

---

### 8. PLUGINS (`rann_agent/plugins/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `manager.py` | `PluginManager`: dynamic loading, hook registration/execution | ✅ Production |

---

### 9. OTHER

| Component | Path | Status |
|-----------|------|--------|
| API server | `rann_agent/api/server.py` | 🔶 TODO |
| CLI | `rann_agent/cli/` | 🔶 TODO |
| Automation | `rann_agent/automation/` | 🔶 TODO |
| Multimodal | `rann_agent/multimodal/` | 🔶 TODO |

---

## EXISTING TOOL ABSTRACTIONS

### Tool Base Class
```python
class Tool(ABC):
    name: str
    description: str
    parameters: Dict[str, Any]  # OpenAPI schema format
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]: ...
```

### Tool Result Standard
```python
ToolResult(tool, success, output, error, metadata).to_dict()
```

### LLM Function Calling
`ToolRegistry.get_definitions()` returns OpenAI-compatible tool definitions automatically.

### Pluggable Provider Pattern
Web tools use factory pattern: `get_search_provider(name)` / `get_extract_provider(name)`.

---

## SPEC MAPPING: What's Already Implemented

| Spec Section | Feature | Implementation | Status |
|-------------|---------|----------------|--------|
| Section 4 | Task Contract | `task_contract.py`: TaskContract with constraints, acceptance criteria, prohibited actions | ✅ |
| Section 5 | State Machine | `state.py`: 14 states, VALID_TRANSITIONS, disk persistence | ✅ |
| Section 6 | Tool Result | `tool_result.py`: ToolResult dataclass with factories | ✅ |
| Section 8 | Events | `events.py`: 25+ event types, structured logging | ✅ |
| Section 12 | Evidence Ledger | `evidence.py`: EvidenceLedger with search, validation, persistence | ✅ |
| Section 14 | Budget Engine | `budget.py`: BudgetEngine with 5 budget types + warnings | ✅ |
| Section 17 | Tool Executor | `executor.py`: timeout, rate limiting, sanitized params | ✅ |
| Section 19 | Idempotency | `idempotency.py`: OperationTracker | ✅ |
| Section 20 | Approval | `approval.py`: ApprovalSystem for dangerous ops | ✅ |
| Section 23-24 | Verification | `verification.py`: VerificationEngine with check factory | ✅ |
| Section 25 | Working Memory | `working.py`: LRU, TTL, access tracking | ✅ |
| Section 48 | Event Bus | `event_bus.py`: pub/sub singleton | ✅ |
| Section 51 | Autonomy Levels | `autonomy.py`: 6 levels with ACTION_REQUIREMENTS map | ✅ |
| Thinking before executing | Enhanced Brain | `enhanced_brain.py`: 7-phase ThinkingEngine | ✅ |
| Self-correction | Self-improvement | `self_improvement.py`: SelfCorrection, LearningEngine | ✅ |
| Multi-agent | Orchestration | `coordinator.py`, `multi_agent.py`, `task_graph.py` | ✅ |
| Chain/Tree of Thought | Reasoning | `thought_process.py`: ChainOfThought, TreeOfThought | ✅ |
| MCTS Planning | Strategic planning | `mcts_planner.py`: MCTSPlanner with UCB1 | ✅ |
| Dynamic tool creation | Tool factory | `tool_factory.py`: create tools from code | ✅ |
| Web search | Pluggable providers | `web.py`: 5 search + 3 extract providers | ✅ |
| LLM caching | Cache layer | `cached_provider.py`, `cache.py`: Redis + memory | ✅ |
| Config management | Pydantic + YAML | `config.py`: pydantic models, env vars, YAML loading | ✅ |

---

## WHAT NEEDS TO BE BUILT FROM SCRATCH

### High Priority

1. **Vector Memory Integration**
   - Integrate ChromaDB or Pinecone
   - Embed session history for semantic search
   - Auto-retrieve relevant past sessions (RAG)
   - *Blocker:* `memory/vector_memory.py` not inspected

2. **Advanced Self-Healing ML**
   - Pattern recognition classifier for error types
   - Fix strategy library (version-specific, platform-specific)
   - Success rate tracking per fix type
   - *Blocker:* Currently uses simple keyword matching

3. **Agent Specialization**
   - Backend agent (APIs, DBs, servers)
   - Frontend agent (React, Vue, HTML/CSS)
   - DevOps agent (Docker, K8s, CI/CD)
   - Data agent (pandas, analysis, ML)
   - Roadmap 2.2

4. **Smart Task Decomposition**
   - LLM-powered task splitting
   - Dependency graph generation from task analysis
   - Critical path analysis
   - *Blocker:* Currently uses static step generation

5. **Agent Communication Protocol**
   - Structured message passing between agents
   - Shared context store
   - Conflict resolution

### Medium Priority

6. **Browser Automation**
   - Playwright integration (already in web.py as provider)
   - Headless browser tool with screenshot
   - Form filling, interaction
   - Session recording

7. **Vision & Multi-Modal**
   - Image analysis tool
   - Screenshot debugging
   - UI/UX review

8. **Model Router**
   - Route tasks to optimal model based on task type
   - Cost/latency/quality tradeoffs

9. **Tool Policy & Command Policy**
   - Policy enforcement layer
   - Risk assessment before execution

10. **Self-Reflection Module**
    - Deeper self-analysis after task completion
    - `reasoning/self_reflection.py` not inspected

### Lower Priority (Roadmap Phase 3+)

11. **Code Intelligence**
    - `intelligence/code_intelligence.py` not inspected
    - `codebase_context.py` not inspected
    - `code_completion.py` not inspected

12. **Procedural Memory**
    - `memory/procedural.py` not inspected

---

## KEY GAPS ANALYSIS

### 1. No Working Vector Search
The `MemoryManager` uses simple SQL LIKE queries for context retrieval. Semantic similarity search requires vector embeddings.

### 2. Self-Healing is Rudimentary
`_generate_fixes()` in `agent.py` returns a stub. The `LearningEngine` stores solutions but doesn't learn from failures in a sophisticated way.

### 3. Multi-Agent Has No Shared Context
Sub-agents spawned by `Coordinator` have `memory=False`. There's no protocol for inter-agent communication.

### 4. Task Decomposition is Static
`ThinkingEngine._generate_steps()` uses keyword matching, not LLM-powered analysis.

### 5. No Rollback Implementation
`EvidenceLedger` and `TaskContract` define rollback plans but no execution engine.

### 6. Tool Policy is Minimal
`approval.py` checks dangerous commands but there's no `tool_policy.py` or `command_policy.py` implementation.

---

## DEPENDENCY GRAPH (Key)

```
RuntimeAgent
├── ThinkingEngine (intelligence)
├── SelfCorrection + LearningEngine (self-improvement)
├── AgentLifecycle
│   ├── AgentStateMachine (state)
│   ├── EventEmitter (events)
│   └── BudgetEngine (budget)
├── VerificationEngine (verification)
├── LLMProvider
│   └── [Anthropic|OpenAI|Ollama|Custom]Provider
├── ToolRegistry
│   └── [Terminal|File|Web|CodeExec|Git]Tool
├── MemoryManager
│   └── SQLite (sessions, error_resolutions, patterns)
├── Coordinator (orchestration)
│   └── AgentOrchestrator + TaskGraph
└── CacheManager
    └── [Redis|In-Memory]
```

---

## CONFIGURATION

Default config (`config.yaml.example`):
- LLM: `xkiro` provider, `minimax/minimax-m2.7-highspeed:free` model
- Tools enabled: terminal, read_file, write_file, search_files, web_search, web_extract, code_exec, git
- Self-healing: enabled with 3 max retries
- Orchestration: enabled, max 5 concurrent agents, max depth 3
- Memory: SQLite persistence
- Advanced: parallel_tools=true, caching enabled

---

## TEST STATUS

From `ROADMAP.md`:
- 93 tests passing (44 unit + 8 integration + 41 core runtime)
- Coverage config: `--cov-fail-under=15`

---

## RECOMMENDED IMPLEMENTATION ORDER

1. **Inspect remaining files** — vector_memory, session_search, code_intelligence, self_reflection, advanced_tools, etc.
2. **Implement Vector Memory** — ChromaDB integration for semantic search
3. **Build Task Decomposer** — LLM-powered task splitting
4. **Enhance Self-Healing** — Pattern recognition, fix strategy library
5. **Multi-Agent Context Protocol** — Shared context between agents
6. **Browser Automation Tool** — Wrap Playwright provider into full tool
7. **Vision Tool** — Image analysis with the multimodal module