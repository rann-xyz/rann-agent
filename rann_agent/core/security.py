"""
Core Security Utilities for RANN
Provides workspace isolation, path validation, and security checks.
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple

import structlog

logger = structlog.get_logger()


class WorkspaceSecurity:
    """Centralized workspace boundary enforcement."""
    
    @staticmethod
    def safe_join(workspace_root: Path, user_path: str) -> Path:
        """
        Securely join a workspace root with a user-provided path.
        
        Raises:
            ValueError: If path escapes workspace or is invalid
        """
        workspace_root = workspace_root.resolve()
        
        # Reject traversal attempts early
        if ".." in user_path:
            raise ValueError("Path traversal detected")
        
        # Reject absolute paths
        if Path(user_path).is_absolute():
            raise ValueError("Absolute paths not allowed")
        
        # Resolve the candidate path
        candidate = (workspace_root / user_path).resolve()
        
        # Verify containment using canonical paths
        try:
            candidate.relative_to(workspace_root)
        except ValueError:
            raise ValueError("Path escapes workspace boundary")
        
        return candidate
    
    @staticmethod
    def safe_join_with_existence_check(
        workspace_root: Path, 
        user_path: str, 
        must_exist: bool = False
    ) -> Tuple[Path, bool]:
        """
        Safe join with optional existence check.
        
        Returns:
            Tuple of (resolved_path, path_exists)
        """
        workspace_root = workspace_root.resolve()
        
        # Reject traversal attempts
        if ".." in user_path:
            raise ValueError("Path traversal detected")
        
        # Reject absolute paths
        if Path(user_path).is_absolute():
            raise ValueError("Absolute paths not allowed")
        
        candidate = (workspace_root / user_path).resolve()
        exists = candidate.exists()
        
        # Verify containment
        try:
            candidate.relative_to(workspace_root)
        except ValueError:
            raise ValueError("Path escapes workspace boundary")
        
        if must_exist and not exists:
            raise ValueError(f"Path does not exist: {user_path}")
        
        return candidate, exists
    
    @staticmethod
    def validate_symlink(target: Path, workspace_root: Path) -> bool:
        """
        Check if a symlink target stays within workspace.
        Returns True if safe, False if it points outside.
        """
        if not target.is_symlink():
            return True
        
        workspace_root = workspace_root.resolve()
        symlink_target = target.resolve()
        
        try:
            symlink_target.relative_to(workspace_root)
            return True
        except ValueError:
            return False


class CommandSanitizer:
    """Sanitizes and validates shell commands."""
    
    # Dangerous patterns that should never pass through
    DANGEROUS_PATTERNS = [
        r">\s*/dev/sd",           # Write to block device
        r"mkfs\s+",               # Format filesystem
        r"dd\s+if=",              # Direct disk write
        r">\s*/dev/null",        # Potential for data exfiltration
    ]
    
    @classmethod
    def contains_dangerous_pattern(cls, command: str) -> Tuple[bool, str]:
        """Check if command contains dangerous patterns."""
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True, f"Contains dangerous pattern: {pattern}"
        return False, ""
    
    @classmethod
    def escape_shell_metacharacters(cls, arg: str) -> str:
        """Escape shell metacharacters in an argument."""
        # Use single quotes and escape any existing single quotes
        return "'" + arg.replace("'", "'\\''") + "'"


class WorkspaceGuard:
    """Context manager for workspace-bound operations."""
    
    def __init__(self, workspace_root: Path, allow_create: bool = False):
        self.workspace_root = workspace_root.resolve()
        self.allow_create = allow_create
        self._resolved_path: Optional[Path] = None
    
    def validate_path(self, user_path: str) -> Path:
        """Validate a user-provided path is within workspace."""
        return WorkspaceSecurity.safe_join(self.workspace_root, user_path)
    
    def safe_resolve(self, user_path: str) -> Path:
        """Resolve path with symlink safety checks."""
        resolved = self.validate_path(user_path)
        
        # Check symlinks don't escape
        if resolved.is_symlink():
            if not WorkspaceSecurity.validate_symlink(resolved, self.workspace_root):
                raise ValueError("Symlink escape attempt detected")
        
        return resolved