# RANN Execution Backend

This module provides execution backend abstraction with secure fallback for development environments without Docker.

## Security Model

The isolation hierarchy from strongest to weakest:

| Backend | Isolation | Network | Root FS | Production |
|---------|-----------|---------|---------|------------|
| ContainerExecutionBackend | Docker container | disabled (default) | read-only | YES |
| FakeContainerBackend | host subprocess | NAT through host | host user | NO |
| LocalExecutionBackend | host subprocess | host network | host user | NO |

**IMPORTANT**: FakeContainerBackend is a development convenience, NOT a security sandbox. 
Subprocesses execute on the host with restricted environment. For security-critical workloads,
use ContainerExecutionBackend with Docker.

## Backends

### ContainerExecutionBackend (Production)
**Docker container isolation - the primary security boundary for production**

- ✅ Full OS-level container isolation
- ✅ Non-root execution (user 1000:1000)
- ✅ Network disabled by default (`--network none`)
- ✅ Read-only root filesystem (`--read-only`)
- ✅ Capability dropping (`--cap-drop ALL`)
- ✅ No new privileges (`--security-opt no-new-privileges`)
- ✅ Memory limits (configurable)
- ✅ CPU limits (configurable)
- ✅ PID limits (configurable)
- ✅ Execution timeout support
- ✅ Output size limits
- ✅ Environment variable allowlist only
- ✅ Workspace mounted read-write, root filesystem read-only
- ✅ tmpfs for /dev/shm
- ✅ Implicit Docker socket protection (not mounted)
- ✅ Dedicated per-job workspace
- ✅ Automatic container cleanup
- ✅ Container cleanup on timeout/failure

**Requirements:**
- Docker CLI or compatible container runtime
- Network permissions to create containers
- Access to container image (python:3.11-slim)

### FakeContainerBackend (Development Fallback)
**Process isolation for development when Docker is unavailable**

⚠️  **NOT A SECURITY SANDBOX** - Subprocesses run on the host

- ✅ Workspace filesystem isolation (/tmp/rann_fake_ws_*)
- ✅ Environment variable filtering (blocks RANN_*, API_KEY, etc.)
- ✅ Timeout enforcement
- ✅ Output size limits
- ✅ Cleanup after execution
- ✅ Command validation (blocks obvious dangerous patterns)

**Limitations:**
- No container isolation - processes run on host
- No network namespace isolation
- Host /tmp is still accessible (limited protection)
- Command blocklist can be bypassed

### LocalExecutionBackend (Development Only)
**Same-process execution - minimal isolation**

- ✅ Workspace isolation only
- ✅ Limited environment restriction
- ⚠️ Runs in same process space
- ⚠️ **DEVELOPMENT_ONLY** - not safe for untrusted code

## Fail-Closed Behavior

When Docker is unavailable:
1. `ContainerExecutionBackend` fails with clear error if `RANN_EXECUTION_BACKEND=container`
2. Falls back to `FakeContainerBackend` for safer development
3. Only falls back to `LocalExecutionBackend` if explicitly set

**Production deployments MUST use Docker.** The `container` backend will fail closed if Docker is unavailable.

## Configuration

```bash
# Production (require Docker)
RANN_EXECUTION_BACKEND=container

# Development with safer fallback (default)
RANN_EXECUTION_BACKEND=fake_container

# Development only (least secure)
RANN_EXECUTION_BACKEND=local
```

## Security Controls Summary

### Container Execution (All enforced by Docker runtime)

| Control | Implementation |
|---------|----------------|
| Isolation | Docker container |
| User | `--user 1000:1000` |
| Network | `--network none` (unless enabled) |
| Root FS | `--read-only` |
| Capabilities | `--cap-drop ALL` |
| Privileges | `--security-opt no-new-privileges` |
| Memory | `--memory` limit |
| CPU | `--cpus` limit |
| PID | `--pids-limit` |
| Timeout | Docker exec timeout + process kill |
| Workspace | `-v <workspace>:/workspace:rw` only |
| Docker socket | Not mounted (implicit protection) |
| Cleanup | `--rm` + explicit workspace cleanup |

### Fake Container Execution (Process-level protections)

| Control | Implementation |
|---------|----------------|
| Isolation | Separate /tmp subdirectory per job |
| Environment | Allowlist only, sensitive vars filtered |
| Timeout | asyncio.wait_for() |
| Output | Truncated to max_output_bytes |
| Cleanup | shutil.rmtree() after execution |
| Commands | Blocklist for obvious dangerous patterns |

## Environment Variables

The following environment variables configure resource limits:

```bash
# Container image to use
SANDBOX_IMAGE=python:3.11-slim

# Resource limits
SANDBOX_MEMORY_LIMIT=1g
SANDBOX_CPU_LIMIT=1.0
SANDBOX_PIDS_LIMIT=256
SANDBOX_TIMEOUT=120
SANDBOX_MAX_OUTPUT_BYTES=1048576
SANDBOX_NETWORK_MODE=none
SANDBOX_WORKSPACE_ROOT=/var/lib/rann/workspaces
```