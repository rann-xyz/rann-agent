# PTY Terminal Runtime Validation Reference

## Quick Start

```bash
# On Docker-enabled machine:
python tests/security/run_terminal_runtime_validation.py

# With pytest:
pytest tests/runtime/test_terminal_runtime.py -v
```

## Docker Commands

### Build sandbox image
```bash
docker build -t rann-sandbox:latest docker/sandbox/
```

### Create test container
```bash
docker run -d --rm rann-sandbox:latest
```

### Execute in container
```bash
docker exec -i -t <container_id> bash -i
```

## Required Container Tests

### 1. PTY Verification
```bash
# tty command
docker exec <container> tty

# Expected: /dev/pts/0 (or similar)
```

### 2. Terminal Size
```bash
docker exec <container> stty size

# Expected: "32 120" format
```

### 3. Non-root Verification
```bash
docker exec <container> whoami

# Expected: NOT "root"
```

### 4. Working Directory
```bash
docker exec <container> pwd

# Expected: /workspace
```

### 5. ANSI Preservation
```bash
docker exec <container> bash -c "printf '\033[31mRED\033[0m\n'"

# Expected: Escape sequences preserved
```

### 6. Network Isolation
```bash
# When SANDBOX_NETWORK_MODE=none
docker exec <container> curl -s --connect-timeout 2 https://example.com

# Expected: Connection failure
```

### 7. Docker Socket Check
```bash
docker exec <container> ls /var/run/docker.sock 2>&1

# Expected: "No such file or directory"
```

### 8. Environment Isolation
```bash
docker exec <container> env | grep -E '(SECRET|PASSWORD|KEY|TOKEN)'

# Expected: No matches
```

## WebSocket Protocol

### Client → Server Messages

```json
{"type": "input", "data": "ls -la\r"}
```

```json
{"type": "resize", "cols": 120, "rows": 40}
```

```json
{"type": "ping"}
```

### Server → Client Messages

```json
{"type": "output", "data": "file listing...\n"}
```

```json
{"type": "status", "status": "connected"}
```

```json
{"type": "exit", "code": 0}
```

```json
{"type": "error", "code": "SANDBOX_UNAVAILABLE", "message": "Docker not available"}
```

## Environment Variables

```bash
TERMINAL_MAX_MESSAGE_BYTES=1048576        # 1MB max per message
TERMINAL_MAX_SESSIONS_PER_USER=5          # Per-user limit
TERMINAL_MAX_SESSIONS_PER_PROJECT=2       # Per-project limit
TERMINAL_IDLE_TIMEOUT=3600                # 1 hour idle timeout
TERMINAL_DETACHED_TIMEOUT=7200            # 2 hour detached timeout (optional)
MAX_MESSAGE_BYTES=1048576                 # Same as above, used in code
```

## Container Inspection

### Resource Limits
```bash
docker inspect <container_id> | jq '.[0].HostConfig'
```

Expected fields:
- `Memory`: 1g (or configured value)
- `NanoCpus`: 1000000000 (1.0 CPU)
- `PidsLimit`: 256
- `NetworkMode`: "none" (when restricted)
- `ReadonlyRootfs`: true (if configured)
- `User`: "1000:1000" (non-root)

### Security Options
```bash
docker inspect <container_id> | jq '.[0].HostConfig.SecurityOpt'
```

Expected: ["no-new-privileges"]

### Capabilities
```bash
docker inspect <container_id> | jq '.[0].HostConfig.CapDrop'
```

Expected: ["ALL"]

## Failure Scenarios

### Docker Unavailable
- Return error: `{"type": "error", "code": "SANDBOX_UNAVAILABLE"}`
- Never fall back to host shell
- FastAPI must remain responsive

### Container Death
- Detect EOF on PTY read
- Send exit message
- Close WebSocket cleanly

### Unauthorized Access
- Empty project row → close WebSocket
- Mismatch owner_id → close WebSocket
- No session cookie → close WebSocket

## Common Pitfalls

1. **Wrong exec_resize order**: Must be `(exec_id, rows, cols)`
2. **Missing TTY**: Shell must be `/bin/bash -i` for proper terminal
3. **Resource leaks**: Always kill exec on cleanup
4. **Host execution**: Never use `subprocess` for terminal commands