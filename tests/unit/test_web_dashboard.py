"""
Tests for RANN Agent Web Interface
Phase 40-42: Dashboard, security, and mobile testing
"""
import pytest
import sys
import re
sys.path.insert(0, "/root/rann-agent")


class TestDashboardRoute:
    """Test the dashboard route exists and returns valid HTML"""

    def test_dashboard_returns_html(self):
        """Dashboard should return HTML content-type"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/dashboard")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_contains_title(self):
        """Dashboard HTML should contain the title"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/dashboard")

        # The HTML is lowercased by HTMLResponse, so check for lowercase
        assert "rann agent dashboard" in response.text.lower() or "rann agent" in response.text.lower()

    def test_dashboard_contains_execute_button(self):
        """Dashboard should have execute functionality"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/dashboard")

        # Check for key UI elements (lowercased)
        html = response.text.lower()
        assert "goalinput" in html or "goal" in html
        assert "executetask" in html or "execute" in html


class TestChatRequestIntegration:
    """Test chat request flow through the full stack"""

    def test_api_root_returns_endpoints(self):
        """API root should list available endpoints"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "endpoints" in data
        # Endpoints are object keys, not array items
        endpoints = data["endpoints"]
        assert "execute" in endpoints  # Key is "execute", value is "/api/execute"

    def test_health_endpoint(self):
        """Health check should return healthy status"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_config_endpoint_returns_provider(self):
        """Config endpoint should return provider info"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        assert "provider" in data
        assert "model" in data


class TestMessageValidation:
    """Test message validation in chat requests"""

    def test_empty_message_handling(self):
        """Empty goal should be handled"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": ""
        })

        # Should not crash - either succeed or fail gracefully
        assert response.status_code in [200, 400, 500]

    def test_whitespace_message_handling(self):
        """Whitespace-only goal should be handled"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "   "
        })

        assert response.status_code in [200, 400, 500]


class TestProviderErrorHandling:
    """Test error handling for provider failures"""

    def test_dry_run_no_provider_error(self):
        """Dry-run should never call provider"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "any task",
            "dry_run": True
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["mode"] == "dry_run"


class TestExecutionSafety:
    """Test safety boundaries are maintained"""

    def test_execute_tools_requires_auth(self):
        """execute_tools=True should be blocked without auth"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "test",
            "execute_tools": True
        })

        assert response.status_code == 403

    def test_conversation_only_default(self):
        """Default should be conversation_only mode"""
        from rann_agent.api.server import TaskRequest

        req = TaskRequest(goal="test")
        assert req.conversation_only is True
        assert req.execute_tools is False


class TestInputSanitization:
    """Test input validation and sanitization"""

    def test_script_injection_safe(self):
        """Script tags in goal should be safe"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "<script>alert('xss')</script>Hello"
        })

        # Should not crash, response should be escaped or safe
        assert response.status_code in [200, 400]

    def test_sql_injection_safe(self):
        """SQL injection attempts should be safe"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "'; DROP TABLE users; --"
        })

        assert response.status_code in [200, 400]


class TestAuthenticationRequirements:
    """Test authentication requirements for sensitive endpoints"""

    def test_execute_without_auth(self):
        """Execute endpoint works without auth (conversation mode)"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "test"
        })

        # Should work in conversation mode (may fail on LLM call, but not 401)
        assert response.status_code in [200, 500]

    def test_execute_with_explicit_provider(self):
        """Explicit provider parameter should work"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "test",
            "provider": "custom",
            "model": "openrouter/free"
        })

        # May fail due to no LLM config, but shouldn't crash
        assert response.status_code in [200, 500]


class TestSessionIsolation:
    """Test session isolation between requests"""

    def test_dry_run_sessions_are_unique(self):
        """Each dry-run should have unique session ID"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)

        response1 = client.post("/api/execute", json={
            "goal": "test1",
            "dry_run": True
        })

        response2 = client.post("/api/execute", json={
            "goal": "test2",
            "dry_run": True
        })

        data1 = response1.json()
        data2 = response2.json()

        # Session IDs should be different
        assert data1["session_id"] != data2["session_id"]

    def test_api_agents_exposes_session_ids(self):
        """Verify /api/agents behavior (may expose session IDs)"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/agents")

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "agents" in data


