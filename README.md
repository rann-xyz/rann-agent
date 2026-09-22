# RANN Agent V3

[![CI](https://github.com/rann-xyz/rann-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/rann-xyz/rann-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **THE MODEL GENERATES DECISIONS. RANN CONTROLS EXECUTION.**

Autonomous AI agent system with 16-state machine, structured memory, tool orchestration, and multi-provider LLM support.

---

## ⚠️ CRITICAL: Execution Security Status

**RANN Agent CANNOT safely execute arbitrary code in public deployment.**

The current architecture lacks:
- Execution sandbox (code runs in API process)
- Secret isolation (environment variables inherited)
- Resource limits (CPU, memory, disk, timeout)
- Network isolation

**DO NOT expose arbitrary terminal execution publicly without implementing the required sandboxing.**

See `docs/STATUS.md` for detailed security status.

---

## Status

```
Authentication:    ✅ Implemented & Tested
Authorization:     ✅ Implemented & Tested
Session Security:  ✅ Database-backed sessions
CSRF Protection:   ❌ NOT IMPLEMENTED
Execution Safety:  ❌ NOT SAFE FOR PUBLIC ACCESS
```

**Authentication layer is production-ready.
Execution layer requires additional sandboxing for public use.**

---

## Features

### 16-State Agent State Machine
```
QUEUED → ANALYZING → CONTEXT_READY → PLANNING → WAITING_POLICY → EXECUTING → VERIFYING → ACCEPTANCE_CHECK → LEARNING → COMPLETED
                                          ↓            ↓              ↓            ↓
                                     BLOCKED      FAILED        BLOCKED      FAILED
                                                                       ↓
                                                             RECOVERING → TIMED_OUT → CANCELLED
```

### Core Components
- **RuntimeAgent** — Budget + lifecycle-driven execution loop
- **AgentLifecycle** — State machine + event emission + checkpointing  
- **ToolRegistry** — OpenAI function-calling compatible tools
- **WorkspaceGuard** — Path traversal prevention (application-level)
- **CommandPolicy** — Risk classification (SAFE/LOW/MEDIUM/HIGH/CRITICAL)

---

## Installation

```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
./setup.sh
```

---

## Quick Start

```bash
# System check
rann doctor

# Run a task
rann run "create a hello world file"

# Dry run (no execution)
rann run "fix the bug" --dry-run
```

---

## Web API (Authentication Enabled)

```bash
python -m rann_agent.web.app
```

### API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/auth/register` | Register new user | No |
| `POST` | `/auth/login` | Login | No |
| `POST` | `/auth/logout` | Logout | Yes (CSRF required) |
| `GET` | `/auth/session` | Validate session | Yes |
| `POST` | `/api/tasks` | Create task | Yes |
| `GET` | `/api/health` | Health check | No |

**Authentication implemented with:**
- PBKDF2-HMAC-SHA256 password hashing (600K iterations)
- Database-backed sessions with hashed tokens
- HttpOnly, Secure, SameSite=Lax cookies
- CSRF protection for authenticated mutations

---

## Vercel Deployment

**Control plane only.** See `docs/vercel_deployment_guide.md` for architecture.

Vercel components:
- Frontend UI
- Authentication endpoints
- Run creation (enqueue only, no blocking execution)
- Session management

**NOT POSSIBLE on Vercel:**
- Arbitrary terminal execution (blocked by Vercel)
- Long-running tasks (timeout limits)
- Direct SQLite WAL (ephemeral filesystem)

External worker required for execution.

---

## Security Status

| Component | Status |
|-----------|--------|
| Authentication | ✅ Implemented & Tested |
| Authorization | ✅ Implemented |
| Session Persistence | ⚠️ Partial (needs restart verification) |
| CSRF Protection | ❌ Not implemented |
| Trusted Proxy | ❌ Not implemented |
| Execution Sandbox | ❌ Not implemented |
| Secret Isolation | ❌ Not implemented |
| Resource Limits | ❌ Not implemented |

**DO NOT expose arbitrary execution publicly.**

Detailed status: `docs/STATUS.md`

---

## Architecture Note

**WorkspaceGuard ≠ OS Sandbox**

WorkspaceGuard provides application-level path validation to prevent `../` escapes within the tools RANN controls. It does NOT:
- Prevent arbitrary subprocess filesystem access
- Provide OS-level isolation
- Stop shell commands from escaping
- Limit CPU, memory, or disk usage

For public deployment, external sandbox infrastructure is required for execution safety.