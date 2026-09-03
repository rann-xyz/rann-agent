#!/usr/bin/env python3
"""
RANN Agent CLI - V3

Main command-line interface for RANN Agent.
Wire all commands to use RuntimeAgent as backend.

Usage:
    rann run "<task>"         Execute a task
    rann run --dry-run "<task>"  Show plan without executing
    rann doctor                Check system health
    rann status                Show agent status
    rann task list             List tasks
    rann task show <id>        Show task details
    rann task cancel <id>      Cancel a task
    rann memory search <query> Search memory
    rann audit                 Show audit log
"""

import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import click
import asyncio
import json
from datetime import datetime
from typing import Optional

from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.budget import Budget
from rann_agent.core.task_contract import TaskContract, TaskCategory
from rann_agent.core.event_bus import EventBus
from rann_agent.storage.database import Database


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """RANN Agent - Autonomous AI Engineering Platform

    THE MODEL GENERATES DECISIONS. RANN CONTROLS EXECUTION.
    """
    pass


@cli.command()
@click.argument("task")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
@click.option("--workspace", default=os.getcwd(), help="Working directory")
@click.option("--max-iterations", default=50, help="Maximum iterations")
@click.option("--max-tokens", default=50000, help="Token budget")
def run(task: str, dry_run: bool, workspace: str, max_iterations: int, max_tokens: int):
    """Execute a task with RANN Agent."""
    if dry_run:
        click.echo(f"[DRY RUN] Would execute: {task}")
        click.echo(f"  Workspace: {workspace}")
        click.echo(f"  Max iterations: {max_iterations}")
        click.echo(f"  Max tokens: {max_tokens}")
        click.echo("\nPlan would include:")
        click.echo("  - Files to inspect")
        click.echo("  - Files to change")
        click.echo("  - Risk assessment")
        click.echo("  - Verification strategy")
        click.echo("  - Rollback plan")
        return

    async def _execute():
        budget = Budget(
            max_tokens=max_tokens,
            max_turns=max_iterations,
        )
        agent = RuntimeAgent(budget=budget, workspace=workspace)

        click.echo(f"Executing: {task}")
        click.echo(f"Workspace: {workspace}")

        try:
            result = await agent.execute(task)
            if result.get("done"):
                click.echo("\n✅ Task completed!")
                if "output" in result:
                    click.echo(f"\nOutput:\n{result['output']}")
            else:
                click.echo(f"\n⚠️ Task ended after {result.get('turns', 0)} turns")
                if "error" in result:
                    click.echo(f"Error: {result['error']}")
        except Exception as e:
            click.echo(f"\n❌ Error: {e}", err=True)
            sys.exit(1)

    asyncio.run(_execute())


@cli.command()
def doctor():
    """Check system health and dependencies."""
    click.echo("🏥 RANN Agent System Check\n")

    checks = []

    # Python version
    py_version = sys.version_info
    checks.append(("Python version", f"{py_version.major}.{py_version.minor}.{py_version.micro}", py_version >= (3, 11)))

    # Check core modules
    try:
        from rann_agent.core.runtime import RuntimeAgent
        from rann_agent.core.budget import Budget
        from rann_agent.core.event_bus import EventBus
        from rann_agent.storage.database import Database
        checks.append(("Core modules", "OK", True))
    except ImportError as e:
        checks.append(("Core modules", f"FAIL: {e}", False))

    # Check storage
    try:
        db = Database()
        db.get_task("__health_check__")
        checks.append(("Database", "OK", True))
    except Exception as e:
        checks.append(("Database", f"WARN: {e}", True))  # Warning, not fail

    # Check workspace
    workspace = os.getcwd()
    writable = os.access(workspace, os.W_OK)
    checks.append(("Workspace", workspace, writable))

    # Print results
    for name, status, ok in checks:
        icon = "✅" if ok else "❌"
        click.echo(f"  {icon} {name}: {status}")

    all_ok = all(ok for _, _, ok in checks)
    click.echo()
    if all_ok:
        click.echo("All checks passed ✅")
    else:
        click.echo("Some checks failed ❌")
        sys.exit(1)


@cli.command()
def status():
    """Show agent status and statistics."""
    try:
        db = Database()
        tasks = db.list_tasks(limit=5)
        incomplete = db.get_incomplete_runs()

        click.echo("📊 RANN Agent Status\n")
        click.echo(f"  Recent tasks: {len(tasks)}")
        click.echo(f"  Incomplete runs: {len(incomplete)}")

        # Event bus stats
        eb = EventBus()
        handler_counts = {et.value: len(eb._handlers.get(et, [])) for et in list(EventType)[:5]}
        click.echo(f"  Event handlers: {sum(handler_counts.values())}")

    except Exception as e:
        click.echo(f"Status unavailable: {e}")


# Task subcommand group
@cli.group("task")
def task():
    """Task management commands."""
    pass


@task.command("list")
@click.option("--limit", default=20, help="Maximum tasks to show")
def task_list(limit: int):
    """List recent tasks."""
    try:
        db = Database()
        tasks = db.list_tasks(limit=limit)
        if not tasks:
            click.echo("No tasks found")
            return

        click.echo(f"Recent Tasks ({len(tasks)}):\n")
        for t in tasks:
            state = t.get("state", "unknown")
            task_id = t.get("task_id", "")[:8]
            updated = t.get("updated_at", "")[:19]
            click.echo(f"  [{state:15}] {task_id}... {updated}")
    except Exception as e:
        click.echo(f"Error: {e}")


