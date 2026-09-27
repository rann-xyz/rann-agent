#!/bin/bash
# RANN Agent Runtime Validation Script
# Run this script on a Docker-enabled machine

set -e

echo "========================================="
echo "RANN Agent Runtime Validation"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
NOT_RUN=0

pass() { echo -e "${GREEN}✓ PASS${NC} $1"; ((PASS++)); }
fail() { echo -e "${RED}✗ FAIL${NC} $1"; ((FAIL++)); }
not_run() { echo -e "${YELLOW}○ NOT_RUN${NC} $1"; ((NOT_RUN++)); }

echo ""
echo "1. DOCKER AVAILABILITY"
echo "----------------------"
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        pass "Docker daemon available"
        DOCKER_AVAILABLE=1
    else
        fail "Docker daemon not accessible"
        DOCKER_AVAILABLE=0
    fi
else
    not_run "Docker not installed"
    DOCKER_AVAILABLE=0
fi

echo ""
echo "2. BUILD SANDBOX IMAGE"
echo "----------------------"
if [ "$DOCKER_AVAILABLE" -eq 1 ]; then
    if [ -f "docker/sandbox/Dockerfile" ]; then
        if docker build -t rann-sandbox:latest docker/sandbox/ 2>&1 | grep -q "Successfully"; then
            pass "Sandbox image built"
        else
            fail "Sandbox image build failed"
        fi
    else
        not_run "Dockerfile not found"
    fi
else
    not_run "Docker unavailable"
fi

echo ""
echo "3. PTY VALIDATION"
echo "-----------------"
if [ "$DOCKER_AVAILABLE" -eq 1 ]; then
    # Test actual PTY in sandbox
    RESULT=$(docker run --rm rann-sandbox:latest sh -c 'tty && whoami && pwd && stty size' 2>&1)
    if echo "$RESULT" | grep -q "/dev/pts"; then
        pass "PTY exists (/dev/pts/*)"
    else
        fail "No PTY found"
    fi

    if echo "$RESULT" | grep -q "^nonroot$"; then
        pass "Non-root user (whoami)"
    else
        fail "Not running as non-root"
    fi

    if echo "$RESULT" | grep -q "^/workspace$"; then
        pass "Workspace directory (pwd)"
    else
        fail "Not in workspace"
    fi
else
    not_run "Docker unavailable"
fi

echo ""
echo "4. BACKEND API TESTS"
echo "--------------------"
if command -v pytest &> /dev/null; then
    echo "Running API tests..."
    if pytest tests/api/test_projects_files_terminal.py -v --tb=short 2>&1; then
        pass "Backend API tests"
    else
        fail "Backend API tests failed"
    fi
else
    not_run "pytest not installed"
fi

echo ""
echo "5. RUNTIME SANDBOX TESTS"
echo "------------------------"
if [ "$DOCKER_AVAILABLE" -eq 1 ]; then
    if pytest tests/runtime/test_terminal_runtime.py -v --tb=short 2>&1; then
        pass "Runtime terminal tests"
    else
        fail "Runtime terminal tests failed"
    fi
else
    not_run "Docker unavailable"
fi

echo ""
echo "6. SYMLINK SECURITY"
echo "--------------------"
if [ "$DOCKER_AVAILABLE" -eq 1 ]; then
    # Create symlink test
    RESULT=$(docker run --rm rann-sandbox:latest sh -c 'ln -s /etc/passwd /workspace/escape && ls -la /workspace/escape' 2>&1)
    echo "Symlink created in container: checking path resolution..."
    # In production, this would be tested against actual API
    echo -e "${YELLOW}○ NOT_RUN${NC} Requires running File API test"
    ((NOT_RUN++))
else
    not_run "Docker unavailable"
fi

echo ""
echo "========================================="
echo "SUMMARY"
echo "========================================="
echo -e "${GREEN}PASS:${NC} $PASS"
echo -e "${RED}FAIL:${NC} $FAIL"
echo -e "${YELLOW}NOT_RUN:${NC} $NOT_RUN"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo "Overall: $([ $DOCKER_AVAILABLE -eq 1 ] && echo "READY FOR PRODUCTION" || echo "NOT READY - Docker unavailable")"
else
    echo "Overall: NEEDS ATTENTION"
fi
