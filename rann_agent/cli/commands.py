"""
Additional RANN Agent CLI commands for V3 agent operations.
These complement the core commands in rann.py.
"""

import click
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.budget import Budget
from rann_agent.core.config import Config
from rann_agent.storage.database import Database


# =============================================================================
# SHELL — Interactive chat mode
# =============================================================================

def shell_cmd():
    """Interactive shell mode (alias for --interactive flag on run)."""
    pass  # Handled below as a real command


def register_shell(cli):
    """Register the shell (chat) command."""
    
    @cli.command("shell")
    @click.option("--workspace", default=None, help="Working directory")
    @click.option("--max-iterations", default=50, help="Max turns per task")
    def shell(workspace: Optional[str], max_iterations: int):
        """Interactive chat mode - type 'exit' to quit, 'clear' to clear history."""
        
        if workspace is None:
            workspace = Path.cwd()
        
        click.echo("=" * 60)
        click.echo("  RANN Agent Shell — Interactive Mode")
        click.echo("  Type 'exit' to quit, 'clear' to clear history")
        click.echo("  Type '!run <task>' to execute a task")
        click.echo("=" * 60)
        click.echo()
        
        config = Config()
        budget = Budget(max_tokens=50000, max_turns=max_iterations)
        
        # Shared agent for conversation continuity
        agent = RuntimeAgent(budget=budget, config=config)
        
        async def run_task(task: str) -> dict:
            return await agent.execute(task)
        
        while True:
            try:
                user_input = click.prompt("\n👤 You", type=str, default="").strip()
            except (EOFError, KeyboardInterrupt):
                click.echo("\n\nGoodbye!")
                break
            
            if not user_input:
                continue
            
            if user_input.lower() in ("exit", "quit", "q"):
                click.echo("\nGoodbye!")
                break
            
            if user_input.lower() == "clear":
                click.echo("History cleared.")
                continue
            
            if user_input.startswith("!run "):
                task = user_input[5:]
                click.echo(f"\n🤖 Agent: executing '{task}'...")
                result = asyncio.run(run_task(task))
                output = result.get("output", result.get("error", "No output"))
                click.echo(f"\n📤 Output:\n{output}")
                continue
            
            if user_input.startswith("!status"):
                click.echo(f"\n📊 Session stats:")
                click.echo(f"   Max iterations: {max_iterations}")
                click.echo(f"   Provider: {config.agent.llm.provider}")
                click.echo(f"   Model: {config.agent.llm.model}")
                continue
            
            # Echo back as thinking
            click.echo(f"\n💭 RANN: (use !run '<task>' to execute tasks)")
            click.echo(f"   Received: {user_input[:50]}...")


# =============================================================================
# TASK — Extended task management
# =============================================================================

def register_task_commands(task_group):
    """Register extended task commands."""
    
    @task_group.command("retry")
    @click.argument("task_id")
    @click.option("--max-iterations", default=50, help="Max iterations")
    def task_retry(task_id: str, max_iterations: int):
        """Retry a failed task."""
        try:
            db = Database()
            task = db.get_task(task_id)
            
            if not task:
                click.echo(f"Task not found: {task_id}")
                return
            
            goal = task.get("goal") or task.get("description", "")
            if not goal:
                click.echo(f"No goal found for task: {task_id}")
                return
            
            click.echo(f"Retrying task: {goal[:60]}...")
            
            config = Config()
            budget = Budget(max_tokens=50000, max_turns=max_iterations)
            agent = RuntimeAgent(budget=budget, config=config)
            
            async def do_retry():
                return await agent.execute(goal)
            
            result = asyncio.run(do_retry())
            output = result.get("output", result.get("error", "No output"))
            click.echo(f"\n📤 Output:\n{output}")
            
        except Exception as e:
            click.echo(f"Error: {e}")
    
    @task_group.command("delete")
    @click.argument("task_id")
    @click.option("--force", is_flag=True, help="Skip confirmation")
    def task_delete(task_id: str, force: bool):
        """Delete a task and its history."""
        try:
            db = Database()
            task = db.get_task(task_id)
            
            if not task:
                click.echo(f"Task not found: {task_id}")
                return
            
            goal = task.get("goal", task.get("description", ""))[:50]
            
            if not force:
                click.confirm(f"Delete task '{goal}'?", abort=True)
            
            db._get_conn().execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            db._get_conn().commit()
            click.echo(f"✅ Deleted: {task_id}")
            
        except click.Abort:
            click.echo("Cancelled.")
        except Exception as e:
            click.echo(f"Error: {e}")
    
    @task_group.command("cancel")
    @click.argument("task_id")
    def task_cancel(task_id: str):
        """Cancel a running task."""
        try:
            db = Database()
            task = db.get_task(task_id)
            
            if not task:
                click.echo(f"Task not found: {task_id}")
                return
            
            state = task.get("state", "")
            if state in ("completed", "failed", "cancelled"):
                click.echo(f"Task already {state}: {task_id}")
                return
            
            db._get_conn().execute(
                "UPDATE tasks SET state = 'cancelled' WHERE task_id = ?",
                (task_id,)
            )
            db._get_conn().commit()
            click.echo(f"✅ Cancelled: {task_id}")
            
        except Exception as e:
            click.echo(f"Error: {e}")


