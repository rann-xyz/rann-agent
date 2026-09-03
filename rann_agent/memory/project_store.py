"""
Project memory store for RANN Agent.
As required by MASTER PROMPT Section 27.
Persists project context across sessions.
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class ProjectContext:
    project_id: str
    name: str
    workspace_root: str
    language: str = "unknown"
    framework: str = ""
    test_framework: str = ""
    build_system: str = ""
    dependencies: List[str] = field(default_factory=list)
    file_structure: Dict[str, Any] = field(default_factory=dict)
    recent_files: List[str] = field(default_factory=list)
    key_modules: List[str] = field(default_factory=list)
    coding_conventions: Dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    session_count: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class ProjectMemoryStore:
    """Persistent project context across agent sessions."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".rann-agent" / "project_memory.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workspace_root TEXT UNIQUE NOT NULL,
                language TEXT DEFAULT 'unknown',
                framework TEXT DEFAULT '',
                test_framework TEXT DEFAULT '',
                build_system TEXT DEFAULT '',
                dependencies_json TEXT DEFAULT '[]',
                file_structure_json TEXT DEFAULT '{}',
                recent_files_json TEXT DEFAULT '[]',
                key_modules_json TEXT DEFAULT '[]',
                coding_conventions_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                session_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace ON projects(workspace_root)")
        conn.commit()
        conn.close()

    def save(self, ctx: ProjectContext) -> None:
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO projects
            (project_id, name, workspace_root, language, framework, test_framework,
             build_system, dependencies_json, file_structure_json, recent_files_json,
             key_modules_json, coding_conventions_json, created_at, updated_at, session_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ctx.project_id, ctx.name, ctx.workspace_root, ctx.language, ctx.framework,
            ctx.test_framework, ctx.build_system,
            json.dumps(ctx.dependencies),
            json.dumps(ctx.file_structure),
            json.dumps(ctx.recent_files),
            json.dumps(ctx.key_modules),
            json.dumps(ctx.coding_conventions),
            ctx.created_at, ctx.updated_at, ctx.session_count
        ))
        conn.commit()
        conn.close()
        logger.debug("project_saved", project_id=ctx.project_id)

    def load(self, workspace_root: str) -> Optional[ProjectContext]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM projects WHERE workspace_root=?", (workspace_root,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_context(row)

    def load_or_create(self, workspace_root: str, name: str = "") -> ProjectContext:
        existing = self.load(workspace_root)
        if existing:
            return existing
        ctx = ProjectContext(
            project_id=workspace_root.replace("/", "_").replace(".", "_"),
            name=name or Path(workspace_root).name,
            workspace_root=workspace_root
        )
        self.save(ctx)
        return ctx

    def increment_session(self, workspace_root: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE projects SET session_count=session_count+1, updated_at=? WHERE workspace_root=?",
            (datetime.utcnow().isoformat(), workspace_root)
        )
        conn.commit()
        conn.close()

    def list_projects(self) -> List[ProjectContext]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        conn.close()
        return [self._row_to_context(r) for r in rows]

    def delete(self, workspace_root: str) -> bool:
        conn = self._get_conn()
        n = conn.execute("DELETE FROM projects WHERE workspace_root=?", (workspace_root,)).rowcount
        conn.commit()
        conn.close()
        return n > 0

    def _row_to_context(self, row) -> ProjectContext:
        return ProjectContext(
            project_id=row["project_id"],
            name=row["name"],
            workspace_root=row["workspace_root"],
            language=row["language"],
            framework=row["framework"],
            test_framework=row["test_framework"],
            build_system=row["build_system"],
            dependencies=json.loads(row["dependencies_json"] or "[]"),
            file_structure=json.loads(row["file_structure_json"] or "{}"),
            recent_files=json.loads(row["recent_files_json"] or "[]"),
            key_modules=json.loads(row["key_modules_json"] or "[]"),
            coding_conventions=json.loads(row["coding_conventions_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            session_count=row["session_count"]
        )