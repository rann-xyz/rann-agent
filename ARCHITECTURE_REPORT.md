# RANN Agent Architecture Report

## Overview

RANN is an autonomous AI agent system with two distinct architectural layers.

---

## Control Plane (Implemented)

The control plane handles authentication, authorization, state, and API responses.

```
[HTTP Client] → [API Router] → [Auth Middleware] → [Database] → [Response]
                              → [Authorization Checks]
                              → [State Changes]
```

### Components

| Component | Purpose | Status |
|-----------|---------|--------|
| FastAPI Router | HTTP endpoints | ✅ Implemented |
| Authentication | Session via cookies | ✅ Implemented |
| Authorization | User ownership enforcement | ✅ Implemented |
| Database | SQLite with 12 tables | ✅ Implemented |
| Task/Runs | State management | ✅ Implemented |

### Authentication Architecture

```
Client → POST /auth/login → Database → Session Cookie
                             ↑
                       sessions table
```

Session flow:
1. Credentials validated against `users` table
2. New session created in `sessions` table
3. Only `token_hash` (SHA256) stored, not raw token
4. Authentication cookies set with HttpOnly, SameSite=Lax

### Authorization Architecture

```
User A → POST /api/runs → API → Database → user_id = session_user_id
User B → tries User A's run → user_id = B ≠ run.user_id = A → DENIED
```

---

## Execution Plane (Planned)

The execution plane handles untrusted agent code execution outside the control plane.

### Current Architecture (UNSAFE - Development Only)

```
[API] → RuntimeAgent → Subprocess (inherits Environment)
           ↓
      Same process!
```

**Critical**: This architecture has no isolation.

### Target Architecture

```
[API] → Execution Queue → Isolated Worker → Sandbox → Agent Runtime
              ↓                    ↓              ↓
         Auth Job          Separate Process   Container/MicroVM
```

### Required Sandbox Features

| Feature | Purpose | Status |
|---------|---------|--------|
| Process Isolation | API separate from execution | NOT_IMPLEMENTED |
| Environment Sanitization | No secrets to subprocess | NOT_IMPLEMENTED |
| Network Policy | Restrict outbound access | NOT_IMPLEMENTED |
| Resource Limits | CPU, memory, disk caps | NOT_IMPLEMENTED |
| Timeout | Kill runaway processes | NOT_IMPLEMENTED |
| Non-root Execution | Prevent privilege escalation | NOT_IMPLEMENTED |

---

## Data Flow

### Authenticated Request Flow

```
1. HTTP Request
2. Extract session cookie
3. Hash token → query sessions table
4. Load user from users table
5. Attach user to request context
6. Database queries include user_id in WHERE clause
7. Response with user-owned data only
```

### Execution Submission Flow

```
1. Authenticated session provides user_id
2. API validates run.user_id == session.user_id
3. ExecutionJob created with user_id, run_id
4. Job submitted to queue (future: isolated worker)
5. Current: RuntimeAgent.execute() in API process (DEVELOPMENT)
```

---

## Security Boundaries

### Implemented Boundaries

| Boundary | Mechanism | Verified |
|----------|-----------|----------|
| Identity | Session cookie → database | ✅ HTTP tests |
| Authorization | user_id in SQL queries | ✅ Code review |
| Session | token_hash storage | ✅ Database tests |
| CSRF | Token comparison | ✅ HTTP tests |

### Missing Boundaries

| Boundary | Required | Status |
|----------|----------|--------|
| Process Isolation | Separate execution process | NOT_IMPLEMENTED |
| Environment | Allowlisted only | NOT_IMPLEMENTED |
| Network | Restrict outbound | NOT_IMPLEMENTED |
| Resources | Limits on CPU/memory | NOT_IMPLEMENTED |
| Filesystem | Container mount isolation | NOT_IMPLEMENTED |

---

## Database Schema (Security Relevant Tables)

```
users
  id (PK)
  email
  password_hash (PBKDF2)
  role

sessions
  session_id (PK)
  user_id (FK → users.id)
  token_hash (SHA256)
  expires_at
  revoked_at

tasks
  id (PK)
  user_id (FK → users.id)
  ...

runs
  id (PK)
  user_id (FK → users.id)
  ...

state_transitions
  id (PK)
  user_id (FK → users.id)
  ...
```

Note: All mutable tables have `user_id` foreign key to enforce ownership.

---

## Module Structure

```
rann_agent/
├── auth/          # Authentication (implemented)
│   ├── __init__.py  # PasswordHasher, Session models
│   └── router.py    # HTTP endpoints
├── core/          # Runtime (implemented)
│   └── security.py  # WorkspaceGuard
├── storage/       # Database (implemented)
│   └── database.py
├── tools/         # Agent tools (implemented)
│   ├── terminal.py # Subprocess execution (UNTRUSTED)
│   └── files.py    # File operations (needs context)
├── execution/     # Planned execution backend
└── web/           # Web API (implemented)
    └── app.py
```

---

## Development vs Production

### Development Mode

- Local database: `~/.rann-agent/rann.db`
- Local execution: subprocess in API process
- Generated secrets: acceptable for testing

### Production Requirements

- External database (not local file)
- Isolated execution worker (NOT IMPLEMENTED)
- Explicit `RANN_IP_BINDING_SECRET` (not generated)
- HTTPS for Secure cookies
- Verified execution isolation

---

## Future Architecture

### Execution Backend Interface (Planned)

```python
class ExecutionBackend:
    def submit(self, job: ExecutionJob) -> str: ...
    def status(self, job_id: str) -> ExecutionStatus: ...
    def cancel(self, job_id: str) -> bool: ...
    def result(self, job_id: str) -> ExecutionResult: ...
```

### Container Backend Requirements

- Non-root user
- No privileged mode
- No host mounts
- Dedicated workspace
- Resource limits (CPU, memory, disk)
- Network policy (default: disabled)
- Process timeout
- Container image: minimal base