# =============================================================================
# MEMORY — Extended memory management
# =============================================================================

def register_memory_commands(memory_group):
    """Register extended memory commands."""
    
    @memory_group.command("clear")
    @click.option("--type", "mem_type", default=None, help="Memory type to clear")
    @click.option("--force", is_flag=True, help="Skip confirmation")
    def memory_clear(mem_type: Optional[str], force: bool):
        """Clear memory (all or by type: episodic, semantic, project)."""
        try:
            if not force:
                t = mem_type or "all"
                click.confirm(f"Clear {t} memories?", abort=True)
            
            db = Database()
            conn = db._get_conn()
            
            if mem_type:
                conn.execute("DELETE FROM memories WHERE memory_type = ?", (mem_type,))
            else:
                conn.execute("DELETE FROM memories")
            
            conn.commit()
            t = mem_type or "all"
            click.echo(f"✅ Cleared {t} memories")
            
        except click.Abort:
            click.echo("Cancelled.")
        except Exception as e:
            click.echo(f"Error: {e}")
    
    @memory_group.command("add")
    @click.argument("content")
    @click.option("--type", "mem_type", default="semantic", help="Memory type")
    @click.option("--key", default=None, help="Semantic memory key")
    def memory_add(content: str, mem_type: str, key: Optional[str]):
        """Add a memory manually."""
        try:
            db = Database()
            conn = db._get_conn()
            
            import uuid
            memory_id = str(uuid.uuid4())[:12]
            
            conn.execute(
                "INSERT INTO memories (memory_id, memory_type, content, confidence, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (memory_id, mem_type, content, 1.0, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
            )
            conn.commit()
            click.echo(f"✅ Added {mem_type} memory: {memory_id}")
            
        except Exception as e:
            click.echo(f"Error: {e}")
    
    @memory_group.command("export")
    @click.argument("filepath")
    @click.option("--type", "mem_type", default=None, help="Memory type to export")
    def memory_export(filepath: str, mem_type: Optional[str]):
        """Export memories to JSON file."""
        try:
            db = Database()
            results = db.search_memories("", memory_type=mem_type)
            
            with open(filepath, "w") as f:
                json.dump(results, f, indent=2, default=str)
            
            click.echo(f"✅ Exported {len(results)} memories to {filepath}")
            
        except Exception as e:
            click.echo(f"Error: {e}")


# =============================================================================
# SESSION — Session management
# =============================================================================

