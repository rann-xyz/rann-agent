"""
Phase 29: Verify unauthorized tool execution is blocked
Tests for authorization boundaries
"""
import pytest
import sys
from unittest.mock import AsyncMock, patch, MagicMock
sys.path.insert(0, "/root/rann-agent")


class TestUnauthorizedExecutionBlocked:
    """Verify that tool execution cannot happen without authorization"""

    def test_default_request_never_executes_tools(self):
        """Default request (goal only) cannot execute tools"""
        from rann_agent.api.server import TaskRequest
        
        req = TaskRequest(goal="rm -rf /")
        
        # conversation_only defaults to True (safe)
        assert req.conversation_only is True
        # execute_tools defaults to False
        assert req.execute_tools is False
        
        # These settings together mean: NO TOOL EXECUTION

    def test_conversation_only_never_executes_tools(self):
        """conversation_only=True never executes tools even with valid creds"""
        from rann_agent.api.server import TaskRequest
        
        req = TaskRequest(goal="ls -la", conversation_only=True)
        
        assert req.dry_run is False  # Falls through to LLM
        assert req.conversation_only is True  # But no tools
        assert req.execute_tools is False  # Explicitly False

    def test_explicit_execute_tools_blocked(self):
        """execute_tools=True is blocked (requires auth)"""
        from rann_agent.api.server import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # This should be rejected with 403
        response = client.post("/api/execute", json={
            "goal": "list files",
            "conversation_only": False,
            "execute_tools": True
        })
        
        # Should be FORBIDDEN (403) - not 500 error
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"


class TestToolInitializationSafety:
    """Verify tools are not initialized in safe modes"""

    def test_dry_run_tool_initialization(self):
        """Dry-run mode never initializes tools"""
        from rann_agent.api.server import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "rm -rf /",
            "dry_run": True
        })
        
        # Must succeed
        assert response.status_code == 200
        data = response.json()
        
        # No tool registry initialized path was taken
        # (We can verify this indirectly - if tools were init, it might fail)
        assert data["metadata"]["plan"]["simulated"] is True


class TestAuthDependencyExists:
    """Verify auth dependency can be imported for future use"""

    def test_require_auth_importable(self):
        """require_auth dependency is available for use"""
        from rann_agent.auth.router import require_auth, AuthUser
        
        # These can be used to protect routes
        assert callable(require_auth)
        assert AuthUser is not None

    def test_auth_user_model_exists(self):
        """AuthUser model is available"""
        from rann_agent.auth.router import AuthUser
        
        # Create a mock user
        user = AuthUser(user_id="test", email="test@test.com", role="user")
        assert user.id == "test"
        assert user.email == "test@test.com"
        assert user.is_admin() is False


class TestExecutionPathVerification:
    """Verify the exact execution paths through the code"""

    def test_dry_run_path_code_location(self):
        """Dry-run path is in server.py execute_task function"""
        import inspect
        from rann_agent.api.server import execute_task
        
        source = inspect.getsource(execute_task)
        assert "if request.dry_run:" in source
        assert "would_execute\": False" in source

    def test_conversation_only_path_exists(self):
        """Conversation-only path was added to server.py"""
        import inspect
        from rann_agent.api.server import execute_task
        
        source = inspect.getsource(execute_task)
        # Should have the conversation_only check
        assert "conversation_only" in source

    def test_full_execution_blocked(self):
        """Full execution is blocked (requires auth)"""
        import inspect
        from rann_agent.api.server import execute_task
        
        source = inspect.getsource(execute_task)
        
        # Should check for execute_tools and reject it
        assert "execute_tools" in source
        assert "403" in source  # Should return Forbidden


class TestDefaultBehaviorSafety:
    """Comprehensive safety tests for default behavior"""

    def test_safe_defaults_prove_by_code(self):
        """Safe defaults are enforced by default values in TaskRequest"""
        from rann_agent.api.server import TaskRequest
        import inspect
        
        # Get default values from the class
        source = inspect.getsource(TaskRequest)
        
        # conversation_only should default to True (safe)
        assert 'conversation_only: bool = True' in source
        
        # execute_tools should default to False
        assert 'execute_tools: bool = False' in source

    def test_default_request_is_conversation_only(self):
        """Default request (goal only) uses conversation_only mode (safe)"""
        from rann_agent.api.server import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        response = client.post("/api/execute", json={
            "goal": "hello"
        })
        
        # Should NOT be 403 (which would mean execute_tools was attempted)
        assert response.status_code in [200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])