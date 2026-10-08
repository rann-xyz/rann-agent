# RANN Execution Backend

This module provides execution backend abstraction with secure fallback for development environments without Docker.

## Backends

### ContainerExecutionBackend (Production)
- Full Docker container isolation
- Non-root execution (user 1000:1000)
- Network isolation (--network none)
- Resource limits (memory, CPU, PID)
- Read-only root filesystem
- Capability dropping (--cap-drop ALL)

### FakeContainerBackend (Development Fallback)
- Process isolation via subprocess with restricted environment
- Non-root user execution when possible
- Workspace filesystem isolation
- Environment variable filtering
- Network restrictions (limited)
- Resource limits enforcement
- Timeout enforcement
- Cleanup after execution

### LocalExecutionBackend (Not Recommended)
- Same process execution
- DEVELOPMENT_ONLY = True
- Minimal isolation - only use for local development

## Fail-Closed Behavior

When Docker is unavailable:
1. ContainerExecutionBackend fails with clear error if RANN_EXECUTION_BACKEND=container
2. Falls back to FakeContainerBackend for safer development
3. Only falls back to LocalExecutionBackend if explicitly set

## Configuration

```bash
# Production (require Docker)
RANN_EXECUTION_BACKEND=container

# Development with safer fallback
RANN_EXECUTION_BACKEND=fake_container

# Development only (least secure)
RANN_EXECUTION_BACKEND=local
```