def register_session_commands(cli):
    """Register session commands."""
    
    @cli.group("session")
    def session():
        """Session management."""
        pass
    
    @session.command("list")
    @click.option("--limit", default=20, help="Max sessions")
    def session_list(limit: int):
        """List recent sessions."""
        try:
            db = Database()
            conn = db._get_conn()
            rows = conn.execute(
                "SELECT run_id, task_id, start_time, end_time, result FROM runs ORDER BY start_time DESC LIMIT ?",
                (limit,)
            ).fetchall()
            conn.close()
            
            if not rows:
                click.echo("No sessions found")
                return
            
            click.echo(f"Sessions ({len(rows)}):\n")
            for r in rows:
                sid = r["run_id"][:12]
                start = r["start_time"][:19] if r["start_time"] else ""
                result = (r["result"] or "")[:40]
                click.echo(f"  {sid}... | {start} | {result}...")
                
        except Exception as e:
            click.echo(f"Error: {e}")
    
    @session.command("show")
    @click.argument("session_id")
    def session_show(session_id: str):
        """Show session details and trace."""
        try:
            db = Database()
            conn = db._get_conn()
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (session_id,)
            ).fetchone()
            conn.close()
            
            if not row:
                click.echo(f"Session not found: {session_id}")
                return
            
            click.echo(f"Session: {session_id}\n")
            for key, val in row.items():
                if val is None:
                    continue
                v = str(val)[:100]
                click.echo(f"  {key:15}: {v}")
                
        except Exception as e:
            click.echo(f"Error: {e}")
    
    @session.command("export")
    @click.argument("session_id")
    @click.argument("filepath")
    def session_export(session_id: str, filepath: str):
        """Export session trace to JSON."""
        try:
            db = Database()
            conn = db._get_conn()
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (session_id,)
            ).fetchone()
            conn.close()
            
            if not row:
                click.echo(f"Session not found: {session_id}")
                return
            
            with open(filepath, "w") as f:
                json.dump(dict(row), f, indent=2, default=str)
            
            click.echo(f"✅ Exported session to {filepath}")
            
        except Exception as e:
            click.echo(f"Error: {e}")


# =============================================================================
# PROJECT — Project initialization and learning
# =============================================================================

