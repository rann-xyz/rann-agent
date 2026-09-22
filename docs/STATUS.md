# RANN Security Status

Authentic status of RANN implementation and security.

## Security Status Matrix

| Component | Status | Evidence |
|-----------|--------|----------|
| AUTHENTICATION | CODE-ONLY | HTTP tests exist, not executed in current env |
| AUTHORIZATION | VERIFIED | User_id enforced in SQL queries |
| SESSION_SECURITY | VERIFIED | HttpOnly, SameSite=Lax, SHA256 hashed tokens |
| CSRF | VERIFIED | Token required for state-changing requests |
| SESSION_PERSISTENCE | VERIFIED | Database-backed sessions |
| ONE_ACTIVE_SESSION | VERIFIED | Old sessions revoked on new login |
| IDOR_PROTECTION | VERIFIED | User ownership in all protected queries |

## Execution Layer Status

| Component | Status | Evidence |
|-----------|--------|----------|
| LOCAL_BACKEND | DEVELOPMENT_ONLY | Marked with DEVELOPMENT_ONLY=True |
| CONTAINER_BACKEND | NOT_RUN | Docker not available in test env |
| ENVIRONMENT_ISOLATION | PARTIAL | Allowlist blocks os.environ inheritance |
| PROCESS_ISOLATION | NOT_IMPLEMENTED | Requires ContainerExecutionBackend |
| OS_SANDBOX | NOT_RUN | Requires Docker/Container runtime |
| NETWORK_POLICY | PARTIAL | Default=False, runtime enforcement untested |
| RESOURCE_LIMITS | PARTIAL | Timeout configured, runtime enforcement untested |
| NON_ROOT | NOT_RUN | Requires container runtime |
| FAIL_CLOSED | VERIFIED | ContainerExecutionBackend raises RuntimeError without Docker |

## Test Status

| Test File | Status | Notes |
|-----------|--------|-------|
| tests/auth/test_http_auth.py | EXISTS | HTTP tests exist but not executed |
| tests/security/test_execution_isolation.py | EXISTS | Unit + Integration tests with markers |

## Overall Public Gate

**STATUS: NOT_READY** ⚠️

```
AUTH_GATE: VERIFIED (implementation verified, tests pending env)
EXECUTION_GATE: NOT_RUN (Docker unavailable)
OVERALL_PUBLIC_GATE: NOT_READY
```

### Why NOT READY

1. **Container runtime unavailable** in current environment
2. **Integration tests not executed** due to missing Docker
3. **Execution must use ContainerExecutionBackend for production**
4. **LocalExecutionBackend is DEVELOPMENT_ONLY**

## Production Requirements

For `EXECUTION_GATE = VERIFIED` and `OVERALL_PUBLIC_GATE = VERIFIED`:

1. ✅ ContainerExecutionBackend implemented
2. ✅ Environment allowlist (no os.environ inheritance)
3. ❌ Container runtime tests (awaiting runtime)
4. ❌ Non-root verification (awaiting runtime)
5. ❌ Network isolation verification (awaiting runtime)
6. ❌ Secret leak prevention (awaiting runtime)

## Test Commands

```bash
# Run unit tests (no Docker required)
pytest tests/security/ -v -m unit

# Run integration tests (requires Docker)
pytest tests/security/ -v -m integration

# Run all tests
pytest tests/ -v
```

## Implementation Details

### ContainerExecutionBackend

- Uses Docker with: no-new-privileges, dropped capabilities
- Read-only root filesystem
- Workspace mounted at /workspace:rw only
- Network disabled by default
- Resource limits enforced by Docker
- Non-root user (UID 1000)

### Fail-Closed Behavior

When Docker unavailable:
```
RuntimeError: FAIL CLOSED: ContainerExecutionBackend unavailable.
Set RANN_EXECUTION_BACKEND=local for development only.
```

### LocalExecutionBackend

- Development-only backend
- Runs in API process space
- Environment allowlist enforced
- Timeout via asyncio.wait_for
- NOT a production sandbox
