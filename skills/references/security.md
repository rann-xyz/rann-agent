# Security Validation Requirements

## Unit-Level Security Tests (No Docker Required)

### test_security.py
- test_no_hardcoded_secrets_in_code
- test_env_example_no_real_keys
- test_shell_injection_protection
- test_path_traversal_protection
- test_sql_injection_protection
- test_input_sanitization_browser

### test_execution_bypass_audit.py
- Checks for direct subprocess execution without ExecutionBackend routing
- Validates all tool execution paths route through ExecutionBackend
- **FIX: Update hardcoded path from /home/userland/rann-agent/ to $GITHUB_WORKSPACE/**

## Docker-Dependent Tests

### test_execution_isolation.py
- Container isolation verification
- Network isolation tests
- Filesystem isolation tests
- Process cleanup verification

### run_terminal_runtime_validation.py
- PTY validation
- Terminal resize
- Ctrl+C / Ctrl+D handling
- ANSI escape sequence preservation
- Concurrent attach protection

## Required pytest Markers

Tests requiring Docker:
- @pytest.mark.docker_required
- @pytest.mark.integration

Unit-level tests:
- @pytest.mark.unit

To run only Docker-less tests:
```bash
pytest tests/security/ -v -m unit
pytest tests/auth/ -v
```

## Common Security Issues to Fix

1. Hardcoded paths in test files
2. Missing pytest markers on test functions
3. Docker commands without fallback when Docker unavailable
