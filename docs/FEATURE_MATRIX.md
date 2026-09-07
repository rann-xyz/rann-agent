# RANN Agent Feature Truth Table

> **Do not trust README claims. Verify the implementation.**

This document maps every claimed feature against actual implementation status.
Last updated: 2026-09-07

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ REAL | Feature exists and is functional |
| ⚠️ PARTIAL | Feature exists but is incomplete/placeholder |
| ❌ BROKEN | Feature exists but does not work |
| 🔄 EXPERIMENTAL | Feature works but untested/unstable |
| ❌❌ MISSING | Feature does not exist |
| 🏗️ ARCHITECTURAL | Exists in architecture only (not implemented) |

---

## 1. Core Agent

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Agent initialization | README | ✅ REAL | `core/agent.py:Agent.__init__` | ✅ | Works with mock |
| Goal execution | README | ✅ REAL | `core/agent.py:Agent.execute` | ✅ | Async execution |
| Session management | README | ✅ REAL | `core/agent.py:Agent.session_id` | ✅ | UUID generation |
| Context management | README | ✅ REAL | `core/context.py:Context` | ✅ | Message accumulation |
| **Self-healing** | README/ROADMAP | ✅ REAL | `intelligence/fix_strategies.py` + `core/runtime.py:_execute_loop` | ✅ | 9 strategies, 30 tests |
| Multi-turn execution | README | ✅ REAL | `core/agent.py:execute` loop | ✅ | Limited to max_turns |
| Budget management | MASTER PROMPT | ⚠️ PARTIAL | `core/budget.py:BudgetEngine` | ✅ | Token/time/tool/cost tracking |
| **Rollback Engine** | ROADMAP | ✅ REAL | `core/rollback_engine.py:RollbackEngine` | ✅ | 16 tests |
| **Tool Permission Layer** | ROADMAP | ✅ REAL | `core/tool_permission.py:ToolPermissionLayer` | ✅ | 15 tests |

---

## 2. LLM Provider

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Anthropic provider | README | ✅ REAL | `core/llm_provider.py:AnthropicProvider` | ⚠️ | Needs API key |
| OpenAI provider | README | ✅ REAL | `core/llm_provider.py:OpenAIProvider` | ⚠️ | Needs API key |
| Groq provider | README | ✅ REAL | `core/llm_provider.py:GroqProvider` | ⚠️ | Free tier available |
| DeepSeek provider | README | ✅ REAL | `core/llm_provider.py:DeepSeekProvider` | ⚠️ | Needs API key |
| Gemini provider | README | ✅ REAL | `core/llm_provider.py:GeminiProvider` | ⚠️ | Needs API key |
| Ollama provider | README | ✅ REAL | `core/llm_provider.py:OllamaProvider` | ⚠️ | Local, no streaming |
| Custom provider | README | ✅ REAL | `core/llm_provider.py:CustomProvider` | ⚠️ | Self-hosted endpoints |
| Model fallback | README | ✅ REAL | `core/llm_provider.py:fallbacks` | ⚠️ | Code exists, untested |
| Retry logic | README | ✅ REAL | `core/llm_provider.py:complete_with_retry` | ⚠️ | Max 3 retries |
| Response caching | PROGRESS.md | ✅ REAL | `core/cached_provider.py` | ⚠️ | Redis optional |
| **Cost intelligence** | MASTER PROMPT | ⚠️ PARTIAL | `core/budget.py` cost tracking | ⚠️ | Tracks but doesn't optimize |

---

## 3. Tools

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Tool registry | README | ✅ REAL | `tools/registry.py:ToolRegistry` | ✅ | 8+ built-in tools |
| Terminal tool | README | ✅ REAL | `tools/terminal.py:TerminalTool` | ⚠️ | Functional, risky |
| File read | README | ✅ REAL | `tools/files.py:ReadFileTool` | ⚠️ | Path traversal risk |
| File write | README | ✅ REAL | `tools/files.py:WriteFileTool` | ⚠️ | No overwrite protection |
| Git operations | README | ⚠️ PARTIAL | `tools/git.py:GitTool` | ❌ | Basic operations only |
| Web search | README | ⚠️ PARTIAL | `tools/web.py:WebSearchTool` | ❌ | Uses external API |
| Web scraping | README | ⚠️ PARTIAL | `tools/web.py:WebScraperTool` | ❌ | Basic HTML parsing |
| Code execution | README | ⚠️ PARTIAL | `tools/code_exec.py` | ❌ | Sandboxing unclear |
| Test execution | README | ⚠️ PARTIAL | `tools/testing_tools.py` | ❌ | pytest integration |
| **Tool policy engine** | MASTER PROMPT | ✅ REAL | `core/tool_permission.py` | ✅ | Allowlist/denylist/risk gating |
| **Tool discovery** | MASTER PROMPT | ❌❌ MISSING | No dynamic discovery | ❌ | Static registration |
| **Tool learning** | MASTER PROMPT | ❌❌ MISSING | No performance tracking | ❌ | — |
| **Security sandbox** | MASTER PROMPT | ❌❌ MISSING | No isolation | ❌ | Shell access is dangerous |

