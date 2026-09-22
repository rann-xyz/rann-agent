# RANN Agent Status Report

**Last Updated:** 2026-09-21
**Purpose:** Authoritative status of security components for RANN Agent public deployment

---

## Security Status Matrix

| Component | Status | Verified By |
|-----------|--------|-------------|
| AUTHENTICATION | ✅ PASS | HTTP tests |
| AUTHORIZATION | ✅ PASS | Code review |
| SESSION_SECURITY | ✅ PASS | HTTP tests |
| CSRF | ❌ FAIL | Not implemented |
| TOKEN_SECURITY | ✅ PASS | Code review |
| COOKIE_SECURITY | ✅ PASS | Config exists |
| PASSWORD_SECURITY | ✅ PASS | PBKDF2-HMAC-SHA256, 600K iterations |
| IP_HMAC | ✅ PASS | HMAC-SHA256 implementation |
| TRUSTED_PROXY | ❌ FAIL | Not configured |
| CORS | ✅ PASS | Explicit origins |
| RATE_LIMITING | ⚠️ PROCESS_LOCAL | In-memory only |
| HTTP_AUTHENTICATION | ✅ PASS | HTTP integration tests |
| HTTP_AUTHORIZATION | ✅ PASS | HTTP tests |
| IDOR_HTTP | ✅ PASS | HTTP tests |
| EVIDENCE_OWNERSHIP | ⚠️ NOT_VERIFIED | No public evidence endpoint |
| WORKSPACE_RUNTIME | ⚠️ PARTIAL | WorkspaceGuard (app-level only) |
| TERMINAL_RUNTIME | ❌ FAIL | Execution in API process |
| SECRET_ISOLATION | ❌ FAIL | Env vars inherited by subprocess |
| RESOURCE_LIMITS | ❌ NOT_IMPLEMENTED | No CPU/memory/time limits |
| NETWORK_ISOLATION | ❌ NOT_IMPLEMENTED | No restrictions |
| EXECUTION_SANDBOX | ❌ FAIL | Not implemented |

---

## Execution Layer Status: ⚠️ NOT SAFE FOR PUBLIC ACCESS

**DO NOT expose arbitrary agent execution publicly.**

Current state:
- `RuntimeAgent.execute()` runs in the FastAPI process
- Subprocesses inherit the full host environment
- Database secrets, API keys, and credentials are exposed to executed code
- No resource limits prevent resource exhaustion
- No network restrictions are enforced
- No OS-level container or process isolation

The `WorkspaceGuard` provides application-level path validation but provides NO isolation from:
- Arbitrary subprocess filesystem access
- Shell command escapes
- Symlink attacks
- Memory/CPU exhaustion

---

## Required Work Before Public Execution

| Item | Requirement |
|------|-------------|
| Execution Isolation | Separate process/container from API |
| Environment Sanitization | Explicit variable allowlist, no DB_SECRET propagation |
| Resource Limits | Timeout, CPU, memory, disk limits |
| Network Policy | Disabled by default |
| Session Persistence Verification | Restart test with HTTP |
| One Active Session | HTTP verified |
| CSRF Protection | Browser mutations protected |

---

## Vercel Architecture

**Vercel = Control Plane Only**

DO NOT attempt to run arbitrary execution on Vercel. Vercel serverless functions:
- Block shell command execution
- Timeout at 10-60 seconds
- Have ephemeral filesystem

External worker service required for:
- Terminal execution
- Long-running tasks
- Persistent workspace

See `docs/vercel_deployment_guide.md` for architecture diagram.

---

## Overall Public Gate: ❌ NOT READY

**Reason:** Execution sandbox and secret isolation are not implemented. The authentication layer is complete but does not make arbitrary execution safe.

### Breakdown:

- **Auth Gate:** ✅ PASS
- **Execution Gate:** ❌ FAIL
  - No process isolation
  - No secret isolation
  - No resource limits
  - No sandbox
- **Overall:** ❌ NOT READY

---

## Test Commands

```bash
# Run all tests
pytest tests/ -v

# Auth tests
pytest tests/auth/ -v

# Verify session persistence (manual)
# 1. POST /auth/login → capture cookie
# 2. Kill server process
# 3. Start server
# 4. GET /auth/session with cookie → must work

# Verify one active session
# 1. Login as user
# 2. Login again
# 3. Old cookie should be invalid
```

---

## Documentation

For detailed architecture and deployment requirements, see:

- `README.md` - Project overview
- `SECURITY.md` - Security model (if exists)
- `ARCHITECTURE_REPORT.md` - Technical architecture
- `rann-agent/docs/execution_security_guidelines.md` - Future requirements

DO NOT use "production-ready", "fully sandboxed", or "secure execution" in any documentation until sandbox is implemented and verified.