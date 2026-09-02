"""
CLI interface for Rann Agent
"""

import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.live import Live
from rich.spinner import Spinner
import structlog

from rann_agent import Agent, Config

app = typer.Typer(help="🤖 Rann Agent - Next-generation autonomous AI agent")
console = Console()
logger = structlog.get_logger()


@app.command()
def chat(
    goal: str = typer.Argument(..., help="What you want the agent to do"),
    context: str = typer.Option(None, "--context", "-c", help="Additional context"),
    provider: str = typer.Option(None, "--provider", "-p", help="LLM provider (anthropic|openai|ollama)"),
    model: str = typer.Option(None, "--model", "-m", help="Model name"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream response"),
    background: bool = typer.Option(False, "--background", "-b", help="Run in background"),
):
    """Execute a task with the agent"""
    
    console.print(Panel.fit(
        f"[bold cyan]🤖 Rann Agent[/bold cyan]\n\n"
        f"[yellow]Goal:[/yellow] {goal}\n"
        f"[dim]Provider:[/dim] {provider or 'default'}",
        border_style="cyan"
    ))
    
    # Load config
    config = Config.load()
    
    # Create agent
    agent = Agent(
        config=config,
        provider=provider,
        model=model,
    )
    
    if stream:
        # Stream mode
        asyncio.run(_stream_execution(agent, goal, context))
    else:
        # Normal mode
        asyncio.run(_execute_task(agent, goal, context, background))


async def _execute_task(agent: Agent, goal: str, context: str, background: bool):
    """Execute task and show result"""
    
    if background:
        console.print("[yellow]Running in background...[/yellow]")
        # TODO: Implement background execution with notification
        return
    
    with console.status("[bold green]Agent working...", spinner="dots"):
        result = await agent.execute(goal, context)
    
    if result.get("success", True):
        console.print("\n[bold green]✅ Task completed![/bold green]\n")
        console.print(result.get("output", ""))
        
        # Show metadata
        metadata = result.get("metadata", {})
        if metadata:
            console.print(f"\n[dim]Turns: {metadata.get('turns', 'unknown')}[/dim]")
            if "tokens" in metadata:
                tokens = metadata["tokens"]
                console.print(f"[dim]Tokens: {tokens.get('input_tokens', 0) + tokens.get('output_tokens', 0)}[/dim]")
    else:
        console.print(f"\n[bold red]❌ Task failed[/bold red]\n")
        console.print(result.get("error", "Unknown error"))


async def _stream_execution(agent: Agent, goal: str, context: str):
    """Stream execution"""
    console.print("\n[bold cyan]Agent:[/bold cyan]\n")
    
    async for token in agent.stream(goal, context):
        console.print(token, end="")
    
    console.print("\n")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Server host"),
    port: int = typer.Option(8000, "--port", help="Server port"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
):
    """Start API server with web dashboard"""
    
    console.print(Panel.fit(
        f"[bold cyan]🚀 Starting Rann Agent Server[/bold cyan]\n\n"
        f"[yellow]URL:[/yellow] http://{host}:{port}\n"
        f"[yellow]Dashboard:[/yellow] http://{host}:{port}/dashboard\n"
        f"[yellow]API Docs:[/yellow] http://{host}:{port}/docs",
        border_style="cyan"
    ))
    
    import uvicorn
    uvicorn.run(
        "rann_agent.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def config_show():
    """Show current configuration"""
    
    config = Config.load()
    
    console.print(Panel.fit(
        f"[bold cyan]⚙️  Configuration[/bold cyan]\n\n"
        f"[yellow]Provider:[/yellow] {config.agent.llm.provider}\n"
        f"[yellow]Model:[/yellow] {config.agent.llm.model}\n"
        f"[yellow]Tools:[/yellow] {', '.join(config.tools.enabled)}\n"
        f"[yellow]Self-healing:[/yellow] {'✅' if config.agent.self_healing.enabled else '❌'}\n"
        f"[yellow]Orchestration:[/yellow] {'✅' if config.agent.orchestration.enabled else '❌'}\n"
        f"[yellow]Memory:[/yellow] {'✅' if config.agent.memory.persist else '❌'}",
        border_style="cyan"
    ))
    
    # Show warnings
    warnings = config.validate_config()
    if warnings:
        console.print("\n[yellow]⚠️  Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  • {warning}")


@app.command()
def tools_list():
    """List available tools"""
    
    config = Config.load()
    agent = Agent(config=config)
    
    tools = agent.tools.list_tools()
    
    console.print(Panel.fit("[bold cyan]🛠️  Available Tools[/bold cyan]", border_style="cyan"))
    console.print()
    
    for tool in tools:
        status = "✅" if tool["enabled"] else "❌"
        console.print(f"{status} [bold]{tool['name']}[/bold]")
        console.print(f"   [dim]{tool['description']}[/dim]\n")


@app.command()
def memory_stats():
    """Show memory statistics"""
    
    config = Config.load()
    from rann_agent.memory.manager import MemoryManager
    
    memory = MemoryManager(config)
    stats = memory.get_stats()
    
    console.print(Panel.fit(
        f"[bold cyan]🧠 Memory Statistics[/bold cyan]\n\n"
        f"[yellow]Sessions:[/yellow] {stats.get('sessions', 0)}\n"
        f"[yellow]Successful Fixes:[/yellow] {stats.get('successful_fixes', 0)}\n"
        f"[yellow]Learned Patterns:[/yellow] {stats.get('patterns', 0)}",
        border_style="cyan"
    ))


@app.command()
def init(
    path: str = typer.Argument(".", help="Project path"),
):
    """Initialize Rann Agent in a project"""
    
    project_path = Path(path).resolve()
    project_path.mkdir(parents=True, exist_ok=True)
    
    console.print(f"[cyan]Initializing Rann Agent in {project_path}...[/cyan]\n")
    
    # Create .env
    env_path = project_path / ".env"
    if not env_path.exists():
        env_path.write_text("""# Rann Agent Configuration

# === LLM Provider API Keys ===
ANTHROPIC_API_KEY=sk-ant-xxxxx
# OPENAI_API_KEY=sk-xxxxx

# === Database ===
DATABASE_URL=sqlite:///~/.rann-agent/data/sessions.db

# === Logging ===
LOG_LEVEL=INFO
""")
        console.print("✅ Created .env")
    
    # Create config.yaml
    config_path = project_path / "config.yaml"
    if not config_path.exists():
        import shutil
        example_config = Path(__file__).parent.parent.parent / "config.yaml.example"
        if example_config.exists():
            shutil.copy(example_config, config_path)
            console.print("✅ Created config.yaml")
    
    console.print(f"\n[bold green]✨ Rann Agent initialized![/bold green]")
    console.print("\n[yellow]Next steps:[/yellow]")
    console.print("1. Edit .env and add your API keys")
    console.print("2. Run: rann-agent chat 'your task here'")
    console.print("3. Or start server: rann-agent serve")


@app.command()
def version():
    """Show version information"""
    from rann_agent import __version__
    
    console.print(Panel.fit(
        f"[bold cyan]Rann Agent[/bold cyan]\n\n"
        f"[yellow]Version:[/yellow] {__version__}\n"
        f"[yellow]Python:[/yellow] 3.11+\n"
        f"[yellow]License:[/yellow] MIT",
        border_style="cyan"
    ))


if __name__ == "__main__":
    app()
