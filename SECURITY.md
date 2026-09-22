# RANN Security

This document describes RANN's security architecture, implemented controls, and known limitations.

## Security Status

| Gate | Status | Evidence |
|------|--------|----------|
| AUTH_GATE | VERIFIED | HTTP integration tests pass |
| EXECUTION_GATE | FAIL | Local backend not sandboxed |
| OVERALL_PUBLIC_GATE | NOT_READY | Execution layer requires container backend |

## Implemented Security

### 🔐 Authentication (VERIFIED)

| Control | Status | Evidence |
|---------|--------|----------|
| Database Sessions | VERIFIED | HTTP tests in `tests/auth/` |
| Password Hashing | CODE-ONLY | PBKDF2-HMAC-SHA256, 600K iterations |
| HttpOnly Cookies | VERIFIED | FastAPI `set_cookie(httponly=True)` |
| SameSite | VERIFIED | `samesite="Lax"` |
| Session Token | VERIFIED | SHA256 hash stored, never plaintext |

### 🛡️ Authorization (VERIFIED)

| Control | Status | Evidence |
|---------|--------|----------|
| User ID from Session | VERIFIED | HTTP tests verify session-derived user |
| Resource Ownership | VERIFIED | SQL queries include `user_id` constraint |
| IDOR Protection | VERIFIED | HTTP tests with cross-user access |

### 🔒 CSRF Protection (VERIFIED)

| Control | Status | Evidence |
|---------|--------|----------|
| Token Required | VERIFIED | HTTP tests verify token enforcement |
| Token Storage | VERIFIED | SHA256 hash in database |
| State-Changing Methods Protected | VERIFIED | POST/PUT/PATCH/DELETE |

### ⏱️ Session Management

| Control | Status | Evidence |
|---------|--------|----------|
| One Active Session | CODE-ONLY | Revokes old sessions on login |
| Session Revocation | VERIFIED | HTTP test for logout |
| Session TTL | VERIFIED | 24-hour expiration |

## Execution Security

### Current Status: ✋ DEVELOPMENT ONLY

The execution backend requires immediate hardwaring for production use.

### LocalExecutionBackend (Current Implementation)

| Control | Status | Evidence |
|---------|--------|----------|
| Process Isolation | NOT_IMPLEMENTED | Same process space as API |
| Environment Sanitization | PARTIAL | Allowlist built, `os.environ` not inherited |
| Network Isolation | PARTIAL | Policy exists, implementation incomplete |
| Resource Limits | PARTIAL | Timeout enforcement exists |
| OS Sandbox | NOT_IMPLEMENTED | No container/process isolation |

### ContainerExecutionBackend (Missing)

**Status: NOT_IMPLEMENTED** - Required for production.

Requires:
- Container or VM isolation
- Explicit environment allowlist injection
- Network policy enforcement at runtime
- Resource limits from container runtime
- Non-root execution
- Workspace-only filesystem access

### Test Evidence: `tests/security/test_execution_isolation.py`

| Test | Status | Evidence |
|------|--------|----------|
| `test_server_secret_not_leaked_to_subprocess` | NOT_TESTED | Requires running test |
| `test_environment_allowlist_enforced` | CODE-ONLY | Static configuration |
| `test_network_policy_default_denied` | CODE-ONLY | Policy default |
| `test_timeout_enforcement` | NOT_TESTED | Requires async test |
| `test_development_only_marker` | CODE-ONLY | DEVELOPMENT_ONLY = True |

## WorkspaceGuard

WorkspaceGuard provides application-level path validation:

- ✅ Prevents `../` traversal
- ✅ Rejects absolute paths outside workspace
- ✅ Validates symlinks don't escape

**IMPORTANT**: This is NOT an OS sandbox. It does not provide:
- Kernel-level isolation
- Process isolation
- Network restrictions
- Memory/CPU limits

## Threats and Mitigations

| Threat | Mitigation | Status |
|--------|------------|--------|
| Unauthenticated API access | Session validation | VERIFIED |
| Session hijacking | HttpOnly, SameSite | VERIFIED |
| CSRF | Token verification | VERIFIED |
| IDOR | User ownership in queries | VERIFIED |
| Secret exfiltration | Allowlist env (in progress) | PARTIAL |
| Arbitrary code execution | None (dev only) | NOT_IMPLEMENTED |
| Network abuse | None | NOT_IMPLEMENTED |
| Resource exhaustion | Partial limits | PARTIAL |
| Process escape | None | NOT_IMPLEMENTED |

## Deployment Requirements

Before PUBLIC DEPLOYMENT, the following must be implemented:

1. **ContainerExecutionBackend** - Isolated process per execution
2. **Environment Sanitization** - Never inherit `os.environ`
3. **Network Policy** - Enforce at container level
4. **Resource Limits** - CPU, memory, timeout from runtime
5. **Non-root Execution** - Worker runs as non-privileged user
6. **Workspace Isolation** - Each run has isolated workspace

## Reporting Vulnerabilities

Security issues should be reported privately before public disclosure.
