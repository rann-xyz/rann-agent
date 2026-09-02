"""
Better CLI with rich progress bars and interactive features
"""

import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.syntax import Syntax
import structlog

from rann_agent import Agent, Config

app = typer.Typer(help="🤖 Rann Agent - Next-generation autonomous AI agent")
console = Console()
logger = structlog.get_logger()


@app.command()
def chat(
    goal: str = typer.Argument(None, help="What you want the agent to do"),
    context: str = typer.Option(None, "--context", "-c", help="Additional context"),
    provider: str = typer.Option(None, "--provider", "-p", help="LLM provider"),
    model: str = typer.Option(None, "--model", "-m", help="Model name"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream response"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode"),
):
    """Execute a task with the agent (enhanced UX)"""
    
    # Interactive mode - ask for goal if not provided
    if not goal:
        if interactive:
            goal = Prompt.ask("[cyan]What would you like me to do?[/cyan]")
        else:
            console.print("[red]Error: Goal is required[/red]")
            raise typer.Exit(1)
    
    # Show nice banner
    console.print(Panel.fit(
        f"[bold cyan]🤖 Rann Agent[/bold cyan]\n\n"
        f"[yellow]Task:[/yellow] {goal}\n"
        f"[dim]Provider:[/dim] {provider or 'default'}\n"
        f"[dim]Mode:[/dim] {'streaming' if stream else 'standard'}",
        border_style="cyan",
        title="Starting..."
    ))
    
    # Load config
    config = Config.load()
    
    # Create agent
    agent = Agent(config=config, provider=provider, model=model)
    
    if stream:
        asyncio.run(_stream_execution_enhanced(agent, goal, context))
    else:
        asyncio.run(_execute_with_progress(agent, goal, context, interactive))


async def _execute_with_progress(agent: Agent, goal: str, context: str, interactive: bool):
    """Execute with rich progress bar"""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        
        task = progress.add_task("[cyan]Agent working...", total=100)
        
        # Simulate progress (in real impl, track actual progress)
        progress.update(task, advance=10, description="[cyan]Initializing...")
        await asyncio.sleep(0.3)
        
        progress.update(task, advance=20, description="[cyan]Planning approach...")
        await asyncio.sleep(0.3)
        
        progress.update(task, advance=20, description="[cyan]Executing tools...")
        
        # Execute actual task
        result = await agent.execute(goal, context)
        
        progress.update(task, advance=50, description="[green]✓ Complete!")
    
    # Display result
    console.print("\n" + "="*60)
    
    if result.get("done", False):
        console.print(Panel(
            result.get("output", ""),
            title="[bold green]✅ Task Completed[/bold green]",
            border_style="green"
        ))
        
        # Show metadata
        metadata = result.get("metadata", {})
        if metadata:
            _show_metadata_table(metadata)
        
        # Interactive follow-up
        if interactive:
            follow_up = Confirm.ask("\n[cyan]Would you like to do another task?[/cyan]")
            if follow_up:
                next_goal = Prompt.ask("[cyan]What next?[/cyan]")
                await _execute_with_progress(agent, next_goal, None, interactive)
    else:
        console.print(Panel(
            result.get("error", "Unknown error"),
            title="[bold red]❌ Task Failed[/bold red]",
            border_style="red"
        ))


async def _stream_execution_enhanced(agent: Agent, goal: str, context: str):
    """Enhanced streaming with live updates"""
    
    console.print("\n[bold cyan]Agent:[/bold cyan]\n")
    console.print("[dim]" + "─" * 60 + "[/dim]\n")
    
    token_count = 0
    
    async for token in agent.stream(goal, context):
        console.print(token, end="")
        token_count += 1
    
    console.print("\n\n[dim]" + "─" * 60 + "[/dim]")
    console.print(f"[dim]Generated {token_count} tokens[/dim]\n")


def _show_metadata_table(metadata: dict):
    """Display metadata in a nice table"""
    table = Table(title="Execution Details", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    if "turns" in metadata:
        table.add_row("Turns", str(metadata["turns"]))
    
    if "tokens" in metadata:
        tokens = metadata["tokens"]
        total = tokens.get("input_tokens", 0) + tokens.get("output_tokens", 0)
        table.add_row("Tokens", f"{total:,}")
    
    if "model" in metadata:
        table.add_row("Model", metadata["model"])
    
    console.print("\n")
    console.print(table)


@app.command()
def workflows():
    """Show available pre-built workflows"""
    
    workflows_list = [
        {
            "name": "deploy-vercel",
            "description": "Deploy app to Vercel",
            "command": 'rann-agent chat "deploy to vercel"'
        },
        {
            "name": "setup-ci",
            "description": "Set up GitHub Actions CI/CD",
            "command": 'rann-agent chat "setup github actions ci/cd"'
        },
        {
            "name": "add-auth",
            "description": "Add authentication to your app",
            "command": 'rann-agent chat "add jwt authentication"'
        },
        {
            "name": "generate-crud",
            "description": "Generate CRUD API endpoints",
            "command": 'rann-agent chat "generate crud api for users"'
        },
        {
            "name": "write-tests",
            "description": "Write tests for untested code",
            "command": 'rann-agent chat "write tests for all untested functions"'
        },
    ]
    
    console.print(Panel.fit(
        "[bold cyan]📋 Pre-built Workflows[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="yellow")
    table.add_column("Description")
    table.add_column("Command", style="dim")
    
    for wf in workflows_list:
        table.add_row(wf["name"], wf["description"], wf["command"])
    
    console.print(table)
    console.print("\n[dim]Run any workflow by copying the command above[/dim]")


@app.command()
def quick(preset: str = typer.Argument(..., help="Preset name")):
    """Quick access to common tasks"""
    
    presets = {
        "test": "run all tests and show coverage",
        "lint": "run linters and fix auto-fixable issues",
        "deploy": "build and deploy to production",
        "docs": "generate documentation from code",
        "analyze": "analyze codebase for issues and improvements",
    }
    
    if preset not in presets:
        console.print(f"[red]Unknown preset: {preset}[/red]")
        console.print("\n[cyan]Available presets:[/cyan]")
        for name, desc in presets.items():
            console.print(f"  • {name}: {desc}")
        raise typer.Exit(1)
    
    goal = presets[preset]
    console.print(f"[cyan]Running preset:[/cyan] {preset}")
    console.print(f"[dim]Goal:[/dim] {goal}\n")
    
    asyncio.run(_execute_preset(goal))


async def _execute_preset(goal: str):
    """Execute preset with nice output"""
    agent = Agent()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Running: {goal}", total=None)
        result = await agent.execute(goal)
        progress.update(task, description="[green]✓ Done!")
    
    if result.get("done"):
        console.print("\n[green]Success![/green]\n")
        console.print(result.get("output", ""))
    else:
        console.print("\n[red]Failed![/red]\n")
        console.print(result.get("error", ""))


if __name__ == "__main__":
    app()
