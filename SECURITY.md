# RANN Security

This document describes the security architecture, implemented controls, and known limitations.

## Security Status

| Area | Status | Evidence |
|------|--------|----------|
| Authentication | PASS | Database sessions, PBKDF2-HMAC-SHA256 |
| Authorization | PASS | User ID enforced in all queries |
| CSRF | PASS | Token required for mutations |
| Session Security | PASS | HttpOnly, SameSite cookies |
| IDOR | PASS | User ID enforced at API layer |
| WorkspaceGuard | PARTIAL | Path validation, not OS sandbox |
| Execution Backend | NOT_IMPLEMENTED | Local subprocess only |
| Process Isolation | FAIL | Same process as API |
| Secret Isolation | FAIL | Environment inherited |
| Filesystem Isolation | FAIL | No container |
| Network Isolation | NOT_IMPLEMENTED | No restrictions |
| Resource Limits | NOT_IMPLEMENTED | No limits |
| OS Sandbox | NOT_IMPLEMENTED | No container/sandbox |

**AUTH_GATE: PASS** (authentication layer is secure)

**EXECUTION_GATE: FAIL** (arbitrary execution is NOT safely isolated)

**OVERALL_PUBLIC_GATE: FAIL**

## Authentication

### Database Sessions

Sessions are stored in the `sessions` table with:
- `id`: Session ID (user_id)
- `token_hash`: SHA256 hash of the session token
- `user_id`: Foreign key to users table
- `expires_at`: Session expiration timestamp
- `revoked_at`: Null until session is revoked

Session tokens are never stored in plaintext in the database.

### Password Hashing

- Algorithm: PBKDF2-HMAC-SHA256
- Iterations: 600,000
- Salt: 32 bytes cryptographically random
- Format: `pbkdf2_sha256$600000$salt$hash`

**Do not call this Argon2id** - PBKDF2-HMAC-SHA256 is used.

### Cookie Security

Authentication cookies are set with:
- `HttpOnly=true` - JavaScript cannot read
- `SameSite=Lax` - CSRF mitigation for most requests
- `Path=/` - Available site-wide
- `Secure` - Only in production with HTTPS

## Authorization

### Authenticated Identity

The authenticated user identity comes from the session cookie:

1. Read session cookie
2. Hash token and query database
3. Validate session not revoked/expired
4. Load user from database
5. Return user object

**Never trust client-supplied user identity:**
- `user_id` in JSON body is ignored
- `user_id` in query parameters is ignored
- `X-User-ID` header is ignored

### User Ownership

All protected endpoints enforce ownership through database queries:

```sql
SELECT * FROM runs WHERE id = ? AND user_id = ?
```

The `user_id` comes from the authenticated session, not the request.

## CSRF Protection

Authenticated state-changing requests require a CSRF token:

1. Session stores `csrf_token_hash`
2. Client receives readable CSRF cookie
3. Client sends `X-CSRF-Token` header
4. Server hashes header value and compares to stored hash

Protected methods:
- POST
- PUT
- PATCH
- DELETE

Not protected (establish authentication):
- POST /auth/register
- POST /auth/login

## Session Management

### One Active Session

When a user logs in, existing active sessions are revoked:

```sql
UPDATE sessions SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL
```

### Session Revoke Flow

1. POST /auth/logout
2. Mark current session as revoked in database
3. Clear authentication cookie
4. Subsequent session validation fails

## WorkspaceGuard

WorkspaceGuard provides application-level path validation:

- Prevents `../` traversal
- Rejects absolute paths outside workspace
- Validates symlinks don't escape

**WorkspaceGuard is NOT an OS sandbox.** It:
- Does not prevent kernel-level escapes
- Does not isolate processes
- Does not restrict network access
- Does not limit CPU/memory

## Execution Security

### Current State (NOT PRODUCTION-SAFE)

Arbitrary agent execution occurs:
- In the API process thread
- As a Python subprocess inheriting environment
- With no execution isolation

**Critical limitations:**
- No container/sandbox isolation
- Server environment variables accessible to subprocess
- No network restrictions
- No resource limits

### Environment Handling

**Current behavior**: Subprocesses inherit `os.environ`

**Required**: Environment must be explicitly allowlisted. Server secrets must never reach execution.

## Threats Not Yet Mitigated

| Threat | Current Mitigation |
|--------|---------------------|
| Malicious code execution | ❌ None |
| Secret exfiltration | ❌ Environment inherited |
| Network abuse | ❌ No restrictions |
| Resource exhaustion | ❌ No limits |
| Process escape | ❌ No sandbox |
| Host filesystem access | ⚠️ WorkspaceGuard only |

## Recommendations

Before public deployment:

1. Implement isolated execution worker
2. Add container/sandbox runtime
3. Implement network restrictions
4. Add resource limits
5. Implement proper environment sanitization
6. Test cancellation terminates process trees
7. Verify non-root execution in sandbox

## Reporting Vulnerabilities

Security issues should be reported privately to maintainers before public disclosure.