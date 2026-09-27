# RANN Agent Architecture Audit

A class-level skill for safely extending the RANN Agent codebase.

## When to Use This Skill

Use when working on the RANN Agent repository to ensure you're extending, not duplicating, the existing architecture.

## Key Principles

### 1. IMMEDIATE ARCHITECTURE INSPECTION

Before any implementation:
- `git log --oneline -10` to understand recent changes
- Find the main entry point (`web/app.py`)
- Identify existing routers, middlewares, and services
- Locate authentication, database, and execution systems

**DO NOT** start implementing until you've traced through the existing code paths.

### 2. EXISTING SYSTEM REUSE

RANN Agent already has comprehensive systems for:
- Authentication: `rann_agent/auth/router.py` (FastAPI, cookie-based sessions)
- Database: `rann_agent/storage/database.py` (SQLite with FK constraints)
- Execution: `rann_agent/execution/__init__.py` (Local + Container backends)
- Session Management: Database-backed with JWT-like tokens

**DO NOT** create duplicate:
- Express.js servers when FastAPI exists
- Separate auth systems when one is already comprehensive
- New database schemas when migrations exist
- Host-level shell execution (security risk)

### 3. VERIFY BEFORE CLAIM PRODUCTION

The user emphasized:
> "Do NOT claim 'production-ready' unless the actual code and tests support that claim."

**Static analysis ≠ production readiness** for container isolation.

If Docker is unavailable, mark tests as:
```
NOT_TESTED — Docker unavailable
```

Never claim "production-ready" based solely on code review.

### 4. STATIC VS RUNTIME VALIDATION

**Static Analysis** proves:
- Code correctness
- Security property assertions
- Configuration validation

**Runtime Validation** proves:
- Container isolation
- Filesystem isolation
- Network isolation
- Resource limits
- Process isolation
- Actual Docker security

When Docker CLI is unavailable:
1. Implement the code correctly
2. Document what CAN'T be tested
3. Create validation scripts for when Docker is available
4. Do NOT mark as production-ready

### 5. ARCHITECTURAL VERIFICATION CHECKLIST

Before implementing new features:

```
[ ] Inspect existing auth system
[ ] Check database schema for auth tables
[ ] Verify session management approach
[ ] Identify execution backend
[ ] Understand project/workspace model
[ ] Find existing authorization checks
[ ] Check environment configuration
[ ] Verify WebSocket/Webhook support
```

### 6. IMPLEMENTATION PATTERN

When adding new endpoints or features:

1. **Start with verification**: `git log`, `git show` last commits
2. **Find the router**: Look for `APIRouter` in existing code
3. **Reuse auth dependency**: Use `get_current_user` from existing auth
4. **Add authorization**: Verify `project.owner_id == user_id`
5. **Route through sandbox**: Always use `get_sandbox_manager()`
6. **Test locally**: Run with `SANDBOX_RUNTIME=local`
7. **Document limitations**: Note what requires Docker

### 7. COMMON PITFALLS

| Pitfall | How to Avoid |
|---------|--------------|
| Creating duplicate auth system | Use `rann_agent/auth/router.py` |
| Host shell execution | Go through DockerSandboxProvider |
| Hardcoding secrets | Use environment variables |
| Claiming production-ready without Docker | Mark tests NOT_TESTED |
| Trusting client IDs | Always derive from authenticated session |
| Missing rate limiting | Use existing `_rate_limits` dict or Redis |

### 8. WEBSOCKET TERMINAL PATTERN

When implementing terminal access:

```python
# Use existing session validation
async def get_current_user_id(websocket: WebSocket) -> Optional[str]:
    session_id = websocket.cookies.get("session")
    if not session_id:
        return None

    # Validate against database (not auth_manager which may not exist)
    db = Database()
    conn = db._get_conn()
    row = conn.execute(
        "SELECT u.id FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.session_id = ?",
        (session_id,),
    ).fetchone()
    return row["id"] if row else None


# Authorization check
if row["owner_id"] != user_id:
    await websocket.close()
    return  # Don't reveal if project exists

# Execution through sandbox
result = await sandbox_provider.execute(project_id, command)
```

### 9. VERIFICATION SCRIPTS

Create validation scripts in `tests/security/validate_sandbox_runtime.py` that:
- Check if Docker is available
- Run actual container tests
- Report what was tested vs what wasn't
- Provide clear PASS/FAIL/NOT_TESTED results

### 10. PUSH STRATEGY

When pushing multiple files:
```bash
git add file1 file2 file3
git commit -m "feat: description of complete feature"
git push origin main
```

Don't push half-implemented work. Push complete, working features.

## References

- `rann_agent/auth/router.py` - Authentication system
- `rann_agent/storage/database.py` - Database schema and migrations
- `rann_agent/execution/docker_sandbox.py` - Docker sandbox implementation
- `rann_agent/web/websocket_terminal.py` - WebSocket terminal
- `web/app.py` - Main FastAPI application
