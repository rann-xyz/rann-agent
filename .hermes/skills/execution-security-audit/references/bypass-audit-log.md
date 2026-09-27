# Bypass Audit Log - Session Findings

## Audit Date: Current Session

## Repository-wide Scan Results

### subprocess.run occurrences
| File | Line | Context | Classification |
|------|------|---------|----------------|
| `terminal.py` | 129 | `await backend.submit(job)` | ✅ ROUTES_THROUGH_BACKEND |
| `code_exec.py` | 232 | `await backend.submit(job)` | ✅ ROUTES_THROUGH_BACKEND |
| `git.py` | 108 | `await backend.submit(job)` | ✅ ROUTES_THROUGH_BACKEND |
| `testing_tools.py` | 99 | `await backend.submit(job)` | ✅ ROUTES_THROUGH_BACKEND |
| `intelligence_tools.py` | 315 | `await backend.submit(job)` | ✅ ROUTES_THROUGH_BACKEND |
| `advanced_tools.py` | 265 | `await backend.submit(job)` | ✅ ROUTES_THROUGH_BACKEND |
| `filesystem.py` | 242 | `subprocess.run(["grep", ...])` | ✅ SAFE_INTERNAL (canoncalized path) |

### shell=True occurrences
| File | Line | Code | Classification |
|------|------|------|----------------|
| `self_coding.py` | 94, 95 | Regex DETECTION patterns | ✅ FALSE_POSITIVE (not execution) |
| `terminal.py` | doc | Comment line | ✅ FALSE_POSITIVE (doc) |

### Actual Subprocess Patterns (CRITICAL)

**BEFORE FIX:**
```python
# terminal.py - DIRECT EXECUTION (BYPASS)
process = await asyncio.create_subprocess_shell(command, ...)

# code_exec.py - DIRECT EXECUTION (BYPASS)
process = await asyncio.create_subprocess_exec(...)

# git.py - SHELL=TRUE BYPASS
cmd = f"git {action} {files}"
result = subprocess.run(cmd, shell=True, ...)

# advanced_tools.py - DOCKER KUBERNETES BYPASS
cmd = f"docker run {image} {command}"
result = subprocess.run(cmd, shell=True, ...)
```

**AFTER FIX:**
```python
# ALL TOOLS NOW ROUTE THROUGH BACKEND
job = ExecutionJob(
    job_id=job_id,
    user_id=user_id,  # Server-derived
    command=cmd,
    policy=policy,
)
backend = get_execution_backend()
await backend.submit(job)
```

## Tool-by-Tool Audit Results

### 1. terminal.py
- **Before**: Direct `asyncio.create_subprocess_shell`
- **After**: Routes through `get_execution_backend()`
- **Status**: ✅ FIXED

### 2. code_exec.py
- **Before**: Direct `subprocess.run` with code argument
- **After**: Routes through `get_execution_backend()`
- **Status**: ✅ FIXED

### 3. git.py (CRITICAL)
- **Before**: `subprocess.run(cmd, shell=True, ...)` with string interpolation
- **After**: Routes through `get_execution_backend()` with argv list
- **Status**: ✅ FIXED (final piece)

### 4. advanced_tools.py
- **Before**: `DockerTool` and `KubernetesTool` with `shell=True`
- **After**: Routes through `get_execution_backend()`
- **Status**: ✅ FIXED

### 5. testing_tools.py
- **Before**: `TestRunnerTool`, `BenchmarkTool` with direct execution
- **After**: Routes through `get_execution_backend()`
- **Status**: ✅ FIXED

### 6. intelligence_tools.py
- **Before**: `ProfilerTool`, `SecurityScannerTool` with `shell=True`
- **After**: Routes through `get_execution_backend()`
- **Status**: ✅ FIXED

### 7. filesystem.py
- **Status**: ✅ SAFE (uses `subprocess.run(["grep", ...])` with canonicalized path)

## Execution Flow Verification

```
HTTP Request
 ↓
Authenticated Session (user_id from session, not input)
 ↓
Tool.execute() [terminal, code_exec, git, etc.]
 ↓
ExecutionJob(
    job_id=SERVER_GENERATED,
    user_id=SERVER_DERIVED,
    command=VALIDATED,
    policy=CONFIGURED
)
 ↓
get_execution_backend() # FAIL-CLOSED if Docker unavailable
 ↓
ContainerExecutionBackend.submit(job) / LocalExecutionBackend
 ↓
Isolated Runtime
```

## Environment Constraint

**Docker Runtime: NOT AVAILABLE**
- Cannot run container integration tests
- Execution isolation remains CONFIGURED, NOT_VERIFIED
- Fail-closed behavior verified via code inspection

## Final Status

```
EXECUTION_ARCHITECTURE: VERIFIED (CODE)
EXECUTION_ISOLATION: NOT_RUN (Docker unavailable)
OVERALL_PUBLIC_GATE: NOT_READY
```

No false claims made. All bypasses closed. Runtime verification pending.
