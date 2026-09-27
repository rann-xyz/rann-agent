#!/usr/bin/env python3
"""
Dynamic Security Validation for RANN Docker Sandbox

Run with: python tests/security/validate_sandbox_runtime.py

This script performs Phase 2-20 validation tests that require Docker.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rann_agent.core.security import WorkspaceSecurity
from rann_agent.execution.docker_sandbox import (
    DockerSandboxConfig,
    DockerSandboxProvider,
)


def check_docker_available():
    """Check if Docker is available."""
    try:
        result = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def print_header(title):
    print(f"\n{'=' * 70}")
    print(f"{title}")
    print("=" * 70)


def print_test(name, passed, evidence=None):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if evidence and not passed:
        print(f"       Evidence: {evidence}")


async def run_validation():
    """Run all security validation tests."""

    print_header("RANN DOCKER SANDBOX SECURITY VALIDATION")

    if not check_docker_available():
        print("\n❌ Docker is not available in this environment")
        print("   Please run this script in a Docker-enabled environment")
        return False

    print("\n✅ Docker is available")

    # Create test config with restrictive settings
    config = DockerSandboxConfig(
        image="rann-sandbox:latest",
        memory_limit="256m",
        cpu_limit="0.5",
        timeout=30,
        max_output_bytes=10240,  # 10KB for tests
        workspace_root=Path(tempfile.mkdtemp()),
    )

    provider = DockerSandboxProvider(config)
    project_id = "validation-test-project"

    results = []

    # ========================================
    # PHASE 2: Container Identity
    # ========================================
    print_header("PHASE 2 — CONTAINER IDENTITY")

    try:
        await provider.create(project_id)
        await provider.start(project_id)

        # Test whoami
        result = await provider.execute(project_id, "whoami")
        whoami_pass = result.stdout.strip() != "root"
        print_test("whoami (not root)", whoami_pass, result.stdout)
        results.append(("whoami", whoami_pass))

        # Test id
        result = await provider.execute(project_id, "id")
        id_pass = "uid=1000" in result.stdout
        print_test("id (contains uid=1000)", id_pass, result.stdout)
        results.append(("id", id_pass))

        # Test pwd
        result = await provider.execute(project_id, "pwd")
        pwd_pass = "/workspace" in result.stdout or result.exit_code == 0
        print_test("pwd", pwd_pass, result.stdout)
        results.append(("pwd", pwd_pass))

        # Test os-release
        result = await provider.execute(project_id, "cat /etc/os-release")
        os_pass = len(result.stdout) > 0
        print_test("/etc/os-release readable", os_pass)
        results.append(("os-release", os_pass))

        # Test privilege escalation
        result = await provider.execute(project_id, "sudo -n id")
        sudo_pass = result.exit_code != 0
        print_test("sudo fails (privilege escalation blocked)", sudo_pass, result.stderr)
        results.append(("sudo", sudo_pass))

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False

    # ========================================
    # PHASE 3: Filesystem Isolation
    # ========================================
    print_header("PHASE 3 — FILESYSTEM ISOLATION")

    sensitive_paths = [
        ("/", "root filesystem"),
        ("/etc/shadow", "password file"),
        ("/root", "root home"),
        ("/home", "user home"),
        ("/var/run/docker.sock", "docker socket"),
        ("/proc/1/root", "proc root"),
    ]

    for path, desc in sensitive_paths:
        result = await provider.execute(
            project_id, f"test -r {path} && echo readable || echo not_readable"
        )
        readable = "readable" in result.stdout and "not_readable" not in result.stdout
        # For directories, permission denied is expected
        blocked = "not_readable" in result.stdout or result.exit_code != 0
        print_test(f"{desc} unreadable", blocked or not readable)
        results.append((f"fs-{path}", blocked or not readable))

    # ========================================
    # PHASE 4: Network Isolation
    # ========================================
    print_header("PHASE 4 — NETWORK ISOLATION")

    # Test network isolation
    result = await provider.execute(
        project_id,
        "curl -s --connect-timeout 2 https://example.com/test 2>&1 || echo 'network_blocked'",
    )
    network_blocked = (
        "network_blocked" in result.stdout
        or "Connection refused" in result.stderr
        or "Failed" in result.stderr
    )
    print_test("Network requests blocked", network_blocked)
    results.append(("network-blocked", network_blocked))

    # Test localhost
    result = await provider.execute(
        project_id, "ping -c 1 127.0.0.1 -W 1 2>&1 || echo 'ping_failed'"
    )
    localhost_blocked = "ping_failed" in result.stdout or result.exit_code != 0
    print_test("localhost ping blocked", localhost_blocked)
    results.append(("localhost-blocked", localhost_blocked))

    # ========================================
    # PHASE 7: Capabilities
    # ========================================
    print_header("PHASE 7 — CAPABILITIES")

    result = await provider.execute(project_id, "cat /proc/self/status | grep Cap")
    has_capabilities = len(result.stdout) > 0
    print_test("Proc status readable", has_capabilities)
    results.append(("proc-status", has_capabilities))

    # ========================================
    # PHASE 9: Symlink Escape
    # ========================================
    print_header("PHASE 9 — SYMLINK ESCAPE")

    # Create symlink in workspace
    result = await provider.execute(project_id, "ln -sf /etc /workspace/link_to_etc")

    # Try to read through symlink
    result = await provider.execute(
        project_id, "cat /workspace/link_to_etc/shadow 2>&1 || echo 'symlink_blocked'"
    )
    symlink_safe = (
        "symlink_blocked" in result.stdout
        or "Permission denied" in result.stderr
        or result.exit_code != 0
    )
    print_test("Symlink escape blocked", symlink_safe)
    results.append(("symlink-escape", symlink_safe))

    # ========================================
    # PHASE 13: Container Lifecycle
    # ========================================
    print_header("PHASE 13 — CONTAINER LIFECYCLE")

    # Create a persistent file
    await provider.write_file(project_id, "persistent.txt", "test_data_12345")

    # Stop and restart
    await provider.stop(project_id)
    await provider.start(project_id)

    # Read the file back
    content = await provider.read_file(project_id, "persistent.txt")
    persisted = "test_data_12345" in content
    print_test("File persists after restart", persisted, content)
    results.append(("file-persist", persisted))

    # ========================================
    # PHASE 14: Concurrent Execution
    # ========================================
    print_header("PHASE 14 — CONCURRENT EXECUTION")

    # Run multiple commands
    async def run_cmd(cmd):
        return await provider.execute(project_id, cmd)

    try:
        results1 = await asyncio.gather(
            run_cmd("echo cmd1"),
            run_cmd("echo cmd2"),
            run_cmd("echo cmd3"),
        )
        concurrent_ok = all(r.exit_code == 0 for r in results1)
        print_test("Concurrent commands execute correctly", concurrent_ok)
        results.append(("concurrent", concurrent_ok))
    except Exception as e:
        print_test("Concurrent commands", False, str(e))
        results.append(("concurrent", False))

    # Cleanup
    await provider.destroy(project_id)

    # ========================================
    # SUMMARY
    # ========================================
    print_header("VALIDATION SUMMARY")

    passed = sum(1 for _, p in results if p)
    total = len(results)

    print(f"\nTotal tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Container is production-ready")
        return True
    else:
        print("\n❌ SOME TESTS FAILED - Review failures above")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_validation())
    sys.exit(0 if success else 1)
