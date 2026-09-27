# RANN Architecture Reference Guide

## Main Entry Points

| File | Purpose |
|------|---------|
| `web/app.py` | FastAPI application, includes all routers |
| `rann_agent/__main__.py` | CLI entry point |

## Authentication System

### Router
- `rann_agent/auth/router.py` - POST /auth/register, /auth/login, /auth/logout, /auth/session

### Key Functions
- `hash_password()` - PBKDF2-HMAC-SHA256, 600k iterations
- `verify_password()` - Constant-time comparison
- `generate_session_id()` - `sess_` prefix + random bytes
- `get_current_user()` - FastAPI dependency for auth

### Database Tables
```sql
users: id, email, password_hash, role, disabled_at, created_at, updated_at
sessions: session_id, user_id, csrf_token_hash, created_at, expires_at, revoked_at, last_seen_at
```

## Database Layer

### Main File
- `rann_agent/storage/database.py`

### Schema
- SQLite-based with foreign keys
- `/home/userland/.rann-agent/rann.db` by default
- Automatic migrations on startup

## Execution Backend

### Abstract Interface
- `rann_agent/execution/__init__.py`

### Implementations
- `LocalExecutionBackend` - Development only (runs in process)
- `ContainerExecutionBackend` - Production (Docker)

### Security Settings
```python
# DEFAULT RESOURCE POLICY
timeout_seconds: 60
memory_bytes: 256MB
cpu_shares: 512
pid_limit: 10
max_output_bytes: 1MB
network_allowed: False
```

## Sandbox Provider

### Main File
- `rann_agent/execution/docker_sandbox.py`

### Key Classes
- `DockerSandboxProvider` - Production Docker container management
- `Sandbox` - Container state tracking
- `DockerSandboxConfig` - Environment-based configuration

### Required Environment Variables
```
SANDBOX_IMAGE=rann-sandbox:latest
SANDBOX_MEMORY_LIMIT=1g
SANDBOX_CPU_LIMIT=1.0
SANDBOX_PIDS_LIMIT=256
SANDBOX_TIMEOUT=120
SANDBOX_MAX_OUTPUT_BYTES=1048576
SANDBOX_NETWORK_MODE=none
SANDBOX_WORKSPACE_ROOT=/var/lib/rann/workspaces
```

## WebSocket Terminal

### Implementation
- `rann_agent/web/websocket_terminal.py`

### Endpoint
```
WS /ws/projects/{project_id}/terminal
```

### Message Protocol
```
Client -> Server: {"type": "input", "data": "command\n"}
Server -> Client: {"type": "stdout", "data": "output\n"}
Server -> Client: {"type": "stderr", "data": "error\n"}
Server -> Client: {"type": "exit", "code": 0}
```

### Security Flow
1. Extract session from cookie
2. Validate session against database
3. Check expiration/revocation
4. Verify project ownership
5. Route through sandbox provider
6. Execute inside Docker container

## Common Mistakes to Avoid

### 1. Wrong Authentication Method
```python
# WRONG - creating new auth system
@app.post("/register")
async def register(...):
    # New code instead of using existing

# RIGHT - using existing
from rann_agent.auth.router import router
app.include_router(router)
```

### 2. Host Shell Execution
```python
# WRONG - direct subprocess
subprocess.Popen(["bash", "-c", user_input])

# RIGHT - sandbox provider
await sandbox_provider.execute(project_id, command)
```

### 3. Trusting Client Identity
```python
# WRONG - trusting body
user_id = request.json().get("user_id")

# RIGHT - from session
session_id = request.cookies.get("session")
user_id = session.user_id  # from database lookup
```

### 4. Missing Authorization
```python
# WRONG - no ownership check
result = await db.get_project(project_id)

# RIGHT - verify ownership
if project.owner_id != current_user.id:
    raise HTTPException(403)
```

## Testing Patterns

### Unit Tests
- Use `pytest` with fixtures
- Mock Docker when needed
- Test authorization logic

### Integration Tests
- Run with `SANDBOX_RUNTIME=local`
- Test full request/response cycles
- Verify auth flows

### Security Tests
- Test WebSocket without auth
- Test user A accessing user B's resources
- Test path traversal attempts
- Test symlink escapes