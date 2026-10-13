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

### Start the Web API

```bash
# Start the FastAPI server
python -m rann_agent.web.app
# Or use: uvicorn rann_agent.web.app:app --reload
```

### Use the CLI

```bash
# Run a task
rann run "create a file hello.txt with content 'Hello World'"
```

---

## Project Structure

```
rann_agent/           # Core Python agent package
├── auth/               # Database sessions, CSRF, auth router
├── execution/          # Execution backend (Local + Container)
├── core/               # Runtime, state machine, config
├── api/                # REST API routes
├── web/                # WebSocket terminal
├── tools/              # Shell, file, git tools
├── storage/            # SQLite database
├── intelligence/       # LLM integration, code analysis
├── memory/             # Session context, episodic memory
└── ...                 # Other modules

frontend/             # Next.js React frontend
docs/                 # Documentation and security audits
tests/                # Test suite (pytest)
scripts/              # Development scripts
docker/               # Sandbox container
skills/               # RANN agent skills and validation
```

### Execution Planes

**Control Plane (Production Ready)**
- Authentication & Authorization
- Session management
- Task/run ownership

**Execution Plane (Development Only)**
- `LocalExecutionBackend` runs subprocesses in API process
- Requires `DockerSandboxProvider` for production isolation

---

## Documentation

- [SECURITY.md](SECURITY.md) - Security model and limitations
- [docs/STATUS.md](docs/STATUS.md) - Factual security status table
- [docs/security-audit/](docs/security-audit/) - Internal security audit methodology

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run unit tests
pytest tests/unit/ -v

# Run security tests
pytest tests/security/ -v

# Run auth tests
pytest tests/auth/ -v
```

---

## License

MIT