@task.command("show")
@click.argument("task_id")
def task_show(task_id: str):
    """Show task details."""
    try:
        db = Database()
        task = db.get_task(task_id)
        if not task:
            click.echo(f"Task not found: {task_id}")
            return

        click.echo(f"\nTask: {task_id}\n")
        click.echo(f"  State: {task.get('state', 'unknown')}")
        click.echo(f"  Created: {task.get('created_at', 'unknown')}")
        click.echo(f"  Updated: {task.get('updated_at', 'unknown')}")

        contract = task.get("contract_json", "{}")
        try:
            c = json.loads(contract)
            if "objective" in c:
                click.echo(f"  Objective: {c['objective'][:100]}...")
        except:
            pass

        # Show transitions
        runs = db.get_incomplete_runs()
        for run in runs:
            if run.get("task_id") == task_id:
                transitions = db.get_transitions(run["run_id"])
                if transitions:
                    click.echo(f"\n  State transitions ({len(transitions)}):")
                    for tr in transitions[-5:]:
                        click.echo(f"    {tr.get('from_state', '?'):15} -> {tr.get('to_state', '?'):15}")

    except Exception as e:
        click.echo(f"Error: {e}")


@task.command("cancel")
@click.argument("task_id")
def task_cancel(task_id: str):
    """Cancel a running task."""
    click.echo(f"Cancel requested for task: {task_id}")
    # In full implementation, this would signal the running task
    click.echo("(Full cancellation requires running task monitor)")


# Memory subcommand group
@cli.group("memory")
def memory():
    """Memory management commands."""
    pass


@memory.command("search")
@click.argument("query")
@click.option("--type", "mem_type", default=None, help="Memory type filter")
@click.option("--limit", default=10, help="Maximum results")
def memory_search(query: str, mem_type: Optional[str], limit: int):
    """Search memory for information."""
    try:
        db = Database()
        results = db.search_memories(query, memory_type=mem_type)

        if not results:
            click.echo(f"No memory results for: {query}")
            return

        click.echo(f"Memory results for '{query}' ({len(results)} found):\n")
        for r in results[:limit]:
            mem_id = r.get("memory_id", "")[:12]
            content = r.get("content", "")[:80]
            mem_type_val = r.get("memory_type", "unknown")
            confidence = r.get("confidence", 0.0)
            click.echo(f"  [{mem_type_val:10}] {mem_id}... (conf: {confidence:.2f})")
            click.echo(f"    {content}...")
            click.echo()
    except Exception as e:
        click.echo(f"Error: {e}")


@memory.command("stats")
def memory_stats():
    """Show memory statistics."""
    try:
        db = Database()
        all_memories = db.search_memories("", None)  # Get all

        by_type: dict[str, int] = {}
        for m in all_memories:
            t = m.get("memory_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        click.echo("📊 Memory Statistics\n")
        click.echo(f"  Total memories: {len(all_memories)}")
        click.echo(f"  By type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            click.echo(f"    {t}: {count}")

    except Exception as e:
        click.echo(f"Error: {e}")


@cli.command()
def audit():
    """Show recent audit log entries."""
    try:
        db = Database()
        conn = db._get_conn()
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()
        conn.close()

        if not rows:
            click.echo("No audit entries")
            return

        click.echo("📋 Recent Audit Log:\n")
        for row in rows:
            ts = row["timestamp"][:19] if row["timestamp"] else ""
            operation = row["operation"] or ""
            result = row["result"] or ""
            click.echo(f"  {ts} | {operation:20} | {result[:40]}")
    except Exception as e:
        click.echo(f"Error: {e}")


# Skills subcommand group
@cli.group("skills")
def skills():
    """Skill management commands."""
    pass


@skills.command("list")
def skills_list():
    """List available skills."""
    try:
        from rann_agent.skills.registry import SkillRegistry
        registry = SkillRegistry()
        all_skills = registry.list_all()

        if not all_skills:
            click.echo("No skills registered")
            return

        click.echo(f"Registered Skills ({len(all_skills)}):\n")
        for s in all_skills:
            name = s.name if hasattr(s, "name") else str(s)
            category = s.category if hasattr(s, "category") else ""
            enabled = s.enabled if hasattr(s, "enabled") else True
            icon = "✅" if enabled else "❌"
            click.echo(f"  {icon} {name:20} [{category}]")
    except Exception as e:
        click.echo(f"Error: {e}")


@cli.command()
def learn():
    """Show learning status and lessons."""
    try:
        from rann_agent.learning.engine import LearningEngine
        engine = LearningEngine()
        lessons = engine.get_lessons()

        click.echo("📚 Learning Status\n")
        click.echo(f"  Validated lessons: {len(lessons)}")

        if lessons:
            click.echo("\n  Recent lessons:")
            for l in lessons[:5]:
                content = l.content[:60] if hasattr(l, "content") else str(l)[:60]
                click.echo(f"    - {content}...")
    except Exception as e:
        click.echo(f"Error: {e}")


if __name__ == "__main__":
    # Import EventType here to avoid circular import issues
    from rann_agent.core.event_bus import EventType
    cli()