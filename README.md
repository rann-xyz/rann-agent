# RANN Agent

Autonomous AI engineering platform with stateful execution, tool isolation, and self-healing capabilities.

## ⚠️ SECURITY NOTICE

**AUTHENTICATION_GATE: VERIFIED** ✅

**EXECUTION_GATE: NOT READY** ⚠️

**CURRENT STATUS: Development environment only. DO NOT expose arbitrary execution publicly.**

The execution layer lacks container/VM isolation. Server environments are not protected.

See [SECURITY.md](SECURITY.md) and [docs/STATUS.md](docs/STATUS.md) for full details.

---

## Quick Start

```bash
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent
python -m venv venv && source venv/bin/activate
pip install -e .
```

### Run a Task

```bash
rann run "create a file hello.txt with content 'Hello World'"
```

### Start the Web API

```bash
python -m rann_agent.web_api
```

---

## Security Status

| Layer | Status |
|-------|--------|
| Authentication | ✅ VERIFIED |
| Authorization | ✅ VERIFIED |
| Session Security | ✅ VERIFIED |
| CSRF Protection | ✅ VERIFIED |
| Environment Isolation | ⚠️ PARTIAL |
| Process Isolation | ❌ NOT IMPLEMENTED |
| Network Isolation | ❌ NOT IMPLEMENTED |
| Resource Limits | ⚠️ PARTIAL |
| **Overall** | ❌ **NOT READY FOR PUBLIC EXECUTION** |

---

## Architecture

```
rann_agent/
├── auth/           # Database sessions, CSRF, auth router
├── execution/      # Execution backend abstraction (development only)
├── core/
│   ├── runtime.py  # RuntimeAgent
│   ├── security.py # WorkspaceGuard, CommandSanitizer
│   └── state.py    # 16-state machine
├── tools/
│   ├── terminal.py # Shell execution (needs sandbox)
│   └── files.py    # File operations
├── storage/
│   └── database.py # SQLite with users/sessions
└── web/
    └── app.py      # FastAPI endpoints
```

### Execution Planes

**Control Plane (Production Ready)**
- Authentication & Authorization
- Session management
- Task/run ownership

**Execution Plane (Development Only)**
- LocalExecutionBackend runs subprocesses in API process
- Requires ContainerExecutionBackend for production

---

## Documentation

- [SECURITY.md](SECURITY.md) - Security model and limitations
- [docs/STATUS.md](docs/STATUS.md) - Factual security status table

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Auth tests
pytest tests/auth/ -v

# Security tests
pytest tests/security/ -v
```

---

## License

MIT
