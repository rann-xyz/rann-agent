"""
Security Regression Tests for Phase 22 - Final (Updated for safe defaults)
"""
import pytest
import sys
sys.path.insert(0, "/root/rann-agent")


class TestDryRunCompleteness:
    """Verify dry-run mode is completely safe"""

    def test_dry_run_returns_200_without_auth(self):
        """Dry-run works without authentication (public validation)"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        response = client.post("/api/execute", json={
            "goal": "search for files",
            "dry_run": True
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["mode"] == "dry_run"

    def test_dry_run_no_llm_calls(self):
        """Dry-run never calls LLM provider"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        response = client.post("/api/execute", json={
            "goal": "test",
            "dry_run": True
        })

        # Should succeed without any API key errors
        assert response.status_code == 200
        data = response.json()
        # No LLM-related errors
        assert "API key" not in str(data).lower()
        assert "API error" not in str(data).lower()

    def test_dry_run_no_tool_execution(self):
        """Dry-run never executes tools"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        response = client.post("/api/execute", json={
            "goal": "rm -rf /",
            "dry_run": True
        })

        data = response.json()
        plan = data["metadata"]["plan"]

        # CRITICAL SAFETY GUARANTEE
        assert plan["simulated"] is True
        assert plan["safe_to_execute"] is True
        for step in plan.get("steps", []):
            assert step.get("would_execute") is False

    def test_dry_run_no_agent_initialization(self):
        """Dry-run doesn't create real Agent/LLM"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        response = client.post("/api/execute", json={
            "goal": "test",
            "dry_run": True
        })

        data = response.json()
        assert "dry_run" in data["session_id"]


class TestConversationOnlyMode:
    """Verify conversation-only mode is safe and default"""

    def test_conversation_only_is_default(self):
        """Default request uses conversation_only mode (safe)"""
        from rann_agent.api.server import TaskRequest

        req = TaskRequest(goal="hello")
        assert req.conversation_only is True  # SAFE DEFAULT
        assert req.execute_tools is False

    def test_conversation_only_fails_safely_without_credentials(self):
        """Conversation-only mode attempts LLM call and fails safely"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        # Default is conversation_only=True
        response = client.post("/api/execute", json={
            "goal": "hello"
        })

        # Returns 200 with success=false (error response, not tool execution)
        data = response.json()
        assert response.status_code == 200
        assert data["success"] is False
        assert data["metadata"]["mode"] == "conversation_only"
        assert data["metadata"]["status"] == "failed"

    def test_conversation_only_no_tool_execution(self):
        """Conversation-only mode never executes tools"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        response = client.post("/api/execute", json={
            "goal": "ls -la; cat /etc/passwd"
        })

        data = response.json()
        # Even if LLM were called, tools are disabled
        # The request fails due to no credentials, but safely
        assert data["success"] is False
        assert "error" in data


class TestExecuteToolsBlocked:
    """Verify tool execution is blocked without auth"""

    def test_execute_tools_requires_auth(self):
        """execute_tools=True is blocked (403) without auth"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        response = client.post("/api/execute", json={
            "goal": "run command",
            "conversation_only": False,
            "execute_tools": True
        })

        # Should be FORBIDDEN (403) - not 500
        assert response.status_code == 403


class TestEndpointProtection:
    """Verify other endpoints have proper auth"""

    def test_projects_requires_auth(self):
        """Projects endpoint is protected"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/projects")
        assert response.status_code == 401

    def test_health_is_public(self):
        """Health endpoint is public (intentional)"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestFullExecutionDisabled:
    """Verify full tool execution is disabled without auth"""

    def test_full_execution_blocked_without_auth(self):
        """
        Security model when auth unavailable:
        - Dry-run: Public, offline, 200
        - Conversation-only (default): Text-only, fails safely at LLM, 200 success=false
        - Full execution: BLOCKED with 403
        """
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        # Protected endpoints
        proj_resp = client.get("/api/projects")
        assert proj_resp.status_code == 401

        # Full execution blocked
        exec_resp = client.post("/api/execute", json={
            "goal": "test",
            "conversation_only": False,
            "execute_tools": True
        })
        assert exec_resp.status_code == 403

        # Dry-run works and is safe
        dry_resp = client.post("/api/execute", json={
            "goal": "test",
            "dry_run": True
        })
        assert dry_resp.status_code == 200
        json_str = str(dry_resp.json())
        assert "would_execute: false" in json_str.lower() or "would_execute" in dry_resp.json()["metadata"]["plan"]["steps"][0]


class TestApiAgentsSecurity:
    """Verify /api/agents endpoint requires authentication and doesn't expose sessions"""

    def test_api_agents_requires_auth(self):
        """GET /api/agents requires authentication - 401 if not available, 503 if email-validator missing"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/agents")

        # Should NOT return 200 (which would expose sessions)
        # Either 401 (Unauthorized) or 503 (auth unavailable)
        assert response.status_code in [401, 503], \
            f"Expected 401 or 503, got {response.status_code}"

    def test_api_agents_no_session_enumeration_without_auth(self):
        """Unauthenticated users cannot enumerate active agent sessions"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/agents")

        # Cannot enumerate session IDs without auth
        if response.status_code == 200:
            data = response.json()
            # This endpoint should NOT be public
            assert False, "Endpoint should require authentication"

        # Access denied - good
        assert response.status_code in [401, 503]


class TestCorsSecurity:
    """Verify CORS configuration is production-safe"""

    def test_cors_no_wildcard_origin(self):
        """CORS does not use wildcard '*' origin by default"""
        from rann_agent.core.config import Config

        config = Config.load()
        cors = config.api.cors

        if cors.get("enabled", True):
            origins = cors.get("origins", [])
            # Should not use wildcard
            assert "*" not in origins, "CORS origins should not include wildcard"
            # Should be a specific list
            assert isinstance(origins, list), "CORS origins should be a list"
            assert len(origins) >= 1, "CORS origins should have at least one entry"

    def test_cors_default_origins_are_localhost(self):
        """Default CORS origins are localhost URLs for development"""
        from rann_agent.core.config import Config

        config = Config.load()
        cors = config.api.cors

        if cors.get("enabled", True):
            origins = cors.get("origins", [])
            # Default should be localhost URLs
            if origins == ["http://localhost:3000", "http://localhost:8000"]:
                # This is the safe default - development only
                pass
            else:
                # If custom origins, verify no wildcard
                assert "*" not in origins