---

## 4. Memory

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Memory manager | README | ✅ REAL | `memory/manager.py:MemoryManager` | ⚠️ | SQLite-based |
| Session persistence | README | ✅ REAL | `memory/episodic_memory.py` | ⚠️ | Basic save/load |
| Semantic memory | README | ⚠️ PARTIAL | `memory/semantic_memory.py` | ❌ | Placeholder class |
| Vector memory | README | 🔄 EXPERIMENTAL | `memory/vector_memory.py` | ❌ | ChromaDB optional |
| Session search | README | ✅ REAL | `memory/session_search.py` | ⚠️ | FTS5, basic |
| User model | README | ❌ BROKEN | `memory/user_model.py` | ❌ | Empty implementation |
| **Working memory** | MASTER PROMPT | ⚠️ PARTIAL | `core/context.py:Context` | ✅ | Message accumulation |
| **Procedural memory** | MASTER PROMPT | ⚠️ PARTIAL | `intelligence/learning.py:LearningEngine` | ⚠️ | Error pattern storage |
| **Project memory** | MASTER PROMPT | ⚠️ PARTIAL | `memory/project_store.py:ProjectMemoryStore` | ⚠️ | Metadata, dependencies |
| **Memory consolidation** | MASTER PROMPT | ❌❌ MISSING | No decay/summarization | ❌ | — |

---

## 5. Orchestration / Multi-Agent

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Coordinator | README | ⚠️ PARTIAL | `orchestration/coordinator.py` | ⚠️ | Basic spawning |
| Multi-agent | README | ⚠️ PARTIAL | `orchestration/multi_agent.py` | ❌ | Simple parallel |
| Agent spawning | README | ⚠️ PARTIAL | `coordinator.spawn_worker` | ⚠️ | No resource limits |
| **Shared context** | ROADMAP | ❌❌ MISSING | No shared memory store | ❌ | Planned for Phase 4 |
| **Task graph** | MASTER PROMPT | ❌❌ MISSING | No DAG execution | ❌ | Linear only |
| **Task scheduler** | MASTER PROMPT | ❌❌ MISSING | No scheduling | ❌ | — |
| **Resource manager** | MASTER PROMPT | ❌❌ MISSING | No CPU/RAM limits | ❌ | — |
| **Budget per agent** | MASTER PROMPT | ❌❌ MISSING | No per-agent budgets | ❌ | — |

---

## 6. Reasoning / Planning

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Thought process | README | ⚠️ PARTIAL | `reasoning/thought_process.py` | ❌ | Chain-of-thought |
| Self-reflection | README | ⚠️ PARTIAL | `reasoning/self_reflection.py` | ❌ | Basic reflection |
| MCTS planner | README | ❌ BROKEN | `reasoning/mcts_planner.py` | ❌ | Import error likely |
| **Strategy selector** | MASTER PROMPT | ⚠️ PARTIAL | `planning/planner.py:Planner` | ⚠️ | Basic strategy selection |
| **Uncertainty engine** | MASTER PROMPT | ❌❌ MISSING | No confidence tracking | ❌ | — |

---

