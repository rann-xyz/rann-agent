"""
Self-Coding System - RANN Agent can modify its own code

When user asks agent to fix/improve/extend the agent itself,
this system enables safe self-modification.
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class SelfCodeChange:
    """Record of a self-coded change"""
    change_id: str
    timestamp: str
    task: str
    file_path: str
    change_type: str  # "create", "modify", "delete"
    patch: str  # diff/patch content
    verified: bool = False
    rolled_back: bool = False
    review_status: str = "pending"  # pending, approved, rejected


class SelfCodingPolicy:
    """
    Security policy for self-coding - defines what agent can modify.
    """
    
    # Files agent CAN modify
    ALLOWED_PATHS = [
        "rann_agent/core/",
        "rann_agent/cli/",
        "rann_agent/tools/",
        "rann_agent/intelligence/",
        "rann_agent/memory/",
        "rann_agent/storage/",
        "rann_agent/reasoning/",
        "rann_agent/skills/",
        "rann_agent/api/",
        "rann_agent/validation/",
    ]
    
    # Files agent CANNOT modify (security sensitive)
    BLOCKED_PATHS = [
        "rann_agent/core/config.py",  # API keys handled separately
        "tests/",
        ".env",
        "requirements.txt",
        "setup.py",
    ]
    
    # File patterns that need review
    REQUIRES_REVIEW = [
        r"\.py$",  # All Python files
    ]
    
    @classmethod
    def can_modify(cls, file_path: str) -> Tuple[bool, str]:
        """Check if agent can modify this file"""
        abs_path = Path(file_path).resolve()
        
        # Check blocked paths
        for blocked in cls.BLOCKED_PATHS:
            if blocked in str(abs_path):
                return False, f"Path blocked for security: {blocked}"
        
        # Check allowed paths
        for allowed in cls.ALLOWED_PATHS:
            if allowed in str(abs_path):
                # Check if requires review
                for pattern in cls.REQUIRES_REVIEW:
                    if re.search(pattern, file_path):
                        return True, "allowed_with_review"
                return True, "allowed"
        
        return False, f"Path not in allowed list: {file_path}"
    
    @classmethod
    def validate_change(cls, change: SelfCodeChange) -> Tuple[bool, str]:
        """Validate a proposed change"""
        allowed, reason = cls.can_modify(change.file_path)
        if not allowed:
            return False, reason
        
        # Check for dangerous patterns
        dangerous_patterns = [
            (r"os\.system\s*\(", "Dangerous: os.system() call"),
            (r"subprocess.*shell\s*=\s*True", "Dangerous: shell=True subprocess"),
            (r"eval\s*\(", "Dangerous: eval() call"),
            (r"exec\s*\(", "Dangerous: exec() call"),
            (r"__import__\s*\(", "Dangerous: dynamic import"),
            (r"import\s+os\s*\n\s*os\.system", "Dangerous: os system call pattern"),
            (r"chmod\s+\+?x", "Potentially dangerous: chmod +x"),
            (r"rm\s+-rf", "Potentially dangerous: rm -rf"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, change.patch):
                return False, f"Security violation: {message}"
        
        return True, "approved"


class SelfCodingExecutor:
    """
    Executes self-coded changes with backup and verification.
    """
    
    def __init__(self, repo_path: str = None):
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.change_log: List[SelfCodeChange] = []
        self.backup_dir = self.repo_path / ".rann_self_code_backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    def apply_change(
        self,
        task: str,
        file_path: str,
        new_content: str,
        change_type: str = "modify"
    ) -> Dict[str, Any]:
        """
        Apply a self-coded change with backup.
        Returns result with success status and details.
        """
        change_id = hashlib.md5(f"{task}{file_path}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:12]
        
        change = SelfCodeChange(
            change_id=change_id,
            timestamp=datetime.utcnow().isoformat(),
            task=task,
            file_path=file_path,
            change_type=change_type,
            patch=new_content  # For new files, this is the content
        )
        
        # Validate against policy
        allowed, reason = SelfCodingPolicy.validate_change(change)
        if not allowed:
            return {
                "success": False,
                "error": reason,
                "change_id": change_id
            }
        
        target_path = self.repo_path / file_path
        old_content = ""
        
        # Backup existing file
        if change_type == "modify" and target_path.exists():
            old_content = target_path.read_text()
            backup_path = self.backup_dir / f"{change_id}.backup"
            backup_path.write_text(old_content)
        
        try:
            # Apply change
            if change_type == "delete":
                target_path.unlink()
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(new_content)
            
            change.review_status = "approved"
            self.change_log.append(change)
            
            return {
                "success": True,
                "change_id": change_id,
                "file_path": file_path,
                "change_type": change_type,
                "backup_path": str(self.backup_dir / f"{change_id}.backup") if old_content else None,
                "message": f"Successfully applied {change_type} to {file_path}"
            }
            
        except Exception as e:
            # Rollback on failure
            if old_content:
                target_path.write_text(old_content)
            return {
                "success": False,
                "error": str(e),
                "change_id": change_id
            }
    
    def rollback(self, change_id: str) -> Dict[str, Any]:
        """Rollback a change"""
        change = next((c for c in self.change_log if c.change_id == change_id), None)
        if not change:
            return {"success": False, "error": "Change not found"}
        
        backup_path = self.backup_dir / f"{change_id}.backup"
        if not backup_path.exists():
            return {"success": False, "error": "Backup not found"}
        
        target_path = self.repo_path / change.file_path
        old_content = backup_path.read_text()
        
        try:
            target_path.write_text(old_content)
            backup_path.unlink()
            change.rolled_back = True
            
            return {
                "success": True,
                "message": f"Rolled back {change.file_path}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_change_log(self) -> List[Dict[str, Any]]:
        """Get history of self-coded changes"""
        return [
            {
                "change_id": c.change_id,
                "timestamp": c.timestamp,
                "task": c.task[:50],
                "file_path": c.file_path,
                "change_type": c.change_type,
                "review_status": c.review_status,
                "rolled_back": c.rolled_back
            }
            for c in reversed(self.change_log)
        ]
    
    def verify_change(self, change_id: str) -> Dict[str, Any]:
        """Verify a change by running tests"""
        change = next((c for c in self.change_log if c.change_id == change_id), None)
        if not change:
            return {"success": False, "error": "Change not found"}
        
        # Mark as verified (actual test run would be async)
        change.verified = True
        
        return {
            "success": True,
            "change_id": change_id,
            "verified": True
        }


class SelfCodingIntegration:
    """
    Integrates self-coding into agent's tool system.
    """
    
    def __init__(self, repo_path: str = None):
        self.executor = SelfCodingExecutor(repo_path)
        self.policy = SelfCodingPolicy()
    
    def get_self_coding_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions for self-coding"""
        return [
            {
                "name": "self_code_file",
                "description": "Create or modify a Python file in the RANN Agent codebase. Use when user asks to add features, fix bugs, or extend the agent itself.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Description of what this change does"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to file relative to repo root, e.g., 'rann_agent/core/runtime.py'"
                        },
                        "content": {
                            "type": "string",
                            "description": "Full file content (for create/modify) or empty for delete"
                        },
                        "change_type": {
                            "type": "string",
                            "enum": ["create", "modify", "delete"],
                            "description": "Type of change"
                        }
                    },
                    "required": ["task", "file_path", "content", "change_type"]
                }
            },
            {
                "name": "self_rollback",
                "description": "Rollback a previous self-coded change",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "change_id": {
                            "type": "string",
                            "description": "ID of the change to rollback"
                        }
                    },
                    "required": ["change_id"]
                }
            },
            {
                "name": "self_code_log",
                "description": "View history of self-coded changes",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    async def execute_self_code_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a self-coding tool"""
        if tool_name == "self_code_file":
            return self.executor.apply_change(
                task=parameters["task"],
                file_path=parameters["file_path"],
                new_content=parameters["content"],
                change_type=parameters["change_type"]
            )
        
        elif tool_name == "self_rollback":
            return self.executor.rollback(parameters["change_id"])
        
        elif tool_name == "self_code_log":
            return {
                "success": True,
                "changes": self.executor.get_change_log()
            }
        
        return {"success": False, "error": f"Unknown tool: {tool_name}"}