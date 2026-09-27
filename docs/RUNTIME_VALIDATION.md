# RANN Agent Runtime Validation Guide

## Overview

This document describes how to validate the RANN Agent runtime environment.

## Requirements

The production deployment requires:

1. **Docker daemon** - Accessible to backend for sandbox execution
2. **WebSocket support** - For terminal and agent streaming
3. **Persistent storage** - For workspace files and database
4. **HTTPS termination** - For secure WebSocket (wss://)
5. **Port 8000** - FastAPI application port

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install pytest httpx

# 2. Initialize database
python -c "from rann_agent.storage.database import Database; d = Database()"

# 3. Run backend
uvicorn web.app:app --port 8000

# 4. Run tests
./scripts/validate.sh
# or
pytest -v
```

## Docker Runtime Validation

### Build Sandbox Image

```bash
docker build -t rann-sandbox:latest docker/sandbox/
```

### Run Full Validation

```bash
# Full security validation
python tests/security/run_terminal_runtime_validation.py

# Unit tests
pytest tests/runtime/test_terminal_runtime.py -v
pytest tests/execution/test_docker_sandbox.py -v
pytest tests/websocket/test_websocket_terminal.py -v

# Integration tests
pytest tests/api/test_projects_files_terminal.py -v
pytest tests/integration/test_e2e_workspace.py -v
```

## Validation Checklist

### ✅ Backend Components

| Component | Status | Test |
|-----------|--------|------|
| Database init | IMPLEMENTED | `Database()` constructor |
| Auth | IMPLEMENTED | Register/Login flow |
| Project API | IMPLEMENTED | CRUD operations |
| File API | IMPLEMENTED | Path security |
| Terminal API | IMPLEMENTED | Session management |
| Agent API | IMPLEMENTED | Session + WebSocket |

### ⏳ Docker Runtime Tests

| Test | Command | Required |
|------|---------|----------|
| Docker available | `docker info` | ✅ |
| PTY creation | `bash -c 'tty'` | ✅ |
| Non-root user | `whoami` ≠ root | ✅ |
| Workspace dir | `pwd` = /workspace | ✅ |
| Network isolation | curl blocked | ✅ |
| Docker socket | `/var/run/docker.sock` absent | ✅ |
| Environment secrets | env shows no JWT_SECRET | ✅ |
| Resource limits | Memory/CPU capped | ✅ |

### ❌ Production Certification

**NOT GRANTED** - Docker runtime validation not executed in current environment.

## Deployment Targets

### Compatible
- Self-hosted VPS with Docker
- VM with Docker access
- Kubernetes with Docker-in-Docker

### Incompatible
- **Vercel** - No Docker daemon access
- **Netlify** - No WebSocket + Docker
- **Railway** (free tier) - Limited container runtime
- **Render** - Limited Docker features

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | No | SQLite path or PostgreSQL URL |
| JWT_SECRET | Yes (prod) | Secret for session signing |
| CORS_ORIGINS | No | Comma-separated allowed origins |
| SANDBOX_NETWORK_MODE | No | Docker network mode (default: none) |

## Test Expectations

When Docker is unavailable:
```
DOCKER_RUNTIME = NOT_RUN
```

All non-Docker tests should still pass:
- Database operations
- Authentication flow
- Project ownership
- File path security
- WorkspaceGuard validation
```bash
python -c "
from rann_agent.core.security import WorkspaceGuard
from pathlib import Path

guard = WorkspaceGuard(Path('/workspace/project'))
print('Testing path traversal...')

# Test cases
tests = [
    ('../etc/passwd', False),
    ('../../etc/passwd', False),
    ('/etc/passwd', False),
    ('./file.txt', True),
    ('src/app.py', True),
]

for path, should_pass in tests:
    try:
        result = guard.validate_path(path)
        passed = result and not str(result).startswith('/etc')
        print(f'{path}: {\"PASS\" if passed == should_pass else \"FAIL\"}')\"