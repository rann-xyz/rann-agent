# Execution Security Audit

## Purpose

Systematic methodology for auditing RANN Agent execution paths to ensure all agent-controlled command execution routes through the ExecutionBackend abstraction. This prevents arbitrary subprocess execution bypass on the host/API process.

## Trigger

- Security hardening tasks
- Audit of `rann_agent/tools/` directory
- Verification of execution boundary closure
- Pre-deployment security review

## Core Pattern

```
1. REPOSITORY-WIDE SCAN
   - Find all subprocess patterns
   - Categorize by execution risk
   - Trace data flow to caller boundary

2. CLASSIFY SINKS
   - Agent-controlled input? → MUST route through ExecutionBackend
   - Trusted internal operation? → Document why safe
   - Dead/unused code? → Remove or document

3. VERIFY CONTAINMENT
   - All arbitrary execution → ExecutionBackend.submit()
   - No shell=True with arbitrary input
   - No os.system/os.popen
   - No direct Popen for agent commands

4. VERIFY IDENTITY
   - user_id from authenticated session only
   - workspace/run_id/job_id from server
   - client cannot control execution identity

5. RUNTIME VERIFICATION
   - Docker required for container tests
   - NOT_RUN if Docker unavailable
   - Never claim VERIFIED without evidence
```

## File Classification Matrix

| File Type | Risk Level | Action |
|-----------|------------|--------|
| Tool inheritting `Tool` | 🔴 HIGH | Must route through ExecutionBackend |
| Library (helper functions) | 🟡 MEDIUM | Safe only if called by secured tools |
| Internal utilities | 🟢 LOW | Safe if no agent-controlled input |
| Test files | 📝 AUDIT | Verify they don't bypass in production |

## Common False Positives (NOT BYPASSES)

| Pattern | Why It's Safe |
|---------|---------------|
| `shell=False,  # Security: never enable shell=True` | This is a COMMENT/DEFENSE, not activation |
| Regex pattern `r"os\.system\("` | Detection pattern, not execution |
| `subprocess.run(["grep", ...])` | Structured argv, canoncalized paths |
| Library functions called only by secured tools | Indirect path is safe |

## Critical Checks

### 1. Direct Subprocess Patterns (BYPASS)
```
🚨 subprocess.run(cmd, shell=True) with cmd from parameters
🚨 subprocess.Popen(command) with arbitrary input
🚨 os.system(user_input)
🚨 asyncio.create_subprocess_shell(user_command)
```

### 2. Safe Patterns
```
✅ subprocess.run(["fixed_cmd", param1, param2]) with validation
✅ Tools explicitly import and call get_execution_backend()
✅ Commands built as argv lists from allowlisted values
```

## Tool-Specific Checks

### terminal.py / code_exec.py
- Must use `ExecutionJob` with server-derived user_id
- Must call `get_execution_backend()`
- Environment from allowlist only

### Docker/Kubernetes Tools
- `DockerTool`, `KubernetesTool` → ExecutionBackend
- No direct `shell=True` with `image`, `container`, `command` args
- Restricted action allowlists

### Testing Tools
- `TestRunnerTool`, `BenchmarkTool`, `ProfilerTool` → ExecutionBackend
- No shell string interpolation with `target`, `path`, `options`
- Framework/type restricted to allowlists

### Git Tool
- `GitTool` → ExecutionBackend (critical!)
- `workdir` parameter must be validated
- `message`, `files`, `branch` from parameters → backend routing

## Status Definitions (DO NOT CONFUSE)

| Term | Meaning |
|------|---------|
| CODE-VERIFIED | Static analysis confirms correct implementation |
| TEST-VERIFIED | Unit tests pass in this environment |
| RUNTIME-VERIFIED | Container tests pass with Docker |
| NOT_RUN | Environment blocked (Docker unavailable, pytest missing) |
| NOT_IMPLEMENTED | Feature doesn't exist |
| FAIL | Test executed and failed |

## Documentation Requirements

Update these files based on ACTUAL evidence:

- SECURITY.md - Executive summary with honest status
- docs/STATUS.md - Detailed technical status matrix
- README.md - Security warnings about runtime requirements

**Do NOT claim:**
- "production-ready" without Docker tests
- "fully secure" without runtime verification
- "verified isolation" without container tests

## Git Hygiene Checklist

```bash
git diff --check           # Whitespace errors
git status --short         # Unstaged changes
git diff --stat            # Summary of changes
# Verify no .env, secrets, credentials committed
```

## Commit Template

```
security: <action> <affected files>

- Brief description of security fix
- Files changed
- Tool classification (if tools affected)

AUDIT RESULTS:
- [ ] Bypass patterns found: X
- [ ] Tools affected: [list]
- [ ] New risks introduced: None

SECURITY STATUS:
- EXECUTION_ARCHITECTURE: VERIFIED (CODE) / NOT_VERIFIED
- EXECUTION_ISOLATION: VERIFIED / NOT_RUN
- OVERALL_PUBLIC_GATE: VERIFIED / NOT_READY
```

## References

- `references/bypass-audit-log.md` - Session-specific findings
- `scripts/audit_subprocess.py` - Automated scanner script
