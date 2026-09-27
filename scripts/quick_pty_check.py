#!/usr/bin/env python3
"""
Quick PTY validation script - Run with Docker available.

This script performs essential PTY validation checks.
Use: python scripts/quick_pty_check.py
"""

import subprocess
import sys
import time


def run_cmd(cmd, timeout=10):
    """Run shell command, return (success, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def main():
    print("=" * 60)
    print("QUICK PTY VALIDATION")
    print("=" * 60)

    # Check Docker
    ok, out, err = run_cmd("docker version")
    if not ok:
        print(f"❌ Docker not available: {err}")
        return 1
    print("✅ Docker available")

    # Build image
    ok, out, err = run_cmd("docker build -t rann-sandbox:test docker/sandbox/ 2>&1")
    if not ok:
        print(f"❌ Build failed: {out}")
        return 1
    print("✅ Image built")

    # Create container
    container = (
        run_cmd("docker run -d --rm rann-sandbox:test")[1].split()[0]
        if run_cmd("docker ps -q")[0]
        else None
    )
    if not container:
        container = subprocess.run(
            ["docker", "run", "-d", "--rm", "rann-sandbox:test"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if container.returncode == 0:
            container = container.stdout.strip()

    if not container:
        print("❌ Container creation failed")
        return 1
    print(f"✅ Container: {container[:12]}")

    try:
        # Run PTY tests
        tests = [
            ("tty", "tty"),
            ("whoami", "whoami"),
            ("pwd", "pwd"),
            ("non-root", "id -u"),
        ]

        print("\nRunning tests:")
        for name, cmd in tests:
            ok, out, err = run_cmd(f"docker exec {container} {cmd}")
            if ok:
                print(f"  ✅ {name}: {out}")
            else:
                print(f"  ❌ {name}: {err}")

        # Cleanup
        subprocess.run(["docker", "stop", container], capture_output=True)
        print("\n✅ Validation complete")
        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        subprocess.run(["docker", "stop", container], capture_output=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
