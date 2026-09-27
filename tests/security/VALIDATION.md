# RANN Docker Sandbox Security Validation

This document contains the security validation requirements for the Docker sandbox runtime.

**IMPORTANT:** Full validation requires Docker CLI access. Run `pytest tests/security/sandbox_runtime_tests.py` in a Docker-enabled environment.

## Static Analysis Results

### ✅ Container Security Configuration
- Non-root user: `rann` (UID 1000)
- Memory limit: 1GB (configurable)
- CPU limit: 1.0 cores (configurable)
- PID limit: 256 (configurable)
- Read-only root filesystem: Yes
- No-new-privileges: Yes
- Capabilities dropped: ALL
- Network mode: none (by default, configurable)

### ✅ Filesystem Isolation
- Workspace path: `/var/lib/rann/workspaces/<project-id>`
- Container mount: `/workspace` (read-write)
- Host filesystem: Not accessible
- Docker socket: Not mounted

### ✅ Resource Limits
- Memory: 1GB (SANDBOX_MEMORY_LIMIT)
- CPU: 1.0 (SANDBOX_CPU_LIMIT)
- Timeout: 120s (SANDBOX_TIMEOUT)
- Max output: 1MB (SANDBOX_MAX_OUTPUT_BYTES)

## Dynamic Validation Required

The following tests must be run in a Docker-enabled environment:

### Test Script: `tests/security/validate_sandbox_runtime.py`

Run with:
```bash
docker build -t rann-sandbox:latest docker/sandbox/
python tests/security/validate_sandbox_runtime.py
```

### Validation Checklist

| Phase | Test | Expected Result | Status |
|-------|------|-----------------|--------|
| 2 | whoami/id/pwd | non-root, /workspace | ⚠️ Not tested |
| 2 | sudo/su | Permission denied | ⚠️ Not tested |
| 3 | /etc/shadow | Permission denied | ⚠️ Not tested |
| 3 | /var/run/docker.sock | No such file | ⚠️ Not tested |
| 3 | /proc/1/root | Permission denied | ⚠️ Not tested |
| 4 | curl/wget | Connection refused/failed | ⚠️ Not tested |
| 5 | Memory exhaustion | OOM killer or limit | ⚠️ Not tested |
| 5 | CPU stress | Limited to 1 core | ⚠️ Not tested |
| 6 | /proc | Only container PIDs | ⚠️ Not tested |
| 7 | /proc/self/status | Limited capabilities | ⚠️ Not tested |
| 8 | Permission escalation | None possible | ⚠️ Not tested |
| 9 | symlink escape | Blocked | ⚠️ Not tested |
| 10 | path traversal | Blocked | ⚠️ Not tested |
| 13 | Container restart | Workspace preserved | ⚠️ Not tested |
| 14 | Concurrent exec | Proper locking | ⚠️ Not tested |
| 18 | Docker unavailable | FAIL CLOSED | ⚠️ Not tested |

## Security Documentation

See SECURITY.md for detailed security model and threat analysis.
