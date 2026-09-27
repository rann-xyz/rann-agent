# RANN Agent API Documentation

## Authentication

All API endpoints require authentication via session cookie.

### Login
```
POST /auth/login
Content-Type: application/json
Cookie: session=<session_id>

{
  "email": "user@example.com",
  "password": "secure_password"
}

Response: 200 OK
{
  "authenticated": true,
  "user": {
    "id": "user_xxx",
    "email": "user@example.com",
    "role": "user"
  }
}
```

### Session Validation
```
GET /auth/session
Cookie: session=<session_id>

Response:
{
  "authenticated": true,
  "user": {"id": "...", "email": "...", "role": "user"}
}
```

---

## Projects API

### Create Project
```
POST /api/projects
Authorization: Bearer <session_cookie>

Body:
{
  "name": "my-project"
}

Response: 200 OK
{
  "id": "proj_xxx",
  "name": "my-project",
  "workspace": "/workspace/proj_xxx",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### List Projects
```
GET /api/projects

Response: 200 OK
[
  {
    "id": "proj_xxx",
    "name": "my-project",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

---

## Terminal Session API

### Create Terminal Session
```
POST /api/projects/{project_id}/terminal/sessions

Response: 200 OK
{
  "id": "term_xxx",
  "project_id": "proj_xxx",
  "status": "created",
  "cols": 120,
  "rows": 32,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### WebSocket Terminal
```
ws://localhost:8000/ws/projects/{project_id}/terminal
Cookie: session=<session_id>
```

---

## Agent Session API

### Create Agent Session
```
POST /api/projects/{project_id}/agent/sessions

Response: 200 OK
{
  "id": "agent_xxx",
  "project_id": "proj_xxx",
  "status": "idle",
  "created_at": "2024-01-01T00:00:00Z",
  "config": {
    "workspace_path": "/workspace/proj_xxx"
  }
}
```

### Agent WebSocket Streaming
```
ws://localhost:8000/ws/projects/{project_id}/agent/{session_id}
Cookie: session=<session_id>
```

Client Messages:
```json
{ "type": "message", "message": "content here" }
{ "type": "cancel", "run_id": "run_xxx" }
```

Server Events:
```json
{ "type": "run_started", "run_id": "...", "message": "..." }
{ "type": "agent_state", "run_id": "...", "status": "thinking" }
{ "type": "tool_started", "run_id": "...", "tool": "read_file" }
{ "type": "tool_output", "run_id": "...", "data": "..." }
{ "type": "agent_message", "run_id": "...", "data": "..." }
{ "type": "file_changed", "run_id": "...", "path": "file.py" }
{ "type": "run_completed", "run_id": "..." }
{ "type": "run_failed", "run_id": "...", "error": "..." }
```

---

## File API

### List Directory
```
GET /api/projects/{project_id}/files?path=src
Response: 200 OK
{
  "path": "src",
  "entries": [
    {
      "path": "src/main.py",
      "name": "main.py",
      "type": "file",
      "size": 1234,
      "modified": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Read File
```
GET /api/projects/{project_id}/files/content?path=src/main.py
Response: 200 OK
{
  "path": "src/main.py",
  "content": "# Python code"
}
```

### Write File
```
PUT /api/projects/{project_id}/files/content
Body:
{
  "path": "src/main.py",
  "content": "# New content"
}
Response: 200 OK
{
  "path": "src/main.py",
  "size": 18,
  "modified": "2024-01-01T00:00:00Z"
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 401 | Authentication required |
| 403 | Access denied |
| 404 | Resource not found |
| 409 | Conflict (e.g., terminal already attached) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |