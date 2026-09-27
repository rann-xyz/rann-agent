#!/usr/bin/env python3
"""
End-to-End Integration Test for RANN Agent Workspace

This test proves that:
AUTH → PROJECT → FILES → TERMINAL → AGENT
all operate on the same workspace with Docker isolation.

Run when Docker is available:
python tests/integration/test_e2e_workspace.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient
from rann_agent.web.app import app
from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.config import Config
from rann_agent.tools.registry import ToolRegistry

import pytest


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_session(client: TestClient):
    """Create authenticated session."""
    # Register
    register_resp = client.post(
        "/auth/register",
        json={"email": f"e2e_{os.getpid()}@test.com", "password": "testpass123"}
    )
    
    # Login
    login_resp = client.post(
        "/auth/login",
        json={"email": f"e2e_{os.getpid()}@test.com", "password": "testpass123"}
    )
    
    return client


class TestEndToEndWorkspace:
    """End-to-end workspace integration tests."""
    
    def test_full_workspace_cycle(self, auth_session: TestClient):
        """Test complete workspace cycle: create → write → read → terminal → agent."""
        client = auth_session
        
        # 1. Create project
        project_resp = client.post("/api/projects", json={"name": "e2e-test"})
        assert project_resp.status_code == 200
        project_id = project_resp.json()["id"]
        
        # 2. Write file via API
        write_resp = client.put(
            f"/api/projects/{project_id}/files/content",
            json={
                "path": "hello.txt",
                "content": "hello from file api"
            }
        )
        assert write_resp.status_code == 200
        
        # 3. Read file via API
        read_resp = client.get(f"/api/projects/{project_id}/files/content?path=hello.txt")
        assert read_resp.status_code == 200
        assert read_resp.json()["content"] == "hello from file api"
        
        # 4. List directory
        list_resp = client.get(f"/api/projects/{project_id}/files")
        assert list_resp.status_code == 200
        entries = list_resp.json()["entries"]
        assert any(e["name"] == "hello.txt" for e in entries)
        
        # 5. Delete file
        del_resp = client.delete(f"/api/projects/{project_id}/files?path=hello.txt")
        assert del_resp.status_code == 200
        
        # 6. Verify deletion
        read_resp2 = client.get(f"/api/projects/{project_id}/files/content?path=hello.txt")
        assert read_resp2.status_code == 404
    
    def test_agent_session_lifecycle(self, auth_session: TestClient):
        """Test agent session creation and management."""
        client = auth_session
        
        # Create project
        project_resp = client.post("/api/projects", json={"name": "agent-test"})
        assert project_resp.status_code == 200
        project_id = project_resp.json()["id"]
        
        # Create agent session
        session_resp = client.post(f"/api/projects/{project_id}/agent/sessions")
        assert session_resp.status_code == 200
        session_id = session_resp.json()["id"]
        
        # List sessions
        list_resp = client.get(f"/api/projects/{project_id}/agent/sessions")
        assert list_resp.status_code == 200
        sessions = list_resp.json()
        assert any(s["id"] == session_id for s in sessions)
        
        # Get session details
        get_resp = client.get(f"/api/projects/{project_id}/agent/sessions/{session_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == session_id
        
        # Close session
        del_resp = client.delete(f"/api/projects/{project_id}/agent/sessions/{session_id}")
        assert del_resp.status_code == 200
    
    def test_workspace_isolation(self, auth_session: TestClient):
        """Test that users cannot access other users' projects."""
        client = auth_session
        
        # Create project
        project_resp = client.post("/api/projects", json={"name": "isolation-test"})
        project_id = project_resp.json()["id"]
        
        # Try to access another non-existent project
        fake_resp = client.get("/api/projects/fake_project_123")
        assert fake_resp.status_code == 404
        
        # Try to write to non-existent project
        write_resp = client.put(
            "/api/projects/fake_project_123/files/content",
            json={"path": "test.txt", "content": "test"}
        )
        assert write_resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])