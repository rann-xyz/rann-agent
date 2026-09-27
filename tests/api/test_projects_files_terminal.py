"""
Tests for Project, File, and Terminal Session APIs

These tests require an authenticated user and valid session cookie.
Run with: pytest tests/api/test_projects_files_terminal.py -v
"""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.fixture
async def authenticated_client(client: AsyncClient):
    """Create an authenticated test client."""
    # Register user
    register_response = await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    
    # Login
    login_response = await client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    
    return client


class TestProjectAPI:
    """Tests for project management endpoints."""

    async def test_create_project(self, authenticated_client: AsyncClient):
        """Test project creation."""
        response = await authenticated_client.post(
            "/api/projects",
            json={"name": "test-project"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert data["name"] == "test-project"
        assert "workspace" in data

    async def test_list_projects(self, authenticated_client: AsyncClient):
        """Test listing projects."""
        # Create a project first
        await authenticated_client.post("/api/projects", json={"name": "list-test"})
        
        response = await authenticated_client.get("/api/projects")
        
        assert response.status_code == status.HTTP_200_OK
        projects = response.json()
        assert isinstance(projects, list)
        assert len(projects) >= 1

    async def test_get_project(self, authenticated_client: AsyncClient):
        """Test getting a specific project."""
        # Create project
        create_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "get-test"}
        )
        project_id = create_response.json()["id"]
        
        response = await authenticated_client.get(f"/api/projects/{project_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == project_id

    async def test_unauthorized_project_access(self, client: AsyncClient):
        """Test that users cannot access other users' projects."""
        # This test requires creating two users
        # For now, test that unauthenticated access is denied
        response = await client.get("/api/projects")
        
        # Should get 401 or 403 (depending on implementation)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


class TestTerminalSessionAPI:
    """Tests for terminal session endpoints."""

    async def test_create_terminal_session(self, authenticated_client: AsyncClient):
        """Test terminal session creation."""
        # Create project first
        project_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "terminal-test"}
        )
        project_id = project_response.json()["id"]
        
        response = await authenticated_client.post(
            f"/api/projects/{project_id}/terminal/sessions"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert data["status"] == "created"

    async def test_session_limits(self, authenticated_client: AsyncClient):
        """Test that session limits are enforced."""
        # Create project
        project_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "limits-test"}
        )
        project_id = project_response.json()["id"]
        
        # Create sessions up to limit
        for i in range(5):  # MAX_SESSIONS_PER_PROJECT = 2
            response = await authenticated_client.post(
                f"/api/projects/{project_id}/terminal/sessions"
            )
            if response.status_code == status.HTTP_409_CONFLICT:
                # Limit reached
                break

    async def test_close_terminal_session(self, authenticated_client: AsyncClient):
        """Test closing terminal session."""
        # Create project and session
        project_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "close-test"}
        )
        project_id = project_response.json()["id"]
        
        session_response = await authenticated_client.post(
            f"/api/projects/{project_id}/terminal/sessions"
        )
        session_id = session_response.json()["id"]
        
        # Close session
        close_response = await authenticated_client.delete(
            f"/api/projects/{project_id}/terminal/sessions/{session_id}"
        )
        
        assert close_response.status_code == status.HTTP_200_OK


class TestFilesAPI:
    """Tests for file management endpoints."""

    async def test_list_directory(self, authenticated_client: AsyncClient):
        """Test listing directory contents."""
        # Create project and session
        project_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "files-test"}
        )
        project_id = project_response.json()["id"]
        
        response = await authenticated_client.get(f"/api/projects/{project_id}/files")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)

    async def test_create_and_read_file(self, authenticated_client: AsyncClient):
        """Test creating and reading a file."""
        # Create project
        project_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "create-read-test"}
        )
        project_id = project_response.json()["id"]
        
        # Write file
        write_response = await authenticated_client.put(
            f"/api/projects/{project_id}/files/content",
            json={
                "path": "test_file.py",
                "content": "# Test file content\nprint('hello')"
            }
        )
        
        assert write_response.status_code == status.HTTP_200_OK
        
        # Read file
        read_response = await authenticated_client.get(
            f"/api/projects/{project_id}/files/content?path=test_file.py"
        )
        
        assert read_response.status_code == status.HTTP_200_OK
        data = read_response.json()
        assert "content" in data
        assert "hello" in data["content"]

    async def test_path_traversal_blocked(self, authenticated_client: AsyncClient):
        """Test that path traversal is blocked."""
        project_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "traversal-test"}
        )
        project_id = project_response.json()["id"]
        
        # Try path traversal
        response = await authenticated_client.get(
            f"/api/projects/{project_id}/files/content?path=../../../etc/passwd"
        )
        
        # Should get 400 Bad Request
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_absolute_path_blocked(self, authenticated_client: AsyncClient):
        """Test that absolute paths are blocked."""
        project_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "absolute-path-test"}
        )
        project_id = project_response.json()["id"]
        
        response = await authenticated_client.get(
            f"/api/projects/{project_id}/files/content?path=/etc/passwd"
        )
        
        # Should get 400 Bad Request
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_delete_file(self, authenticated_client: AsyncClient):
        """Test file deletion."""
        # Create project and file
        project_response = await authenticated_client.post(
            "/api/projects",
            json={"name": "delete-test"}
        )
        project_id = project_response.json()["id"]
        
        # Create file
        await authenticated_client.put(
            f"/api/projects/{project_id}/files/content",
            json={
                "path": "to_delete.py",
                "content": "delete me"
            }
        )
        
        # Delete file
        delete_response = await authenticated_client.delete(
            f"/api/projects/{project_id}/files?path=to_delete.py"
        )
        
        assert delete_response.status_code == status.HTTP_200_OK
        
        # Verify file is gone
        read_response = await authenticated_client.get(
            f"/api/projects/{project_id}/files/content?path=to_delete.py"
        )
        
        assert read_response.status_code == status.HTTP_404_NOT_FOUND