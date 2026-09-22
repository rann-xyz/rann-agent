---
name: public-ai-coding-agent
description: Deploy a public-facing AI coding agent with user-controlled LLM credentials, session isolation, and SSRF protection
category: software-development
tags:
  - security
  - llm
  - api
  - fastapi
  - deployment
  - authentication
  - web
related_skills:
  - verification-loop
  - hermes-agent
---

# Public AI Coding Agent - Security-Hardened Multi-User Deployment

## 🔧 USE WHEN
Deploying a public-facing AI coding agent where users provide their own LLM credentials via web UI, requiring session isolation, SSRF protection, and API key security.

## 📋 CORE PRINCIPLES

### 1. User-Controlled LLM Credentials
- **NEVER** hardcode API keys in source code
- **NEVER** use global LLM credentials for all users
- **ALWAYS** require per-session LLM configuration
- Users must enter their own credentials via web UI

### 2. Session-Based Authentication
```
Browser → Session ID → LLM Config → RuntimeAgent → LLM Provider → Tools → Result
```
- Create session via `POST /api/session`
- Configure LLM via `POST /api/session/llm`
- Task execution automatically uses session config

### 3. API Key Security
**THE API KEY MUST NEVER:**
- Appear in logs
- Appear in SSE events
- Appear in task history
- Appear in error messages
- Be returned in API responses
- Be saved to disk or database
- Be stored in localStorage/sessionStorage

## 🛡️ SECURITY LAYERS

### SSRF Protection
```python
def ssrf_protect_url(url: str) -> bool:
    # Block:
    # - localhost, 127.0.0.1, ::1
    # - Private IP ranges (10.x, 172.16-31.x, 192.168.x)
    # - Link-local (169.254.x)
    # - Cloud metadata endpoints
    # - DNS resolution to private IPs
    # - HTTP redirects to private IPs
```

### Path Traversal Protection
- Use hashed session workspaces
- Validate all file paths with `relative_to()` checks
- Block `../` sequences
- Prevent symlink escapes

### Rate Limiting
```python
# Per-IP rate limits
session_create: 10 req / 60 sec
llm_config: 20 req / 60 sec
llm_test: 10 req / 60 sec
tasks: 5 req / 60 sec
```

### Session Isolation
- Each session gets isolated workspace
- Credential never leaves memory
- No cross-session access

## 🏗️ ENDPOINT CONTRACT

### POST /api/session
```json
// Response:
{"session_id": "secure_random_id", "expires_in": 3600}
```

### POST /api/session/llm
```json
// Response (NO SECRET):
{
  "success": true,
  "session_id": "...",
  "provider": "custom",
  "model": "..."
}
```

## 🧪 TESTING REQUIREMENTS

1. Mock LLM E2E test
2. Session isolation test
3. SSRF protection test
4. API key leak test
5. Rate limiting test

## 🚨 BLOCKERS

Cannot claim "production ready" until HTTPS configured and real LLM test passes.