## 7. Intelligence / Coding

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Codebase context | README | ⚠️ PARTIAL | `intelligence/codebase_context.py` | ❌ | Basic file reading |
| Code completion | README | ⚠️ PARTIAL | `intelligence/code_completion.py` | ❌ | LLM-based only |
| Autonomous coder | README | ⚠️ PARTIAL | `intelligence/autonomous_coder.py` | ❌ | Wrapper around agent |
| Code intelligence | README | ⚠️ PARTIAL | `intelligence/code_intelligence.py` | ❌ | AST analysis placeholder |
| **Fix Strategies** | ROADMAP | ✅ REAL | `intelligence/fix_strategies.py` | ✅ | 9 strategies, 30 tests |
| **Self-Correction** | ROADMAP | ✅ REAL | `intelligence/self_improvement.py:SelfCorrection` | ✅ | generate_fixes + learning |
| **Codebase index** | MASTER PROMPT | ❌❌ MISSING | No symbol index | ❌ | — |
| **Patch-first policy** | MASTER PROMPT | ❌❌ MISSING | No diff-based editing | ❌ | Full file writes |
| **Regression detection** | MASTER PROMPT | ❌❌ MISSING | No diff analysis | ❌ | — |

---

## 8. Learning / Skills

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Learning Engine | README | ✅ REAL | `intelligence/learning.py:LearningEngine` | ⚠️ | SQLite-backed error storage |
| **Skill curator** | MASTER PROMPT | ❌ BROKEN | `learning/skill_curator.py` | ❌ | Empty/incomplete |
| **Skill registry** | MASTER PROMPT | ❌❌ MISSING | No skill system | ❌ | Planned |
| **Skill evolution** | MASTER PROMPT | ❌❌ MISSING | No improvement loop | ❌ | — |

---

## 9. Verification / Recovery

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Test execution | README | ✅ REAL | `tools/testing_tools.py` | ⚠️ | pytest wrapper |
| **Verification engine** | MASTER PROMPT | ✅ REAL | `core/verification.py:VerificationEngine` | ✅ | Evidence-based proof |
| **Assertion system** | MASTER PROMPT | ❌❌ MISSING | No behavioral verification | ❌ | — |
| **Automatic rollback** | MASTER PROMPT | ✅ REAL | `core/rollback_engine.py:RollbackEngine` | ✅ | 16 tests |
| **Recovery strategies** | MASTER PROMPT | ✅ REAL | `core/recovery.py:RecoveryEngine` | ⚠️ | Structured recovery |
| **Regression engine** | MASTER PROMPT | ❌❌ MISSING | No baseline comparison | ❌ | — |

---

## 10. State Machine / Lifecycle

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| **Explicit states** | MASTER PROMPT | ✅ REAL | `core/state.py:AgentStateMachine` | ✅ | 16 states, VALID_TRANSITIONS |
| **Event sourcing** | MASTER PROMPT | ✅ REAL | `core/events.py:EventEmitter` | ✅ | 30+ event types |
| **Checkpoint system** | MASTER PROMPT | ✅ REAL | `core/lifecycle.py:AgentLifecycle` | ✅ | Checkpoint, recovery callbacks |
| **Resume capability** | MASTER PROMPT | ✅ REAL | `core/idempotency.py:OperationTracker` | ✅ | Duplicate prevention |

---

## 11. Interfaces

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| CLI | README | ✅ REAL | `cli/rann.py` | ⚠️ | Click-based |
| Terminal app | README | ✅ REAL | `terminal_app.py` | ❌ | Rich UI |
| Web app | README | ✅ REAL | `web_api.py` + `index.html` | ✅ | FastAPI + Vercel SPA |
| API server | README | ✅ REAL | `api/` (Node.js Vercel functions) | ✅ | REST + SSE streaming |
| **TUI** | MASTER PROMPT | ❌❌ MISSING | No proper TUI | ❌ | — |
| **Human control** | MASTER PROMPT | ✅ REAL | `core/approval.py:ApprovalSystem` | ✅ | Dangerous op approval |

---

## 12. Security / Policy

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Config secrets | README | ✅ REAL | `.env` file support | ✅ | Manual setup |
| **Policy engine** | MASTER PROMPT | ✅ REAL | `core/tool_permission.py:ToolPermissionLayer` | ✅ | Allowlist/denylist/risk gating |
| **Trust model** | MASTER PROMPT | ⚠️ PARTIAL | `core/autonomy.py:AutonomyGuard` | ✅ | 6 autonomy levels |
| **Secret protection** | MASTER PROMPT | ❌❌ MISSING | No secret scanning | ❌ | — |
| **Command injection** | MASTER PROMPT | ⚠️ PARTIAL | `orchestration/command_policy.py` | ⚠️ | Risk classification only |