def register_project_commands(cli):
    """Register project commands."""
    
    @cli.group("project")
    def project():
        """Project management."""
        pass
    
    @project.command("init")
    @click.argument("path", default=".")
    @click.option("--name", default=None, help="Project name")
    @click.option("--language", default=None, help="Primary language (python, js, etc)")
    def project_init(path: str, name: Optional[str], language: Optional[str]):
        """Initialize RANN Agent for a project directory."""
        try:
            proj_path = Path(path).resolve()
            
            if not proj_path.exists():
                click.confirm(f"Directory {proj_path} does not exist. Create?", abort=True)
                proj_path.mkdir(parents=True)
            
            # Detect language if not provided
            if not language:
                if (proj_path / "package.json").exists():
                    language = "javascript"
                elif (proj_path / "requirements.txt").exists() or (proj_path / "setup.py").exists():
                    language = "python"
                elif (proj_path / "Cargo.toml").exists():
                    language = "rust"
                else:
                    language = "unknown"
            
            if not name:
                name = proj_path.name
            
            db = Database()
            conn = db._get_conn()
            
            # Store project in memories table with type=project
            import uuid
            proj_memory_id = str(uuid.uuid4())[:12]
            
            metadata = json.dumps({
                "name": name,
                "path": str(proj_path),
                "language": language,
                "conventions": ""
            })
            
            conn.execute(
                """INSERT INTO memories (memory_id, memory_type, content, confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (proj_memory_id, "project", metadata, 1.0, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
            )
            conn.commit()
            
            click.echo(f"✅ Project initialized: {name}")
            click.echo(f"   Path: {proj_path}")
            click.echo(f"   Language: {language}")
            click.echo(f"\nNow run: rann project learn")
            
        except click.Abort:
            click.echo("Cancelled.")
        except Exception as e:
            click.echo(f"Error: {e}")
    
    @project.command("learn")
    @click.argument("path", default=".")
    def project_learn(path: str):
        """Learn project conventions by analyzing files."""
        try:
            proj_path = Path(path).resolve()
            
            click.echo(f"Learning project: {proj_path}")
            
            # Scan for convention files
            convention_files = [
                ".pre-commit-config.yaml",
                "pyproject.toml",
                "package.json",
                "Makefile",
                ".eslintrc*",
                ".gitignore",
            ]
            
            found = []
            for cf in convention_files:
                matches = list(proj_path.glob(cf))
                found.extend(matches)
            
            click.echo(f"\nFound {len(found)} convention files:")
            for f in found:
                click.echo(f"  - {f.relative_to(proj_path)}")
            
            project_id = proj_path.name
            conventions = "\n".join(str(f.relative_to(proj_path)) for f in found)
            
            # Save to memories table
            db = Database()
            conn = db._get_conn()
            
            metadata = json.dumps({
                "name": project_id,
                "path": str(proj_path),
                "language": "",
                "conventions": conventions
            })
            
            conn.execute(
                """INSERT INTO memories (memory_id, memory_type, content, confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (project_id, "project", metadata, 1.0, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
            )
            conn.commit()
            
            click.echo(f"\n✅ Learned {len(found)} conventions for {project_id}")
            
        except Exception as e:
            click.echo(f"Error: {e}")


# =============================================================================
# SERVE — API server
# =============================================================================

def register_serve(cli):
    """Register the serve command."""
    
    @cli.command("serve")
    @click.option("--port", default=8000, help="Port to listen on")
    @click.option("--host", default="127.0.0.1", help="Host to bind")
    def serve(port: int, host: str):
        """Start RANN Agent web interface."""
        try:
            import http.server
            import socketserver
            import os
            
            # Find web_app.py path
            web_app_path = Path(__file__).parent.parent.parent / "web_app.py"
            if not web_app_path.exists():
                web_app_path = Path.cwd() / "web_app.py"
            
            if not web_app_path.exists():
                click.echo(f"Error: web_app.py not found at {web_app_path}")
                return
            
            os.chdir(web_app_path.parent)
            
            Handler = http.server.SimpleHTTPRequestHandler
            with socketserver.TCPServer((host, port), Handler) as httpd:
                click.echo(f"🌐 RANN Agent Web Interface")
                click.echo(f"   URL: http://{host}:{port}/web_app.py")
                click.echo(f"   Press Ctrl+C to stop")
                httpd.serve_forever()
        except Exception as e:
            click.echo(f"Error: {e}")


# =============================================================================
# CONTEXT — Context management
# =============================================================================

def register_context_commands(cli):
    """Register context commands."""
    
    @cli.command("context")
    @click.option("--add", "action", flag_value="add", help="Add context")
    @click.option("--show", "action", flag_value="show", help="Show context")
    @click.option("--clear", "action", flag_value="clear", help="Clear context")
    @click.argument("content", required=False)
    def context_cmd(action: Optional[str], content: Optional[str]):
        """Manage agent context (system prompt, project info)."""
        ctx_path = Path.home() / ".rann_agent" / "context.txt"
        
        if action == "clear":
            if ctx_path.exists():
                ctx_path.unlink()
            click.echo("Context cleared.")
            return
        
        if action == "show":
            if ctx_path.exists():
                click.echo(f"Current context:\n{ctx_path.read_text()}")
            else:
                click.echo("No context set.")
            return
        
        if action == "add" or content:
            text = content or ""
            ctx_path.parent.mkdir(parents=True, exist_ok=True)
            existing = ctx_path.read_text() if ctx_path.exists() else ""
            new_context = existing + "\n" + text if existing else text
            ctx_path.write_text(new_context)
            click.echo(f"Context updated ({len(new_context)} chars)")
            return
        
        # Default: show
        if ctx_path.exists():
            click.echo(f"Current context:\n{ctx_path.read_text()}")
        else:
            click.echo("No context set. Usage:")
            click.echo("  rann context --add 'Project is a Python web app'")
            click.echo("  rann context --show")
            click.echo("  rann context --clear")


# =============================================================================
# STATS — System statistics
# =============================================================================

def register_stats(cli):
    """Register stats command."""
    
    @cli.command("stats")
    def stats():
        """Show comprehensive system statistics."""
        try:
            db = Database()
            conn = db._get_conn()
            
            # Counts
            tasks_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            runs_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            memories_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            episodes_count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            
            # State breakdown
            state_rows = conn.execute(
                "SELECT state, COUNT(*) as cnt FROM tasks GROUP BY state ORDER BY cnt DESC"
            ).fetchall()
            
            # Recent activity
            recent = conn.execute(
                "SELECT created_at FROM tasks ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            
            conn.close()
            
            click.echo("📊 RANN Agent Statistics\n")
            click.echo(f"  Tasks:      {tasks_count}")
            click.echo(f"  Runs:       {runs_count}")
            click.echo(f"  Memories:   {memories_count}")
            click.echo(f"  Episodes:   {episodes_count}")
            click.echo(f"\n  Task states:")
            for state, cnt in state_rows:
                click.echo(f"    {state or 'unknown'}: {cnt}")
            
            if recent and recent[0]:
                click.echo(f"\n  Last activity: {recent[0][:19]}")
            
        except Exception as e:
            click.echo(f"Error: {e}")