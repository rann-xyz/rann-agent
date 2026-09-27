#!/usr/bin/env python3
"""Docker availability probe for CI workflows."""

import subprocess
import sys


def check_docker():
    """Check if Docker is available. Returns True if available, False otherwise."""
    try:
        result = subprocess.run(["docker", "version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Docker available")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    print("⚠️ Docker not available - some tests will be skipped")
    return False


if __name__ == "__main__":
    available = check_docker()
    sys.exit(0 if available else 1)
