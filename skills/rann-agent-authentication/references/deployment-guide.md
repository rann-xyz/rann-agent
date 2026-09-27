---
position: after main text
---

# RANN Agent Production Deployment Guide

## Prerequisites
- Python 3.10+
- PostgreSQL or SQLite
- Redis (for rate limiting)
- Docker (for sandbox execution)

## Environment Setup

Create `.env` file:
```bash
# Required
JWT_SECRET=your-strong-random-secret-here-min-32-chars

# Optional
CORS_ORIGIN=https://your-domain.com,http://localhost:3000
RANN_EXECUTION_BACKEND=container
REDIS_URL=redis://localhost:6379/0
RANN_TRUSTED_PROXY_IPS=127.0.0.1
```

## Installation

```bash
# Create venv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Run migrations
python -c "from rann_agent.storage.database import Database; Database()"
```

## Development Mode
```bash
# Local execution only
RANN_EXECUTION_BACKEND=local python -m uvicorn web.app:app --reload
```

## Production Mode
```bash
# Container execution required
RANN_EXECUTION_BACKEND=container python -m uvicorn web.app:app
```

## Reverse Proxy Configuration

### Nginx
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Security Hardening

1. Set `secure=True` for session cookies
2. Enable HSTS headers
3. Configure rate limiting limits
4. Review CORS origins
5. Set proper file permissions

## Monitoring

Key metrics to monitor:
- Session creation rate
- Failed login attempts (brute force detection)
- Container startup failures
- Resource limits exceeded
