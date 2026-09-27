# RANN Agent Validation Workflow

## Purpose
Provides standardized approach for validating RANN Agent backend implementations without disrupting Hermes configuration.

## Key Requirements

### Configuration Isolation
- Use `model_config = ConfigDict(extra="ignore")` in Pydantic Settings classes
- Prevents loading `~/.hermes/.env` which causes validation conflicts
- RANN must have independent configuration namespace

### Database Schema Management
- `agent_sessions` table must be added to `rann_agent/storage/database.py`
- Include proper foreign keys to `users` and `projects` tables
- Schema must match: `schema.sql` definitions

### Tool Name Consistency
- `CodeExecTool` (not `CodeExecutionTool`)
- `file_read` tool name (not `read_file`)
- Tool names must match `Tool.name` class attributes

### Testing Approach
1. Run unit tests first: `pytest tests/unit/ -q`
2. Expected: 335+ tests pass
3. Run targeted security tests: `pytest tests/security/ -v -m unit`
4. Skip Docker-dependent tests if Docker unavailable

## Common CI Workflow Issues

### Python Version Syntax
```yaml
# WRONG
python-version: "3.12"

# CORRECT
python-version: "3.12"
```

### Docker Unavailability
Workflows should handle Docker absence gracefully:
```bash
docker version || echo "Docker not available"
docker info || echo "Docker info unavailable"
```

## Verification Commands

```bash
# Config isolation
python3 -c "from rann_agent.core.config import Config; print('OK')"

# Database check
python3 -c "
from rann_agent.storage.database import Database
db = Database()
conn = db._get_conn()
print([r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type=\\'table\\'').fetchall()])
"

# Tool imports
python3 -c "
from rann_agent.tools.registry import ToolRegistry
from rann_agent.core.config import Config
r = ToolRegistry(Config())
print('Tools:', list(r.tools.keys()))
"
```

## References
- `references/ci-cd.json` - CI workflow specifics
- `references/security.md` - Security validation requirements
- `scripts/docker-check.py` - Docker availability probe script
