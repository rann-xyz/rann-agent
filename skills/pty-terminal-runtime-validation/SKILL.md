---
name: pty-terminal-runtime-validation
description: Runtime validation for Docker PTY terminal implementations
category: testing
tags:
  - runtime-validation
  - docker
  - pty
  - websocket
  - terminal
  - security
  - integration-testing
---

# PTY Terminal Runtime Validation

A skill for validating real Docker PTY terminal implementations for AI agent workspaces.

## Overview

This skill provides comprehensive runtime validation for WebSocket PTY terminals that execute inside Docker containers. It ensures security, isolation, and functionality requirements are met before production deployment.

**IMPORTANT**: All tests MUST run against actual Docker containers. Static analysis is insufficient. Mock tests are NOT acceptance criteria.

## Key Principles

1. **Docker Required**: Tests require Docker CLI and daemon availability
2. **No Mocks**: Real container execution is mandatory
3. **Security First**: Never trust client input, especially for PTY operations
4. **Isolation Verified**: Each user's terminal must be isolated from others

## Validation Phases

### Phase 1: Docker Availability
- Verify `docker version` returns success
- Verify `docker info` works
- Check Docker daemon is running

### Phase 2: Image Build
- Build: `docker build -t rann-sandbox:latest docker/sandbox/`
- Verify image exists and is functional
- Check image size and security configuration

### Phase 3: Container Tests

| Test | Command | Expected |
|------|---------|----------|
| Real TTY | `docker exec <container> tty` | `/dev/pts/*` output |
| Terminal Size | `docker exec <container> stty size` | Valid `rows cols` |
| Non-root | `docker exec <container> whoami` | NOT `root` |
| Workspace | `docker exec <container> pwd` | `/workspace` |
| ANSI Support | `printf '\033[31mRED\033[0m\n'` | Escape codes preserved |
| Network Isolation | `curl https://example.com` | FAIL when `SANDBOX_NETWORK_MODE=none` |
| Docker Socket | `ls /var/run/docker.sock` | Not found |
| Environment | `env` | No `SECRET`, `PASSWORD`, `KEY`, `TOKEN` vars |
| Filesystem | `touch /workspace/test` | Writable |

### Phase 4: Interactive Terminal Tests

Requires WebSocket connection to actual terminal.

| Test | Action | Expected |
|------|--------|----------|
| Ctrl+C | Send `0x03` | Interrupt foreground, shell alive |
| Ctrl+D | Send `0x04` | Normal EOF behavior |
| Resize | `{type:"resize", cols:120, rows:40}` | `stty size` returns `40 120` |
| Python REPL | `python` → `print("hello")` | Output received immediately |
| Streaming | `print("A", flush=True); sleep(1); print("B")` | A before B after ~1s |

## Configuration

```bash
# Environment variables for validation
TERMINAL_MAX_MESSAGE_BYTES=1048576
TERMINAL_MAX_SESSIONS_PER_USER=5
TERMINAL_MAX_SESSIONS_PER_PROJECT=2
TERMINAL_IDLE_TIMEOUT=3600
```

## Runtime Tests

### Container Creation
```python
container_id = subprocess.run(
    ["docker", "run", "-d", "--rm", "rann-sandbox:latest"], capture_output=True, text=True
).stdout.strip()
```

### Command Execution
```python
result = subprocess.run(
    ["docker", "exec", container_id, "bash", "-c", command],
    capture_output=True,
    text=True,
    timeout=30,
)
```

## Security Checks

### Must NOT Allow
- Host shell execution
- Docker socket access from terminal
- Arbitrary container_id from client
- Host environment variable leaks
- Cross-user terminal access

### Must Verify
- Non-root user execution
- Workspace-only filesystem
- Resource limits (memory, CPU, PID)

## Final Classification Rules

| Condition | Classification |
|-----------|----------------|
| Docker unavailable | BLOCKED |
| Real PTY not available | BLOCKED |
| Docker socket present | BLOCKED |
| Root user execution | BLOCKED |
| All tests pass | CERTIFIED FOR FRONTEND |

## References

- [runtime-validation.md](./references/runtime-validation.md) - Detailed validation commands
- [terminal-protocol.md](./references/terminal-protocol.md) - WebSocket protocol spec

## Usage

```bash
# Run validation
python tests/security/run_terminal_runtime_validation.py

# With pytest
pytest tests/runtime/test_terminal_runtime.py -v
```
