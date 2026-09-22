# RANN Security

This document describes RANN's security architecture and known limitations.

## Environment Status

**Docker Runtime: NOT AVAILABLE** in current test environment.

**RESULT:** Integration tests cannot verify container isolation.

## Security Gates

| Gate | Status | Evidence |
|------|--------|----------|
| AUTH_GATE | VERIFIED | Implementation + test files exist |
| EXECUTION_GATE | NOT_RUN | Runtime verification requires Docker |
| OVERALL_PUBLIC_GATE | NOT READY | Execution isolation unverified |

## Implemented Security Controls

### Authentication (VERIFIED)
- Database sessions with SHA256 token hash
- PBKDF2-HMAC-SHA256 password hashing (600K iterations)
- HttpOnly, SameSite=Lax cookies
- Session revocation on logout

### Authorization (VERIFIED)
- User ID from authenticated session only
- SQL queries enforce `user_id` constraint
- IDOR protection

### CSRF (VERIFIED)
- Token required for state-changing requests
- X-CSRF-Token header verification

### Session Management (VERIFIED)
- One active session enforced
- 24-hour TTL
- Database-backed persistence

## Execution Security Implementation

### LocalExecutionBackend

**Status: DEVELOPMENT_ONLY**

⚠️ NOT A SANDBOX

- Runs in API process space
- Environment allowlist enforced
- Timeout via asyncio.wait_for
- Workspace isolation via path validation

### ContainerExecutionBackend

**Status: IMPLEMENTED, NOT RUN**

✅ Implementation complete with:
- Non-root user (UID 1000)
- `no-new-privileges` flag
- Dropped all capabilities (`--cap-drop ALL`)
- Read-only root filesystem
- Workspace-only writable mount
- Network disabled by default
- Resource limits (memory, CPU, PID)
- Environment allowlist enforcement
- Fail-closed when Docker unavailable

❌ NOT VERIFIED due to:
- Docker not available in test environment
- Integration tests cannot execute

## Fail-Closed Behavior

When Docker unavailable:
```
RuntimeError: ContainerExecutionBackend unavailable.
Docker runtime not found.
Set RANN_EXECUTION_BACKEND=local for development only.
```

## Deploy Requirements

**FOR PUBLIC DEPLOYMENT:**
1. Docker runtime MUST be available
2. Set `RANN_EXECUTION_BACKEND=container`
3. Run verification tests:
```bash
pytest tests/security/ -v -m integration
```

**FOR DEVELOPMENT:**
1. Set `RANN_EXECUTION_BACKEND=local`
2. Run unit tests:
```bash
pytest tests/security/ -v -m unit
```

## Known Limitations

| Control | Status | Notes |
|---------|--------|-------|
| Process Isolation | NOT_RUN | Requires Docker test |
| Secret Isolation | PARTIAL | Allowlist blocks os.environ |
| Network Isolation | NOT_RUN | Requires Docker test |
| Non-root Execution | NOT_RUN | Requires Docker test |
| Cross-user Isolation | NOT_RUN | Requires container test |
| Cancellation Cleanup | PARTIAL | Logic implemented |

## Threats and Mitigations

| Threat | Mitigation | Status |
|--------|------------|--------|
| Session hijacking | HttpOnly, SameSite | VERIFIED |
| CSRF | Token verification | VERIFIED |
| IDOR | User ownership | VERIFIED |
| Secret exfiltration | Env allowlist | PARTIAL |
| Arbitrary execution | Container sandbox | NOT_RUN |

## Reporting Vulnerabilities

Report privately to maintainers before public disclosure.