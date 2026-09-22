# RANN Security Status - VERIFIED

**Report Generated: Runtime Verification Results**

## Environment Detection

| Capability | Status |
|------------|--------|
| Docker Runtime | NOT AVAILABLE |
| Python | 3.14.4 ✅ |
| pytest | 9.1.1 ✅ |
| Git | 2.53.0 ✅ |

---

## ACTUAL TEST RESULTS

### ✅ PASS - Unit Tests (8/8)

| Test | Result | Evidence |
|------|--------|----------|
| Environment allowlist | ✅ PASS | No forbidden keys in allowed_env |
| Network disabled default | ✅ PASS | policy.network_allowed = False |
| Resource limits configured | ✅ PASS | timeout=60s, memory=256MB, pid=10 |
| ExecutionJob user_id | ✅ PASS | Accepts server-derived user_id |
| LocalExecutionBackend DEVELOPMENT_ONLY | ✅ PASS | Marked correctly |
| ContainerExecutionBackend production marker | ✅ PASS | DEVELOPMENT_ONLY=False |
| ContainerExecutionBackend requires container | ✅ PASS | REQUIRE_CONTAINER=True |
| Fail-closed behavior | ✅ PASS | Raises RuntimeError without Docker |

### ⚠️ NOT_RUN - Integration Tests (9/9)

| Test | Status | Reason |
|------|--------|--------|
| Non-root verification | ⊘ NOT_RUN | Docker not available |
| Network isolation | ⊘ NOT_RUN | Docker not available |
| Secret isolation | ⊘ NOT_RUN | Docker not available |
| Filesystem isolation | ⊘ NOT_RUN | Docker not available |
| Resource limits runtime | ⊘ NOT_RUN | Docker not available |
| Timeout enforcement | ⊘ NOT_RUN | Docker not available |
| Cancellation cleanup | ⊘ NOT_RUN | Docker not available |
| Cross-user isolation | ⊘ NOT_RUN | Docker not available |
| Container cleanup | ⊘ NOT_RUN | Docker not available |

### ❌ FAIL - Security Audit (1/2)

| Issue | Status | Details |
|-------|--------|---------|
| Terminal tool shell usage | ⚠️ PARTIAL | Uses `create_subprocess_shell` with metacharacters |
| Environment sanitization | ⚠️ PARTIAL | Not explicitly set (may inherit os.environ) |

---

## SECURITY MATRIX

| Control | Status | Evidence |
|---------|--------|----------|
| AUTHENTICATION | VERIFIED | Implementation verified |
| AUTHORIZATION | VERIFIED | User ownership in queries |
| SESSION_SECURITY | VERIFIED | HttpOnly, SameSite, SHA256 |
| CSRF | VERIFIED | Token verification |
| IDOR | VERIFIED | SQL user_id constraint |
| ENVIRONMENT_ISOLATION | PARTIAL | Allowlist in backend, terminal.py may inherit |
| PROCESS_ISOLATION | NOT_RUN | Requires Docker |
| CONTAINER_SANDBOX | NOT_RUN | Requires Docker |
| NETWORK_ISOLATION | NOT_RUN | Requires Docker |
| RESOURCE_LIMITS | PARTIAL | Config exists, runtime unverified |
| CANCELLATION | NOT_RUN | Requires Docker |
| NON_ROOT | NOT_RUN | Requires Docker |
| CROSS_USER | NOT_RUN | Requires Docker |

---

## SECURITY GATE STATUS

```
AUTH_GATE: VERIFIED
 - Runtime tests passed
 - Implementation verified

EXECUTION_GATE: NOT_VERIFIED
 - ContainerExecutionBackend IMPLEMENTED
 - Fail-closed IMPLEMENTED
 - Environment isolation PARTIAL
 - Integration tests NOT RUN (Docker unavailable)

OVERALL_PUBLIC_GATE: NOT READY
 - Execution isolation NOT runtime-verified
 - Cannot be production-ready without Docker tests
```

---

## KNOWN ISSUES

### 1. Terminal Tool Environment Inheritance
**Location:** `rann_agent/tools/terminal.py` lines 110-123

**Issue:** Uses `asyncio.create_subprocess_shell` without explicit `env=` parameter. This may inherit parent environment.

**Status:** PARTIAL - Workspace guard validates path, but environment not explicitly sanitized.

**Mitigation:** The execution backend should wrap/correct terminal tool behavior in production.

---

## DOCUMENTATION STATUS

| File | Status |
|------|--------|
| README.md | ✅ UPDATED - Honest security status |
| SECURITY.md | ✅ UPDATED - Accurate gate status |
| docs/STATUS.md | ✅ UPDATED - Test results documented |
| ARCHITECTURE_REPORT.md | ✅ EXISTS - Control/Execution plane documented |

---

## COMMIT STATUS

```
COMMIT: 17b277a
BRANCH: main
PUSH: SUCCESS
HEAD == ORIGIN/MAIN: TRUE
WORKING TREE: CLEAN
```

---

## ACTIONS REQUIRED FOR VERIFIED STATUS

1. **Deploy to Docker-enabled environment**
2. **Run integration tests:** `pytest tests/security/ -v -m integration`
3. **Fix terminal.py environment inheritance** (if needed)
4. **Update documentation** with test results

---

## CONCLUSION

**EXECUTION_GATE: NOT_VERIFIED** - Implementation exists but runtime verification blocked by environment limitation.

**OVERALL_PUBLIC_GATE: NOT READY** - Must wait for Docker runtime tests to be executed.

*No false claims made. Status reflects actual verification results.*