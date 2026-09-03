"""
Safe filesystem operations for RANN Agent.
As required by MASTER PROMPT Section 8.
"""

import os
import shutil
import hashlib
import tempfile
import re
from pathlib import Path
from typing import Optional, Tuple, List
import structlog

logger = structlog.get_logger()

BACKUP_DIR = ".rann_backup"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB default max


def _hash_file(path: str) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonicalize(path: str, workspace_root: str) -> str:
    """Resolve path and ensure it's within workspace."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    abs_root = os.path.abspath(workspace_root)
    if not abs_path.startswith(abs_root):
        raise ValueError(f"Path {abs_path} is outside workspace {abs_root}")
    return abs_path


def _ensure_backup_dir(workspace: str) -> str:
    """Ensure backup directory exists."""
    backup = os.path.join(workspace, BACKUP_DIR)
    os.makedirs(backup, exist_ok=True)
    return backup


class FilesystemEngine:
    """
    Safe filesystem operations with security checks.

    Features:
    - Canonicalize paths, prevent traversal
    - Workspace restriction
    - Backup before mutation
    - Atomic writes
    - Hash before/after
    - Size limits
    """

    def __init__(
        self,
        workspace_root: str,
        max_file_size: int = MAX_FILE_SIZE,
        allow_binary: bool = False,
    ) -> None:
        self.workspace_root = os.path.abspath(workspace_root)
        self.max_file_size = max_file_size
        self.allow_binary = allow_binary
        logger.info("filesystem_engine_initialized", workspace=self.workspace_root)

    # ---- Read Operations ----

    def safe_read(self, path: str, encoding: str = "utf-8") -> Tuple[str, str]:
        """
        Read file content safely.
        Returns (content, hash).
        Raises on traversal or size violation.
        """
        canonical = _canonicalize(path, self.workspace_root)

        if not os.path.isfile(canonical):
            raise FileNotFoundError(f"Not a file: {canonical}")

        file_size = os.path.getsize(canonical)
        if file_size > self.max_file_size:
            raise ValueError(
                f"File too large: {file_size} bytes (max: {self.max_file_size})"
            )

        with open(canonical, "rb") as f:
            raw = f.read()

        if not self.allow_binary:
            # Check for binary content
            if b"\x00" in raw[:1024]:
                raise ValueError("Binary files not allowed")

        content = raw.decode(encoding, errors="replace")
        file_hash = _hash_file(canonical)

        logger.debug("file_read", path=canonical, size=file_size, hash=file_hash[:8])
        return content, file_hash

    # ---- Write Operations ----

    def safe_write(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_backup: bool = True,
    ) -> Tuple[bool, str]:
        """
        Write file content safely with atomic write and backup.
        Returns (success, new_hash).
        """
        canonical = _canonicalize(path, self.workspace_root)

        # Ensure parent directory exists
        parent = os.path.dirname(canonical)
        if parent:
            os.makedirs(parent, exist_ok=True)

        # Backup existing file
        file_hash = ""
        if create_backup and os.path.exists(canonical):
            backup_dir = _ensure_backup_dir(self.workspace_root)
            rel_path = os.path.relpath(canonical, self.workspace_root)
            backup_path = os.path.join(backup_dir, rel_path)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(canonical, backup_path)
            file_hash = _hash_file(canonical)
            logger.debug("file_backed_up", original=canonical, backup=backup_path)

        # Atomic write: write to temp, then rename
        dir_name = os.path.dirname(canonical) or "."
        with tempfile.NamedTemporaryFile(
            mode="w", encoding=encoding, dir=dir_name, delete=False
        ) as tmp:
            tmp.write(content)
            tmp_name = tmp.name

        try:
            shutil.move(tmp_name, canonical)
        except Exception:
            os.unlink(tmp_name)
            raise

        new_hash = _hash_file(canonical)
        logger.info("file_written", path=canonical, hash=new_hash[:8])
        return True, new_hash

    def safe_patch(
        self,
        path: str,
        old_string: str,
        new_string: str,
    ) -> Tuple[bool, str]:
        """Patch a file by replacing old_string with new_string."""
        content, old_hash = self.safe_read(path)
        if old_string not in content:
            raise ValueError(f"String not found in file: {old_string[:50]}...")

        new_content = content.replace(old_string, new_string, 1)
        success, new_hash = self.safe_write(path, new_content)
        return success, new_hash

    # ---- Mutation Operations ----

    def safe_copy(self, src: str, dst: str) -> bool:
        """Copy file safely within workspace."""
        src_canonical = _canonicalize(src, self.workspace_root)
        dst_canonical = _canonicalize(dst, self.workspace_root)

        if not os.path.isfile(src_canonical):
            raise FileNotFoundError(f"Source not found: {src_canonical}")

        # Backup destination if exists
        if os.path.exists(dst_canonical):
            backup_dir = _ensure_backup_dir(self.workspace_root)
            rel_path = os.path.relpath(dst_canonical, self.workspace_root)
            backup_path = os.path.join(backup_dir, rel_path)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(dst_canonical, backup_path)

        shutil.copy2(src_canonical, dst_canonical)
        logger.info("file_copied", src=src_canonical, dst=dst_canonical)
        return True

    def safe_delete(self, path: str, force: bool = False) -> bool:
        """Delete file with optional backup."""
        canonical = _canonicalize(path, self.workspace_root)

        if not os.path.exists(canonical):
            return True  # Already gone

        if not force:
            # Don't delete important files without force
            important_patterns = [r"\.git", r"\.env", r"config\.yaml", r"requirements\.txt"]
            for pat in important_patterns:
                if re.search(pat, canonical, re.I):
                    raise ValueError(f"Refusing to delete important file without force: {canonical}")

        # Backup before delete
        backup_dir = _ensure_backup_dir(self.workspace_root)
        rel_path = os.path.relpath(canonical, self.workspace_root)
        backup_path = os.path.join(backup_dir, rel_path)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        if os.path.isfile(canonical):
            shutil.copy2(canonical, backup_path)

        if os.path.isfile(canonical):
            os.unlink(canonical)
        elif os.path.isdir(canonical):
            shutil.rmtree(canonical)

        logger.info("file_deleted", path=canonical, backed_up=True)
        return True

    def safe_list(self, path: str, pattern: str = "*") -> List[str]:
        """List files in directory matching pattern."""
        canonical = _canonicalize(path, self.workspace_root)

        if not os.path.isdir(canonical):
            raise NotADirectoryError(f"Not a directory: {canonical}")

        matches = list(Path(canonical).glob(pattern))
        return [str(m) for m in matches]

    def safe_search(self, path: str, pattern: str) -> List[str]:
        """Search for pattern in files."""
        import subprocess

        canonical = _canonicalize(path, self.workspace_root)

        if not os.path.isdir(canonical):
            raise NotADirectoryError(f"Not a directory: {canonical}")

        result = subprocess.run(
            ["grep", "-r", "-n", pattern, canonical],
            capture_output=True,
            text=True,
            cwd=canonical,
        )

        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return [l for l in lines if l]