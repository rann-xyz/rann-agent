# Bypass Audit Results - Executive Summary

## Environment Detection

**Docker Runtime:** NOT RUN - Dependencies installation timed out, pytest not available

## Execution Sink Inventory

### Agent-Controlled Tools (MUST Route Through Backend)

| Tool | Input Source | Execution Method | Status |
|------|--------------|------------------|--------|
| `terminal.py` | agent command | asyncio.create_subprocess_shell | ✅ ROUTED |
| `code_exec.py` | agent code | subprocess.run | ✅ ROUTED |
| `DockerTool` | agent container/image/cmd | subprocess.run + shell=True | ✅ ROUTED |
| `KubernetesTool` | agent resource/namespace | subprocess.run + shell=True | ✅ ROUTED |
| `TestRunnerTool` | agent path/options | subprocess.run | ✅ ROUTED |
| `BenchmarkTool` | agent target | subprocess.run + shell=True | ✅ ROUTED |
| `ProfilerTool` | agent target | subprocess.run + shell=True | ✅ ROUTED |
| `SecurityScannerTool` | agent path | subprocess.run + shell=True | ✅ ROUTED |
| `GitTool` | agent files/message/branch | subprocess.run + shell=True | ✅ ROUTED |

### Internal Infrastructure (Not Bypass)

| File | Purpose | Classification |
|------|---------|----------------|
| `filesystem.py` | File operations | INTERNAL - safe path canoncalization |
| `self_coding.py` | Security regex validation | NOT ACTUAL EXECUTION |
| `rollback_engine.py` | Snapshot rollback | INTERNAL |
| `verification.py` | Test execution | INTERNAL |
| `sandbox.py` | Backend sandbox | BACKEND IMPLEMENTATION |
| `real_terminal.py` | PTY library | INFRASTRUCTURE |

## Test Execution Report

### Tests Actually Executed: 0

| Test Suite | Status | Evidence |
|------------|--------|----------|
| pytest available | NOT_RUN | `python3 -m pytest --version` = "No module named pytest" |
| Backend tests | NOT_RUN | pytest module not available |
| Frontend build | NOT_RUN | npm install timed out |
| Docker validation | NOT_RUN | Dependencies unavailable |

### Tests NOT Run Due to Environment

- `tests/api/test_projects_files_terminal.py` - pytest unavailable
- `tests/integration/test_e2e_workspace.py` - pytest unavailable  
- `tests/runtime/test_terminal_runtime.py` - pytest unavailable
- `tests/execution/test_docker_sandbox.py` - pytest unavailable
- `frontend/npm run build` - npm install timeout

## Final Status

**EXECUTION_ARCHITECTURE: CODE-VERIFIED** ✅
- Zero arbitrary subprocess bypasses remain
- All 9 agent-controlled tools verified routing through backend

**RUNTIME_VALIDATION: NOT_RUN** ⚠️
- Docker unavailable - cannot verify container isolation
- pytest module not installed
- npm dependencies timeout

**PRODUCTION_CERTIFICATION: NOT GRANTED** ❌
- No tests executed
- Docker runtime unavailable
- Runtime security cannot be verified

## Deployment Requirements

When Docker is available:
```bash
# 1. Install dependencies
uv pip install pytest httpx fastapi

# 2. Build sandbox image  
docker build -t rann-sandbox:latest docker/sandbox/

# 3. Run validation
./scripts/validate.sh
```

## Next Steps

1. Fix dependency installation (timeout during `uv pip install pytest`)
2. Run pytest tests when available
3. Execute Docker runtime validation
4. Build and test frontend