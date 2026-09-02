# Contributing to Rann Agent

Thank you for your interest in contributing! 🎉

## Development Setup

```bash
# Clone repo
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Project Structure

```
rann-agent/
├── rann_agent/
│   ├── core/          # Core agent logic
│   ├── tools/         # Tool implementations
│   ├── orchestration/ # Multi-agent coordination
│   ├── memory/        # Persistent memory
│   ├── api/           # FastAPI server
│   ├── cli/           # CLI interface
│   └── utils/         # Utilities
├── tests/             # Test suite
├── docs/              # Documentation
└── examples/          # Usage examples
```

## How to Contribute

### Reporting Bugs

Open an issue with:
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python version, etc.)

### Suggesting Features

Open an issue with:
- Use case description
- Proposed API/interface
- Alternative solutions considered

### Pull Requests

1. **Fork & Branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make Changes**
   - Follow existing code style
   - Add tests for new features
   - Update documentation

3. **Test**
   ```bash
   pytest tests/
   black rann_agent/
   ruff check rann_agent/
   mypy rann_agent/
   ```

4. **Commit**
   ```bash
   git commit -m "feat: add amazing feature"
   ```
   
   Use conventional commits:
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation
   - `test:` tests
   - `refactor:` code refactoring

5. **Push & PR**
   ```bash
   git push origin feature/amazing-feature
   ```

## Code Style

- **Python:** Black (line length 100)
- **Imports:** isort
- **Linting:** Ruff
- **Type hints:** Required for public APIs
- **Docstrings:** Google style

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=rann_agent --cov-report=html

# Specific test
pytest tests/test_agent.py::test_execute

# Integration tests
pytest tests/integration/
```

## Documentation

- Update README.md for user-facing changes
- Add docstrings to new functions/classes
- Update CHANGELOG.md

## Adding New Tools

1. Create tool in `rann_agent/tools/`
2. Inherit from `Tool` base class
3. Implement `execute()` method
4. Register in `ToolRegistry`
5. Add tests
6. Update documentation

Example:
```python
from rann_agent.tools.registry import Tool, ToolResult

class MyTool(Tool):
    name = "my_tool"
    description = "Does something useful"
    parameters = {
        "input": {"type": "string", "required": True},
    }
    
    async def execute(self, input: str, **kwargs):
        # Your logic here
        return ToolResult(
            tool=self.name,
            success=True,
            output="Result"
        ).to_dict()
```

## Release Process

Maintainers only:

1. Update version in `rann_agent/__init__.py`
2. Update CHANGELOG.md
3. Create release tag
4. GitHub Actions will publish to PyPI

## Questions?

- Open a discussion on GitHub
- Join our Discord
- Email: rann@example.com

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
