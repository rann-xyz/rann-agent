"""
File API Router for RANN Agent

Provides secure project-relative file operations:
- List directories
- Read files
- Write files
- Create files/directories
- Rename/move files
- Delete files

All operations:
- Require authentication
- Enforce project ownership
- Validate workspace boundaries
- Return 404 for unowned projects (no information leakage)
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from rann_agent.auth.router import AuthUser, get_current_user
from rann_agent.storage.database import Database
from rann_agent.core.security import WorkspaceGuard, WorkspaceSecurity

logger = structlog.get_logger()

# Configuration
MAX_FILE_SIZE_BYTES = int(os.environ.get("MAX_FILE_SIZE_BYTES", 10485760))  # 10MB default
MAX_DIRECTORY_ENTRIES = int(os.environ.get("MAX_DIRECTORY_ENTRIES", 1000))

router = APIRouter(prefix="/api", tags=["files"])


class FileEntry:
    """File/directory entry response."""
    def __init__(self, path: str, name: str, type: str, size: int = 0, modified: str = ""):
        self.path = path
        self.name = name
        self.type = type
        self.size = size
        self.modified = modified
    
    def dict(self):
        return {
            "path": self.path,
            "name": self.name,
            "type": self.type,
            "size": self.size,
            "modified": self.modified,
        }


@router.get("/projects/{project_id}/files")
async def list_directory(
    project_id: str,
    path: str = "",
    user: AuthUser = Depends(get_current_user),
):
    """List directory contents."""
    # Verify project ownership
    db = Database()
    project = db._get_conn().execute(
        "SELECT id, owner_id, workspace_path FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    workspace = Path(project["workspace_path"])
    
    try:
        # Validate path is within workspace
        workspace_root = WorkspaceGuard(workspace)
        target_path = workspace_root.validate_path(path) if path else workspace
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        
        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="Not a directory")
        
        entries = []
        for entry in target_path.iterdir():
            # Skip hidden files
            if entry.name.startswith('.'):
                continue
            
            entry_type = "directory" if entry.is_dir() else "file"
            stat = entry.stat()
            
            rel_path = str(entry.relative_to(workspace))
            
            entries.append(FileEntry(
                path=rel_path,
                name=entry.name,
                type=entry_type,
                size=stat.st_size if entry_type == "file" else 0,
                modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            ).dict())
        
        return {
            "path": path,
            "entries": entries,
        }
        
    except ValueError as e:
        if "traversal" in str(e).lower() or "escape" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid path")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("list_directory_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list directory")


@router.get("/projects/{project_id}/files/content")
async def read_file(
    project_id: str,
    path: str,
    user: AuthUser = Depends(get_current_user),
):
    """Read file contents."""
    db = Database()
    project = db._get_conn().execute(
        "SELECT id, owner_id, workspace_path FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    workspace = Path(project["workspace_path"])
    
    try:
        workspace_root = WorkspaceGuard(workspace)
        file_path = workspace_root.validate_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")
        
        # Check file size
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Read file content
        content = file_path.read_text()
        
        return {
            "path": path,
            "content": content,
            "raw_path": str(file_path),  # Internal use only
        }
        
    except ValueError as e:
        if "traversal" in str(e).lower() or "escape" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid path")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("read_file_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to read file")


@router.put("/projects/{project_id}/files/content")
async def write_file(
    project_id: str,
    path: str,
    content: str,
    user: AuthUser = Depends(get_current_user),
):
    """Create or update file content."""
    db = Database()
    project = db._get_conn().execute(
        "SELECT id, owner_id, workspace_path FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check content size
    content_size = len(content.encode('utf-8'))
    if content_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Content too large")
    
    workspace = Path(project["workspace_path"])
    
    try:
        workspace_root = WorkspaceGuard(workspace)
        file_path = workspace_root.validate_path(path)
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        file_path.write_text(content)
        
        now = datetime.now(timezone.utc).isoformat()
        
        logger.info("file_written", user_id=user.id, project_id=project_id, path=path)
        
        return {
            "path": path,
            "size": content_size,
            "modified": now,
        }
        
    except ValueError as e:
        if "traversal" in str(e).lower() or "escape" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid path")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("write_file_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to write file")


@router.post("/projects/{project_id}/files")
async def create_file(
    project_id: str,
    path: str,
    is_directory: bool = False,
    content: Optional[str] = None,
    user: AuthUser = Depends(get_current_user),
):
    """Create a file or directory."""
    db = Database()
    project = db._get_conn().execute(
        "SELECT id, owner_id, workspace_path FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    workspace = Path(project["workspace_path"])
    
    try:
        workspace_root = WorkspaceGuard(workspace, allow_create=True)
        target_path = workspace_root.validate_path(path)
        
        if is_directory:
            target_path.mkdir(parents=True, exist_ok=True)
        else:
            # Create parent directories
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create empty file
            target_path.touch()
            
            # Write initial content if provided
            if content is not None:
                content_size = len(content.encode('utf-8'))
                if content_size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="Content too large")
                target_path.write_text(content)
        
        logger.info("file_created", user_id=user.id, project_id=project_id, path=path)
        
        return {"success": True, "path": path}
        
    except ValueError as e:
        if "traversal" in str(e).lower() or "escape" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid path")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("create_file_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create file")


@router.patch("/projects/{project_id}/files")
async def rename_move_file(
    project_id: str,
    path: str,
    new_path: str,
    user: AuthUser = Depends(get_current_user),
):
    """Rename or move a file."""
    db = Database()
    project = db._get_conn().execute(
        "SELECT id, owner_id, workspace_path FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    workspace = Path(project["workspace_path"])
    
    try:
        workspace_root = WorkspaceGuard(workspace)
        
        # Validate source path
        source_path = workspace_root.validate_path(path)
        
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Validate destination path
        dest_path = workspace_root.validate_path(new_path)
        
        # Check destination doesn't exist
        if dest_path.exists():
            raise HTTPException(status_code=409, detail="Destination already exists")
        
        # Rename/move
        source_path.rename(dest_path)
        
        logger.info("file_renamed", user_id=user.id, project_id=project_id, path=path, new_path=new_path)
        
        return {"success": True}
        
    except ValueError as e:
        if "traversal" in str(e).lower() or "escape" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid path")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("rename_file_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to rename file")


@router.delete("/projects/{project_id}/files")
async def delete_file(
    project_id: str,
    path: str,
    user: AuthUser = Depends(get_current_user),
):
    """Delete a file or directory."""
    db = Database()
    project = db._get_conn().execute(
        "SELECT id, owner_id, workspace_path FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    workspace = Path(project["workspace_path"])
    
    try:
        workspace_root = WorkspaceGuard(workspace)
        target_path = workspace_root.validate_path(path)
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if target_path.is_dir():
            import shutil
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
        
        logger.info("file_deleted", user_id=user.id, project_id=project_id, path=path)
        
        return {"success": True}
        
    except ValueError as e:
        if "traversal" in str(e).lower() or "escape" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid path")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("delete_file_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete file")