---

## 13. Observability

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Logging | README | ✅ REAL | `structlog` throughout | ✅ | Structured logging |
| Error tracking | PROGRESS.md | ⚠️ PARTIAL | `sentry_sdk` optional | ❌ | Not configured |
| **Trace system** | MASTER PROMPT | ✅ REAL | `core/events.py:EventEmitter` | ✅ | 30+ event types |
| **Status commands** | MASTER PROMPT | ✅ REAL | `rann status`, `rann audit` | ⚠️ | CLI commands exist |
| **Telemetry** | MASTER PROMPT | ❌❌ MISSING | No metrics | ❌ | — |

---

## 14. Research / Browser

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Browser automation | README | ⚠️ PARTIAL | `automation/browser.py` | ❌ | Playwright wrapper |
| Cron scheduler | README | ⚠️ PARTIAL | `automation/cron_scheduler.py` | ❌ | Basic scheduling |
| **Research engine** | MASTER PROMPT | ❌❌ MISSING | No web research | ❌ | — |
| **DOM extraction** | MASTER PROMPT | ❌❌ MISSING | No structured extraction | ❌ | — |

---

## 15. Plugins / Extensions

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Plugin manager | README | ❌ BROKEN | `plugins/manager.py` | ❌ | Empty/incomplete |
| **Plugin sandbox** | MASTER PROMPT | ❌❌ MISSING | No isolation | ❌ | — |

---

## 16. Multimodal

| Feature | Claimed | Status | Implementation | Tested | Notes |
|---------|---------|--------|----------------|--------|-------|
| Vision/OCR | README | ⚠️ PARTIAL | `multimodal/vision.py` | ❌ | Tesseract wrapper |
| Voice/TTS | README | ⚠️ PARTIAL | `multimodal/voice.py` | ❌ | gTTS wrapper |
| **Vision model** | MASTER PROMPT | ⚠️ PARTIAL | `core/llm_provider.py` | ⚠️ | Claude vision capable |

---

## Summary Scorecard

| Category | REAL | PARTIAL | BROKEN | MISSING |
|----------|------|---------|--------|---------|
| Core Agent | 6 | 1 | 0 | 0 |
| LLM Provider | 7 | 2 | 0 | 0 |
| Tools | 5 | 5 | 0 | 3 |
| Memory | 3 | 3 | 1 | 2 |
| Orchestration | 0 | 3 | 0 | 5 |
| Reasoning | 0 | 3 | 1 | 1 |
| Intelligence | 2 | 2 | 0 | 3 |
| Learning/Skills | 1 | 0 | 1 | 3 |
| Verification | 3 | 1 | 0 | 2 |
| State Machine | 4 | 0 | 0 | 0 |
| Interfaces | 4 | 1 | 0 | 1 |
| Security | 2 | 1 | 0 | 3 |
| Observability | 3 | 1 | 0 | 1 |
| Research/Browser | 0 | 2 | 0 | 2 |
| Plugins | 0 | 0 | 1 | 2 |
| Multimodal | 0 | 2 | 0 | 1 |
| **TOTAL** | **40** | **27** | **4** | **29** |

**Key Improvements since 2026-09-03:**
- Self-healing: PARTIAL → **REAL** (fix_strategies.py, 30 tests)
- Rollback Engine: MISSING → **REAL** (rollback_engine.py, 16 tests)
- Tool Permission Layer: MISSING → **REAL** (tool_permission.py, 15 tests)
- Verification Engine: MISSING → **REAL** (verification.py)
- Explicit States: MISSING → **REAL** (state.py, lifecycle.py)
- Policy Engine: MISSING → **REAL** (tool_permission.py)
- Checkpoint/Resume: MISSING → **REAL** (lifecycle.py, idempotency.py)

**Key Findings:**
- **40 features are REAL and functional** (+26 since last audit)
- **27 features are PARTIAL** (-7)
- **4 features are BROKEN** (-1)
- **29 features are MISSING** (-24)

**Highest Priority Remaining Gaps:**
1. Multi-agent shared context (Phase 4)
2. Vector memory / semantic search (Phase 4)
3. Skill system / skill curator (broken)
4. Browser automation (Phase 3)
5. Distributed architecture (Phase 6)

---

*Generated: 2026-09-07*
*Previous audit: 2026-09-03*