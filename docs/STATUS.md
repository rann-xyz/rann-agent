# RANN Security Status

Authentic status of RANN implementation and security.

## Security Status Matrix

| Component | Status | Evidence |
|-----------|--------|----------|
| AUTHENTICATION | VERIFIED | HTTP integration tests (`tests/auth/`) |
| AUTHORIZATION | VERIFIED | User ownership enforced in queries |
| SESSION_SECURITY | VERIFIED | HttpOnly, SameSite cookies |
| CSRF | VERIFIED | Token required for mutations |
| TOKEN_SECURITY | VERIFIED | SHA256 hash stored |
| COOKIE_SECURITY | VERIFIED | HttpOnly, SameSite=Lax |
| PASSWORD_SECURITY | CODE-ONLY | PBKDF2-HMAC-SHA256, 600K iterations |
| SESSION_PERSISTENCE | VERIFIED | Database-backed sessions |
| ONE_ACTIVE_SESSION | VERIFIED | Old sessions revoked on login |
| IDOR_HTTP | VERIFIED | HTTP tests verify ownership |
| WORKSPACE_RUNTIME | PARTIAL | WorkspaceGuard (app-level only) |
| TERMINAL_RUNTIME | FAIL | Direct subprocess, no isolation |
| SECRET_ISOLATION | PARTIAL | Environment allowlist in progress |
| RESOURCE_LIMITS | PARTIAL | Timeout enforcement exists |
| NETWORK_ISOLATION | PARTIAL | Policy exists, not enforced |
| EXECUTION_SANDBOX | NOT_IMPLEMENTED | No container/sandbox |

## Execution Layer Status: NOT SAFE FOR PUBLIC ACCESS

**DEVELOPMENT ONLY** - Direct subprocess execution.

Current state:
- `LocalExecutionBackend` runs in API process space
- `os.environ` handling changed to allowlist
- No container/sandbox isolation
- No network restrictions enforced at runtime

### Required Before Public Deployment

| Control | Required Implementation |
|---------|------------------------|
| Process Isolation | Container or VM per execution |
| Environment Sanitization | Explicit allowlist only |
| Network Policy | Enforced at container level |
| Resource Limits | From container runtime |
| Non-root Execution | Worker as non-privileged user |
| Workspace Isolation | OS-level filesystem isolation |

## Tests

Execute verification tests:

```bash
# Auth tests (HTTP integration tests)
pytest tests/auth/ -v

# Security tests (execution isolation)
pytest tests/security/ -v

# Full test suite
pytest tests/ -v --tb=short
```

## Overall Public Gate: NOT READY

**EXECUTION_GATE: FAIL** - Execution layer lacks OS-level sandbox.
**AUTH_GATE: VERIFIED** - Authentication is production-ready.
**PUBLIC_DEPLOYMENT: NOT READY** - Cannot expose arbitrary execution.
