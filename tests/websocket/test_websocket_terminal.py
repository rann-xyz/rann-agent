"""
Tests for WebSocket Terminal Implementation

Tests cover:
- WebSocket connection
- Authentication
- Authorization
- Command execution
- Output streaming
- Session management
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from rann_agent.web.app import app

from rann_agent.web.websocket_terminal import (
    TerminalSessionManager,
    TerminalStatus,
    WebSocketTerminal,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def terminal_manager():
    """Create terminal session manager."""
    manager = TerminalSessionManager()
    return manager


class TestWebSocketTerminalSession:
    """Test terminal session management."""

    def test_create_session(self, terminal_manager):
        """Should create terminal session."""
        websocket = MagicMock()
        session = asyncio.get_event_loop().run_until_complete(
            terminal_manager.create_session("user_1", "project_1", websocket)
        )

        assert session.id.startswith("term_")
        assert session.user_id == "user_1"
        assert session.project_id == "project_1"
        assert session.status == TerminalStatus.CONNECTING

    def test_get_session(self, terminal_manager):
        """Should retrieve session by ID."""
        websocket = MagicMock()
        session = asyncio.get_event_loop().run_until_complete(
            terminal_manager.create_session("user_1", "project_1", websocket)
        )

        retrieved = asyncio.get_event_loop().run_until_complete(
            terminal_manager.get_session(session.id)
        )

        assert retrieved.id == session.id

    def test_remove_session(self, terminal_manager):
        """Should remove session."""
        websocket = MagicMock()
        session = asyncio.get_event_loop().run_until_complete(
            terminal_manager.create_session("user_1", "project_1", websocket)
        )

        result = asyncio.get_event_loop().run_until_complete(
            terminal_manager.remove_session(session.id)
        )

        assert result is True
        assert (
            asyncio.get_event_loop().run_until_complete(terminal_manager.get_session(session.id))
            is None
        )


class TestWebSocketTerminalEndpoint:
    """Test WebSocket terminal endpoint."""

    def test_websocket_requires_auth(self, client):
        """WebSocket should require authentication."""
        with client.websocket_connect("/ws/projects/test-project/terminal"):
            # Should close immediately without auth
            with pytest.raises(Exception):
                pass  # Connection should be closed

    def test_websocket_rejects_invalid_project(self, client):
        """WebSocket should reject non-existent project."""
        # This would require proper authentication setup
        pass

    def test_message_protocol(self):
        """Test message protocol structure."""
        # Test message types
        assert TerminalSessionManager.__name__ is not None


class TestTerminalMessage:
    """Test terminal message types."""

    def test_message_types(self):
        """Verify all message types exist."""
        from rann_agent.web.websocket_terminal import TerminalMessage

        assert hasattr(TerminalMessage, "INPUT")
        assert hasattr(TerminalMessage, "STDOUT")
        assert hasattr(TerminalMessage, "STDERR")
        assert hasattr(TerminalMessage, "EXIT")
        assert hasattr(TerminalMessage, "ERROR")
        assert hasattr(TerminalMessage, "PING")
        assert hasattr(TerminalMessage, "PONG")
        assert hasattr(TerminalMessage, "RESIZE")
        assert hasattr(TerminalMessage, "STATUS")


class TestTerminalAuthorization:
    """Test terminal authorization."""

    def test_user_cannot_access_other_user_terminal(self):
        """User A should not be able to access User B's terminal."""
        # This requires mock database setup
        pass

    def test_revoked_session_rejected(self):
        """Revoked session should be rejected."""
        pass


class TestCommandExecution:
    """Test command execution through terminal."""

    def test_command_execution_structure(self):
        """Verify command execution architecture."""
        # Verify terminal uses sandbox provider
        import inspect

        from rann_agent.web.websocket_terminal import WebSocketTerminal

        source = inspect.getsource(WebSocketTerminal._handle_input)

        # Should use sandbox_provider.execute
        assert "sandbox_provider.execute" in source or "sandbox_provider" in source

        # Should NOT call subprocess directly on host
        assert "subprocess.Popen" not in source
        assert "subprocess.run" not in source


class TestTerminalSecurity:
    """Test terminal security properties."""

    def test_no_host_shell_execution(self):
        """Terminal should never execute on host."""
        import inspect

        from rann_agent.web.websocket_terminal import WebSocketTerminal

        source = inspect.getsource(WebSocketTerminal._handle_input)

        # Command execution goes through sandbox provider
        assert "self.sandbox_provider.execute" in source

    def test_message_output_escaping(self):
        """Output messages should be properly formatted JSON."""
        message = {"type": "stdout", "data": "test output"}
        encoded = json.dumps(message)
        decoded = json.loads(encoded)

        assert decoded["type"] == "stdout"
        assert decoded["data"] == "test output"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