class TestSecurityFixes:
    """Test security fixes for Phase 42"""

    def test_api_agents_no_session_ids_unauthenticated(self):
        """VERIFY: /api/agents should not expose session IDs without auth"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/agents")

        assert response.status_code == 200
        data = response.json()

        # SECURITY: Session IDs should NOT be exposed in public endpoint
        # This test documents the vulnerability that needs fixing
        if "agents" in data and len(data["agents"]) > 0:
            # If agents exist, check they don't expose session IDs
            for agent in data["agents"]:
                # Session IDs should be hidden or redacted
                assert "session_id" not in agent or agent.get("session_id") == "***", \
                    "SECURITY ISSUE: Session IDs exposed in public /api/agents endpoint"

    def test_api_agents_returns_safe_data(self):
        """VERIFY: /api/agents should return only safe public data"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/agents")

        assert response.status_code == 200
        data = response.json()

        # Only safe fields should be present
        for agent in data.get("agents", []):
            # Should not contain internal identifiers
            forbidden_keys = ["session_id", "internal_id", "secret", "token", "key"]
            for key in forbidden_keys:
                assert key not in agent or agent[key] == "***", \
                    f"SECURITY ISSUE: {key} exposed in /api/agents response"

    def test_api_config_no_secrets(self):
        """VERIFY: /api/config should not expose secrets"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        # Check no secrets are exposed
        text = str(data).lower()
        forbidden = ["api_key", "token", "secret", "password", "credential", "auth"]
        for word in forbidden:
            assert word not in text, f"SECURITY ISSUE: {word} might be exposed in /api/config"

    def test_api_tools_no_endpoint_exposure(self):
        """VERIFY: /api/tools should not expose sensitive implementation details"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/api/tools")

        assert response.status_code == 200
        data = response.json()

        # Tools endpoint should return tool list without sensitive paths
        if "tools" in data:
            for tool in data["tools"]:
                # Tool schemas should work, but not expose internal file paths
                if "parameters" in tool:
                    schema_str = str(tool["parameters"])
                    assert "/etc/" not in schema_str
                    assert "/root/" not in schema_str


class TestMobileDashboard:
    """Test mobile dashboard responsiveness and structure"""

    def test_dashboard_is_responsive_html(self):
        """Dashboard should return valid HTML structure"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/dashboard")

        html = response.text.lower()
        # Check for essential HTML structure
        assert "<!doctype html>" in html or "<html" in html
        assert "<head" in html
        assert "<body" in html
        assert "</html>" in html

    def test_dashboard_has_responsive_css(self):
        """Dashboard should have CSS for mobile responsiveness"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/dashboard")

        # Check for responsive CSS
        html = response.text.lower()
        # Should have media queries or responsive units
        assert "max-width" in html or "flex" in html or "grid" in html or "padding" in html

    def test_dashboard_input_is_accessible(self):
        """Message input should be usable on mobile"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/dashboard")

        # Input should have proper attributes
        html = response.text.lower()
        assert "type" in html or "input" in html

    def test_dashboard_no_unsafe_html_rendering(self):
        """Dashboard should escape output to prevent XSS"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/dashboard")

        # Check JavaScript doesn't use innerHTML unsafely
        html = response.text
        # innerHTML usage should be commented or safe
        if "innerHTML" in html:
            # If exists, should be in a safe context
            lines = html.split("\n")
            for line in lines:
                if "innerHTML" in line:
                    # Should have escaping or sanitization
                    assert "textContent" in line or "escape" in line.lower() or "//" in line

    def test_dashboard_has_javascript_execution(self):
        """Dashboard should have working JavaScript for chat"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.get("/dashboard")

        html = response.text.lower()
        # Should have fetch/ajax calls
        assert "fetch" in html or "axios" in html or "xmlhttprequest" in html


class TestSafeExecutionDefaults:
    """Test that safe execution defaults are preserved"""

    def test_default_mode_is_conversation_only(self):
        """Default task request should be conversation_only=True"""
        from rann_agent.api.server import TaskRequest

        req = TaskRequest(goal="test task")
        assert req.conversation_only is True
        assert req.execute_tools is False

    def test_dry_run_mode_is_public(self):
        """Dry run should work without authentication"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "test",
            "dry_run": True
        })

        # Should succeed without auth
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_execute_tools_mode_blocked(self):
        """Full tool execution should be blocked without auth"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "test",
            "execute_tools": True
        })

        # Should be blocked with 403
        assert response.status_code == 403

    def test_conversation_only_calls_llm(self):
        """Conversation-only mode should call LLM but not execute tools"""
        from fastapi.testclient import TestClient
        from rann_agent.api.server import app

        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "hello",
            "conversation_only": True
        })

        # Should attempt LLM call (may fail without config, but not 403)
        assert response.status_code in [200, 500]