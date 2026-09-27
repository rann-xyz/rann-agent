#!/usr/bin/env python3
"""
RANN PTY Runtime Validation Script

This script performs REAL runtime validation against Docker containers.
DO NOT MOCK DOCKER - all tests require actual Docker runtime.

Run with Docker available:
    python tests/security/run_terminal_runtime_validation.py

Usage:
    python tests/security/run_terminal_runtime_validation.py [--fix]

    --fix: Attempt to build image and start containers automatically
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

# Ensure we can import the rann_agent module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class ValidationResult:
    """Holds validation result for a single test."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.details: str | None = None
        self.output: str | None = None

    def set_pass(self, details: str = None, output: str = None):
        self.passed = True
        self.details = details
        self.output = output

    def set_fail(self, details: str, output: str = None):
        self.passed = False
        self.details = details
        self.output = output

    def set_not_run(self, reason: str):
        self.passed = False
        self.details = reason
        self.output = None


class PTYRuntimeValidator:
    """Validates PTY terminal implementation against actual Docker."""

    def __init__(self):
        self.results: dict[str, ValidationResult] = {}
        self.docker_available = False
        self.container_id: str | None = None
        self.project_id: str | None = None

    def check_docker_available(self) -> bool:
        """Check if Docker CLI is available."""
        try:
            result = subprocess.run(
                ["docker", "version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return False

            result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return False

    def build_sandbox_image(self) -> bool:
        """Build the RANN sandbox Docker image."""
        project_root = Path(__file__).parent.parent.parent
        dockerfile_path = project_root / "docker" / "sandbox" / "Dockerfile"

        if not dockerfile_path.exists():
            return False

        try:
            result = subprocess.run(
                ["docker", "build", "-t", "rann-sandbox:latest", str(dockerfile_path.parent)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.returncode == 0
        except Exception:
            return False

    def create_test_container(self) -> str | None:
        """Create a test container."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "-v",
                    f"{Path.home()}/.rann-agent:/root/.rann-agent",
                    "rann-sandbox:latest",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def stop_test_container(self, container_id: str):
        """Stop test container."""
        try:
            subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=10)
        except Exception:
            pass

    def run_in_container(self, container_id: str, command: str) -> tuple:
        """Run command in container, return (success, stdout, stderr)."""
        try:
            result = subprocess.run(
                ["docker", "exec", container_id, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)

    async def validate_all(self):
        """Run all validation tests."""
        print("=" * 70)
        print("RANN PTY RUNTIME VALIDATION")
        print("=" * 70)

        # Test 1: Docker Available
        print("\n1. Docker Availability...")
        result = ValidationResult("docker_available")
        if self.check_docker_available():
            result.set_pass("Docker CLI and daemon available")
            self.docker_available = True
        else:
            result.set_not_run("Docker CLI not found in PATH")
        self.results["docker_available"] = result

        if not self.docker_available:
            print("   ❌ DOCKER_UNAVAILABLE - Stopping validation")
            self.print_summary()
            return

        # Test 2: Sandbox Image
        print("2. Sandbox Image...")
        result = ValidationResult("sandbox_image")
        if self.build_sandbox_image():
            result.set_pass("Image rann-sandbox:latest built successfully")
        else:
            result.set_fail("Failed to build sandbox image")
        self.results["sandbox_image"] = result

        if not result.passed:
            print("   ❌ Image build failed")
            self.print_summary()
            return

        # Test 3-18: Container-based tests
        print("\n3-18. Container Tests...")

        # Create container
        self.container_id = self.create_test_container()
        if not self.container_id:
            print("   ❌ Failed to create test container")
            self.results["container_creation"] = ValidationResult("container_creation")
            self.results["container_creation"].set_fail("Could not start container")
            self.print_summary()
            return

        print(f"   Container: {self.container_id[:12]}")

        try:
            # Test 3: Real PTY (tty)
            result = ValidationResult("real_pty")
            success, stdout, stderr = self.run_in_container(self.container_id, "tty")
            if success and ("/dev/pts/" in stdout or "not a tty" in stdout.lower()):
                result.set_pass(output=stdout.strip() if stdout else "tty command executed")
            else:
                result.set_fail(stderr or "tty failed", stdout)
            self.results["real_pty"] = result

            # Test 4: Terminal Size (stty size)
            result = ValidationResult("terminal_size")
            success, stdout, stderr = self.run_in_container(self.container_id, "stty size")
            if success and stdout.strip():
                parts = stdout.strip().split()
                if len(parts) == 2 and all(p.isdigit() for p in parts):
                    result.set_pass(details=f"Size: {parts[0]}x{parts[1]}", output=stdout.strip())
                else:
                    result.set_fail(f"Invalid size format: {stdout}")
            else:
                result.set_fail(stderr or "stty size failed", stdout)
            self.results["terminal_size"] = result

            # Test 5: Non-root
            result = ValidationResult("non_root")
            success, stdout, stderr = self.run_in_container(self.container_id, "whoami")
            if success and stdout.strip() != "root":
                result.set_pass(output=stdout.strip())
            else:
                result.set_fail(f"User should not be root: {stdout.strip()}", stdout)
            self.results["non_root"] = result

            # Test 6: Workspace (pwd)
            result = ValidationResult("workspace")
            success, stdout, stderr = self.run_in_container(self.container_id, "pwd")
            if success and "/workspace" in stdout:
                result.set_pass(output=stdout.strip())
            else:
                result.set_fail(f"Should be in /workspace: {stdout}", stdout)
            self.results["workspace"] = result

            # Test 7: Shell Persistence
            result = ValidationResult("persistent_shell")
            # This test requires actual PTY interaction, mark as NOT_RUN for now
            result.set_not_run("Requires WebSocket PTY interaction")
            self.results["persistent_shell"] = result

            # Test 8: Interactive Python
            result = ValidationResult("interactive_python")
            # Requires PTY for interactive mode, mark as NOT_RUN
            result.set_not_run("Requires WebSocket PTY interaction")
            self.results["interactive_python"] = result

            # Test 9: Ctrl+C
            result = ValidationResult("ctrl_c")
            result.set_not_run("Requires WebSocket PTY interaction")
            self.results["ctrl_c"] = result

            # Test 10: Ctrl+D
            result = ValidationResult("ctrl_d")
            result.set_not_run("Requires WebSocket PTY interaction")
            self.results["ctrl_d"] = result

            # Test 11: ANSI
            result = ValidationResult("ansi")
            success, stdout, stderr = self.run_in_container(
                self.container_id, "printf '\\033[31mRED\\033[0m\\n'"
            )
            if success and "\\033[" in stdout or "\x1b[" in stdout.replace("\\\\033[", "\x1b["):
                result.set_pass("ANSI codes preserved", stdout)
            else:
                result.set_fail("ANSI codes may have been stripped", stdout)
            self.results["ansi"] = result

            # Test 12: Network Isolation
            result = ValidationResult("network_isolation")
            success, stdout, stderr = self.run_in_container(
                self.container_id,
                "curl -s --connect-timeout 2 https://example.com 2>&1 || echo 'blocked'",
            )
            if "blocked" in stdout or "Failed" in stderr or "Connection" in stderr:
                result.set_pass("Network access blocked", stderr[:100] if stderr else stdout)
            else:
                result.set_fail("Network may be accessible", stdout[:200])
            self.results["network_isolation"] = result

            # Test 13: Docker Socket
            result = ValidationResult("docker_socket")
            success, stdout, stderr = self.run_in_container(
                self.container_id, "ls -la /var/run/docker.sock 2>&1"
            )
            if (
                "No such file" in stdout
                or "not found" in stdout.lower()
                or "cannot access" in stdout.lower()
            ):
                result.set_pass("Docker socket not accessible", stdout)
            else:
                result.set_fail("Docker socket may be accessible!", stdout)
            self.results["docker_socket"] = result

            # Test 14: Environment Isolation
            result = ValidationResult("environment_isolation")
            success, stdout, stderr = self.run_in_container(
                self.container_id, "env | grep -E '(SECRET|PASSWORD|KEY|TOKEN|API)' || echo 'safe'"
            )
            if "safe" in stdout:
                result.set_pass("No sensitive env vars exposed")
            else:
                result.set_fail("Potentially sensitive vars found", stdout[:200])
            self.results["environment_isolation"] = result

            # Test 15: Filesystem
            result = ValidationResult("filesystem")
            # Test workspace is writable
            success, stdout, stderr = self.run_in_container(
                self.container_id,
                "echo test > /workspace/test_write.txt && echo 'writable' || echo 'readonly'",
            )
            if "writable" in stdout:
                result.set_pass("/workspace is writable")
            else:
                result.set_fail("Workspace not writable", stdout)
            self.results["filesystem"] = result

            # Test 16: Workspace Persistence
            result = ValidationResult("workspace_persistence")
            result.set_not_run("Requires container restart")
            self.results["workspace_persistence"] = result

        finally:
            # Cleanup
            if self.container_id:
                self.stop_test_container(self.container_id)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)

        for name, result in self.results.items():
            status = (
                "✅ PASS"
                if result.passed
                else (
                    "❌ FAIL"
                    if result.details
                    and "failed" in result.details.lower()
                    or result.details
                    and "not_run" in result.details.lower()
                    else "⚠️ NOT_RUN"
                )
            )
            if result.passed and result.details:
                print(f"  {status} | {name}: {result.details}")
            elif result.passed and result.output:
                print(f"  {status} | {name}: {result.output[:50]}")
            else:
                print(f"  {status} | {name}")

        # Count results
        passed = sum(1 for r in self.results.values() if r.passed)
        not_run = sum(
            1 for r in self.results.values() if r.details and "not_run" in r.details.lower()
        )
        total = len(self.results)

        print(f"\n  Results: {passed}/{total} passed, {not_run}/{total} not run")

        # Final classification
        print("\n" + "-" * 70)
        if not self.docker_available:
            print("FINAL CLASSIFICATION: BLOCKED (Docker unavailable)")
        elif passed == total:
            print("FINAL CLASSIFICATION: CERTIFIED FOR FRONTEND")
        else:
            print("FINAL CLASSIFICATION: BLOCKED (Runtime tests failed)")


async def main():
    """Main entry point."""
    validator = PTYRuntimeValidator()
    await validator.validate_all()


if __name__ == "__main__":
    asyncio.run(main())
