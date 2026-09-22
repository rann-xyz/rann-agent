# RANN Security Status

**Repository Security Status: Architecture-Verified, Runtime-Pending**

---

## Current Status

```
EXECUTION_ARCHITECTURE: CODE-VERIFIED ✅
EXECUTION_ISOLATION: NOT_VERIFIED ⚠️
OVERALL_PUBLIC_GATE: NOT_READY ⚠️
```

---

## Execution Architecture - CODE-VERIFIED

### All Agent-Controlled Execution Routes Through ExecutionBackend

| Tool | Input Source | Execution Path |
|------|--------------|----------------|
| terminal.py | Agent command | Backend → Container |
| code_exec.py | Agent code | Backend → Container |
| DockerTool | Agent container/image/cmd | Backend → Container |
| KubernetesTool | Agent resource/namespace | Backend → Container |
| TestRunnerTool | Agent path/options | Backend → Container |
| BenchmarkTool | Agent target | Backend → Container |
| ProfilerTool | Agent target | Backend → Container |
| SecurityScannerTool | Agent path | Backend → Container |
| GitTool | Agent files/message/branch | Backend → Container |

### Security Controls - Implemented

| Control | Implementation |
|---------|----------------|
| ContainerExecutionBackend | ✅ Fail-closed when Docker unavailable |
| LocalExecutionBackend | ✅ DEVELOPMENT_ONLY = True |
| Environment isolation | ✅ Allowlist, no os.environ.copy() |
| User identity | ✅ From authenticated session |
| Workspace identity | ✅ Server-generated UUIDs |
| Non-root | ✅ --user 1000:1000 |
| Capability drop | ✅ --cap-drop ALL |
| Privilege escalation | ✅ --security-opt no-new-privileges |
| Filesystem | ✅ --read-only with workspace mount |
| Network | ✅ --network none by default |
| Resource limits | ✅ Memory, CPU, PID limits configured |
| Timeout | ✅ Configurable per job |
| Cancellation | ✅ Process tree termination |

---

## Execution Isolation - NOT_VERIFIED

**Docker Runtime: NOT AVAILABLE**

Container-based security tests cannot execute in current environment.

### Tests Required for Runtime Verification

1. **Container Execution** - Job runs in container, not host
2. **Non-root** - `id -u` ≠ 0 in container
3. **Network Isolation** - Outbound blocked when `network_allowed=False`
4. **Secret Isolation** - Server secrets not visible in container
5. **Filesystem Isolation** - Container cannot access host filesystem
6. **Cross-user Isolation** - User A cannot access User B's workspace
7. **Resource Limits** - Memory/CPU/PID limits enforced at runtime
8. **Timeout** - Infinite processes killed
9. **Cancellation** - Process tree terminated
10. **Container Cleanup** - No orphan containers

---

## Bypass Path Audit - ALL CLOSED ✅

**BEFORE (Vulnerabilities):**
- terminal.py → `asyncio.create_subprocess_shell` direct
- code_exec.py → `subprocess.run` direct
- DockerTool → `shell=True` with agent input
- KubernetesTool → `shell=True` with agent input
- TestRunnerTool → `subprocess.run` with agent input
- BenchmarkTool → `shell=True` with agent input
- ProfilerTool → `shell=True` with agent input
- SecurityScannerTool → `shell=True` with agent input
- GitTool → `shell=True` with agent input

**RESULT:**
✅ All agent-controlled execution paths route through ExecutionBackend
✅ Zero arbitrary subprocess bypasses remain
✅ Static audit complete

---

## Integration Tests

Available in `tests/security/` with pytest markers:

```bash
# Static/CODE-VERIFIED tests
pytest tests/security/ -v

# Runtime/RUNTIME-VERIFIED tests (requires Docker)
pytest tests/security/ -v -m integration
```

**Note:** Integration tests will be skipped if Docker is unavailable.

---

## Git Status

| Item | Status |
|------|--------|
| COMMIT | 8f1f5d2 (docs: update security status documentation) |
| BRANCH | main |
| PUSH | ✅ SUCCESS |
| HEAD == ORIGIN/MAIN | ✅ TRUE |
| WORKING TREE | ✅ CLEAN |