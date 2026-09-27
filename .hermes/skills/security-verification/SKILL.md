# Security Verification Skill

## Purpose
Ensure security status is reported based on ACTUAL EVIDENCE, not assumptions or hoped-for results.

## Status Definitions

| Level | Meaning | Evidence Required |
|-------|---------|-------------------|
| **CODE-VERIFIED** | Static analysis/inspection confirms correct implementation | Source code review, configuration check |
| **TEST-VERIFIED** | Automated tests run and PASS | pytest results with exit code 0 |
| **RUNTIME-VERIFIED** | Actual container/execution behavior verified | Docker/container tests executing and passing |
| **NOT_RUN** | Test blocked by environment/tooling | Docker unavailable, missing dependencies |
| **FAIL** | Control missing or bypass found | Security violation detected |

## Policy: NEVER Claim RUNTIME-VERIFIED Without Evidence

### ❌ DO NOT CLAIM:
- Container isolation verified
- Non-root execution working
- Network isolation enforced
- Secret isolation at runtime
- Resource limits enforced
- Process tree cleanup working
- Cross-user isolation working

### ✅ ONLY CLAIM WHEN EVIDENCE EXISTS:
- Container execution routes through backend (CODE-VERIFIED)
- Fail-closed behavior implemented (CODE-VERIFIED)
- Environment allowlist enforced (CODE-VERIFIED)
- Server-derived identity (CODE-VERIFIED)
- Integration tests pass (TEST-VERIFIED)
- Docker behavior verified (RUNTIME-VERIFIED)

## Verification Commands

```bash
# Static/bypass audit
python3 scripts/audit_execution_sinks.py

# Unit tests (no Docker required)
pytest tests/security/ -v -m "not integration"

# Integration tests (Docker required)
pytest tests/security/ -v -m integration
```

## Status Reporting Template

```
AUTH_GATE: VERIFIED|NOT_RUN
EXECUTION_ARCHITECTURE: CODE-VERIFIED
EXECUTION_ISOLATION: RUNTIME-VERIFIED|NOT_RUN|FAIL
OVERALL_PUBLIC_GATE: VERIFIED|NOT_READY

Evidence:
- [x] Static audit: all agent execution routes through backend
- [x] Fail-closed: RuntimeError without Docker
- [ ] Docker tests: NOT RUN (Docker unavailable)
```

## Reference Files
- `references/bypass_audit_results.md` - Detailed sink inventory
- `references/docker_test_plan.md` - Runtime verification checklist
- `references/fail_closed_behavior.md` - Expected error messages

## Common Mistakes to Avoid

1. **Never claim VERIFIED based on hope**: "It should work" ≠ evidence
2. **Never hide environment blocks**: Document clearly when Docker missing
3. **No fake test results**: If test can't run, say NOT_RUN
4. **Status consistency**: All docs must match actual state

## Integration Test Markers

Use pytest markers to classify tests:
- `@pytest.mark.unit` - Static analysis, no Docker
- `@pytest.mark.integration` - Requires Docker/runtime
- `@pytest.mark.runtime` - Container behavior verification
- `@pytest.mark.security` - Security validation tests

## Example: Honest Status Report

```
EXECUTION_ARCHITECTURE: CODE-VERIFIED ✅
- All agent-controlled execution routes through ExecutionBackend
- No arbitrary subprocess bypasses detected
- Server-derived identity enforced

EXECUTION_ISOLATION: NOT_RUN ⚠️
- Docker runtime: NOT AVAILABLE in environment
- Cannot verify container boundary at runtime
- Integration tests blocked by environment

OVERALL_PUBLIC_GATE: NOT READY ⚠️
- Requires Docker deployment for full verification
- Status reflects actual verification state
```
