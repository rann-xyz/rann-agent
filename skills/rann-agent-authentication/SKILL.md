---
name: rann-agent-authentication
category: development
description: Production-ready authentication and workspace system for RANN Agent web application
version: 1.0
---

# RANN Agent Authentication System

## Overview
Production-ready authentication system for RANN Agent web application with session management, workspace isolation, and secure execution architecture.

## Key Components

### Architecture
```
User
├── Projects (owner_id = user.id)
│   └── Agent Sessions
│       └── Execution History
└── Owned Resources
    ├── Tasks
    ├── Runs
    └── Episodes
```

### Authentication Flow
1. User registers with email, username, password
2. System validates and hashes password with PBKDF2
3. Database-backed session created with CSRF token
4. Secure HttpOnly cookie set
5. User redirected to dashboard

### Session Model
- Session ID: cryptographic 32-byte token
- User ID: foreign key reference
- Token hash: SHA256 hash stored
- Expiration: configurable TTL (default 24h)
- Revocation: soft-delete with revoked_at timestamp
- Metadata: optional IP hash and user-agent

### Password Security
- Algorithm: PBKDF2-HMAC-SHA256
- Iterations: 600,000
- Salt: Random 32 bytes per password
- Storage: Never in plaintext, always hashed
- Logging: Never logged or returned in responses

## Environment Configuration

### Required
- `JWT_SECRET` - Strong secret for token signing

### Optional
- `CORS_ORIGIN` - Comma-separated allowed origins
- `RANN_EXECUTION_BACKEND` - `local` (dev) or `container` (prod)
- `REDIS_URL` - For distributed rate limiting
- `RANN_TRUSTED_PROXY_IPS` - Comma-separated trusted proxy IPs

## Database Schema (SQLite)
```sql
-- Users table with FK constraints
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT DEFAULT 'user',
  disabled_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Sessions table with full audit trail
CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT,
  csrf_token_hash TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  ip_hash TEXT,
  user_agent TEXT,
  last_seen_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Authorization Checks
Every protected resource must verify:
1. User is authenticated
2. User owns the resource OR has explicit permission
3. Session is valid and not expired/revoked

### IDOR Protection Pattern
```python
# WRONG - client-provided ID alone
project = db.get_project(project_id)

# CORRECT - server-derived ownership
project = db.get_project_for_user(user_id, project_id)
```

## References
- `references/auth-audit.md` - Security audit findings
- `references/deployment.md` - Production deployment checklist
