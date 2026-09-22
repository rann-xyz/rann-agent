# RANN Security

This document describes RANN's security architecture and known limitations.

## Security Status

| Gate | Status | Evidence |
|------|--------|----------|
| AUTH_GATE | VERIFIED | Implementation verified |
| EXECUTION_GATE | NOT_RUN | Container tests await runtime |
| OVERALL_PUBLIC_GATE | NOT_READY | Execution isolation unverified |

## Implemented Controls

### Authentication (VERIFIED)
- Database sessions with SHA256 token hash
- PBKDF2-HMAC-SHA256 password hashing (600K iterations)
- HttpOnly, SameSite=Lax cookies
- Session revocation on logout

### Authorization (VERIFIED)
- User ID from authenticated session only
- SQL queries enforce `user_id` constraint
- IDOR protection via ownership checks

### CSRF Protection (VERIFIED)
- Token required for state-changing requests
- SHA256 hash stored in database
- X-CSRF-Token header verification

### Session Management (VERIFIED)
- One active session enforced
- 24-hour TTL
- Database-backed persistence

## Execution Security

### LocalExecutionBackend (DEVELOPMENT ONLY)

**Status: DEVELOPMENT_ONLY** - Not a production sandbox.

Features:
- Environment allowlist only (no os.environ inheritance)
- Timeout enforcement via asyncio.wait_for
- Workspace isolation via path validation

Limitations:
- Runs in API process space
- No container/VM isolation
- Network access not restricted at runtime

### ContainerExecutionBackend (PRODUCTION)

**Status: CODE-ONLY** - Implementation exists, runtime testing NOT RUN.

Features:
- Docker container isolation
- Non-root user (UID 1000)
- no-new-privileges security option
- Dropped all Linux capabilities
- Read-only root filesystem
- Workspace-only writable mount
- Network disabled by default
- CPU, memory, PID limits enforced by Docker

Fail-closed behavior:
```
RuntimeError: ContainerExecutionBackend unavailable.
Docker runtime not found.
Set RANN_EXECUTION_BACKEND=local for development only.
```

## Known Limitations

| Control | Status | Notes |
|---------|--------|-------|
| Process Isolation | NOT_RUN | Requires container runtime |
| Secret Isolation | PARTIAL | Allowlist blocks inheritance, not runtime tested |
| Network Isolation | PARTIAL | Policy exists, runtime enforcement not verified |
| Non-root Execution | NOT_RUN | Requires container runtime |
| Cross-user Isolation | NOT_RUN | Requires container runtime |

## Threats and Mitigations

| Threat | Mitigation | Status |
|--------|------------|--------|
| Session hijacking | HttpOnly, SameSite cookies | VERIFIED |
| CSRF attacks | Token verification | VERIFIED |
| IDOR | User ownership checks | VERIFIED |
| Secret exfiltration | Environment allowlist | PARTIAL |
| Arbitrary code execution | Container isolation (awaiting runtime test) | NOT_RUN |
| Resource exhaustion | Docker resource limits | NOT_RUN |

## Deployment

**PUBLIC DEPLOYMENT: NOT READY**

Before public deployment:
1. Run integration tests with Docker available
2. Verify non-root execution
3. Verify network isolation
4. Verify secret isolation
5. Verify cross-user isolation

## Reporting Vulnerabilities

Security issues: report privately before public disclosure.
