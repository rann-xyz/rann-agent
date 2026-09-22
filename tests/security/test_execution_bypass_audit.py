"""
Regression tests to ensure NO arbitrary execution bypasses ExecutionBackend.

These tests verify:
1. All arbitrary command execution goes through ExecutionBackend
2. No os.environ.copy() for execution
3. User identity always server-derived
4. Workspace always server-defined
"""

import asyncio
import inspect
import os
import sys

sys.path.insert(0, "/home/userland/rann-agent")

# ============================================================================
# STATIC ANALYSIS - Check for bypass patterns
# ============================================================================

print("="*70)
print("BYPASS PATH AUDIT - STATIC ANALYSIS")
print("="*70)

# Pattern 1: os.system usage
print("\n1. Checking for os.system() usage:")
print("-" * 40)

found_os_system = False
for root, dirs, files in os.walk('/home/userland/rann-agent/rann_agent'):
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath) as f:
                for line_num, line in enumerate(f, 1):
                    if 'os.system(' in line and 'nosec' not in line.lower():
                        print(f"  ⚠️ {filepath}:{line_num}: {line.strip()[:80]}")
                        found_os_system = True

if not found_os_system:
    print("  ✅ No os.system() found (excluding test comments)")

# Pattern 2: os.environ.copy() in execution context
print("\n2. Checking for os.environ.copy() in execution tools:")
print("-" * 40)

for filepath in [
    'rann_agent/execution/__init__.py',
    'rann_agent/tools/terminal.py',
    'rann_agent/tools/code_exec.py',
    'rann_agent/tools/real_terminal.py',
]:
    full_path = f'/home/userland/rann-agent/{filepath}'
    if os.path.exists(full_path):
        with open(full_path) as f:
            content = f.read()
            if 'os.environ.copy()' in content:
                print(f"  ⚠️ {filepath}: Contains os.environ.copy()")
            else:
                print(f"  ✅ {filepath}: No os.environ.copy()")

# Pattern 3: Direct asyncio subprocess in tools
print("\n3. Checking tools for direct subprocess execution:")
print("-" * 40)

execution_tools = [
    'rann_agent/tools/terminal.py',
    'rann_agent/tools/code_exec.py',
    'rann_agent/tools/real_terminal.py',
]

for filepath in execution_tools:
    full_path = f'/home/userland/rann-agent/{filepath}'
    if os.path.exists(full_path):
        with open(full_path) as f:
            content = f.read()
            # Check for subprocess calls
            if 'subprocess' in content.lower() or 'asyncio.create_subprocess' in content:
                # Check if it uses execution backend
                if 'ExecutionBackend' in content or 'execution_backend' in content: