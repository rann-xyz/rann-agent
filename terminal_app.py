"""
Terminal localhost application for Rann Agent.
Interactive CLI interface with rich UI.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import box

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rann_agent.agent import RannAgent
from rann_agent.intelligence import (
    CodebaseContext,
    CodeCompletion,
    AutonomousCoder
)


console = Console()


class TerminalApp:
    """
    Interactive terminal application for Rann Agent.
    """
    
    def __init__(self):
        self.agent = None
        self.codebase_context = None
        self.code_completion = None
        self.autonomous_coder = None
        self.running = True
        self.current_workspace = Path.cwd()
        
    async def initialize(self):
        """Initialize agent and modules."""
        console.print("[bold cyan]🚀 Initializing Rann Agent...[/bold cyan]")
        
        try:
            self.agent = RannAgent()
            self.codebase_context = CodebaseContext(str(self.current_workspace))
            self.code_completion = CodeCompletion()
            self.autonomous_coder = AutonomousCoder()
            
            console.print("[bold green]✅ Agent ready![/bold green]\n")
        except Exception as e:
            console.print(f"[bold red]❌ Initialization failed: {e}[/bold red]")
            raise
    
    def show_banner(self):
        """Display welcome banner."""
        banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ██████╗  █████╗ ███╗   ██╗███╗   ██╗                  ║
║   ██╔══██╗██╔══██╗████╗  ██║████╗  ██║                  ║
║   ██████╔╝███████║██╔██╗ ██║██╔██╗ ██║                  ║
║   ██╔══██╗██╔══██║██║╚██╗██║██║╚██╗██║                  ║
║   ██║  ██║██║  ██║██║ ╚████║██║ ╚████║                  ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝                  ║
║                                                           ║
║        🤖 AUTONOMOUS AI CODING AGENT 🚀                   ║
║        By Papa Agis (@rann_xyz)                          ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
        """
        
        console.print(banner, style="bold cyan")
        console.print("\n[bold yellow]🔥 THE MOST ADVANCED AI AGENT[/bold yellow]")
        console.print("[dim]Type 'help' for commands, 'exit' to quit[/dim]\n")
    
    def show_help(self):
        """Display help menu."""
        table = Table(title="📚 Available Commands", box=box.ROUNDED)
        
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Example", style="dim")
        
        # General commands
        table.add_row("help", "Show this help menu", "help")
        table.add_row("clear", "Clear screen", "clear")
        table.add_row("status", "Show agent status", "status")
        table.add_row("workspace", "Change workspace directory", "workspace /path/to/dir")
        table.add_row("exit", "Exit application", "exit")
        
        # Coding commands
        table.add_section()
        table.add_row("[bold]CODING COMMANDS[/bold]", "", "")
        table.add_row("code", "Autonomous coding task", "code Build REST API")
        table.add_row("implement", "Implement feature", "implement User auth")
        table.add_row("debug", "Debug error", "debug <error_message>")
        table.add_row("test", "Generate tests", "test my_function")
        table.add_row("review", "Review code", "review code.py")
        
        # Codebase commands
        table.add_section()
        table.add_row("[bold]CODEBASE COMMANDS[/bold]", "", "")
        table.add_row("index", "Index codebase", "index")
        table.add_row("find", "Find symbol", "find UserService")
        table.add_row("search", "Search code", "search authentication")
        table.add_row("context", "Get file context", "context api.py")
        table.add_row("summary", "Codebase summary", "summary")
        
        # Completion commands
        table.add_section()
        table.add_row("[bold]COMPLETION COMMANDS[/bold]", "", "")
        table.add_row("complete", "Code completion", "complete def hello():")
        table.add_row("suggest", "Suggest improvements", "suggest code.py")
        table.add_row("explain", "Explain code", "explain <code>")
        
        console.print(table)
    
    def show_status(self):
        """Display agent status."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header"),
            Layout(name="body")
        )
        
        # Header
        header_text = Text("🤖 Rann Agent Status", style="bold cyan", justify="center")
        layout["header"].update(Panel(header_text))
        
        # Body
        status_table = Table(box=box.SIMPLE)
        status_table.add_column("Property", style="cyan")
        status_table.add_column("Value", style="green")
        
        status_table.add_row("Workspace", str(self.current_workspace))
        status_table.add_row("Agent", "✅ Ready" if self.agent else "❌ Not ready")
        status_table.add_row("Codebase Indexed", "✅" if self.codebase_context.file_index else "❌")
        
        if self.autonomous_coder and self.autonomous_coder.task_history:
            summary = asyncio.run(self.autonomous_coder.get_task_summary())
            status_table.add_row("Tasks Completed", str(summary['completed']))
            status_table.add_row("Success Rate", f"{summary['success_rate']*100:.1f}%")
        
        layout["body"].update(Panel(status_table))
        
        console.print(layout)
    
    async def handle_code_command(self, args: str):
        """Handle autonomous coding command."""
        if not args:
            console.print("[red]❌ Usage: code <description>[/red]")
            return
        
        console.print(f"\n[bold cyan]🤖 Starting autonomous coding...[/bold cyan]")
        console.print(f"[dim]Task: {args}[/dim]\n")
        
        try:
            with console.status("[bold green]Coding in progress...") as status:
                # Simple implementation - split by comma or use as single requirement
                requirements = [req.strip() for req in args.split(',')] if ',' in args else [args]
                
                task = await self.autonomous_coder.implement_feature(
                    task_description=args,
                    requirements=requirements
                )
            
            # Show results
            result_table = Table(title="✅ Task Completed", box=box.ROUNDED)
            result_table.add_column("Metric", style="cyan")
            result_table.add_column("Value", style="green")
            
            result_table.add_row("Status", str(task.status.value))
            result_table.add_row("Files Modified", str(len(task.files_modified)))
            result_table.add_row("Tests Written", str(task.tests_written))
            result_table.add_row("Bugs Fixed", str(task.bugs_fixed))
            
            console.print(result_table)
            
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
    
    async def handle_index_command(self):
        """Handle codebase indexing."""
        console.print("\n[bold cyan]📚 Indexing codebase...[/bold cyan]")
        
        try:
            with console.status("[bold green]Scanning files..."):
                stats = await self.codebase_context.index_codebase()
            
            # Show results
            table = Table(title="✅ Indexing Complete", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Files", str(stats['total_files']))
            table.add_row("Total Lines", str(stats['total_lines']))
            
            for lang, count in stats['languages'].items():
                table.add_row(f"  {lang}", str(count))
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
    
    async def handle_find_command(self, symbol: str):
        """Handle symbol search."""
        if not symbol:
            console.print("[red]❌ Usage: find <symbol_name>[/red]")
            return
        
        console.print(f"\n[cyan]🔍 Searching for '{symbol}'...[/cyan]")
        
        try:
            results = await self.codebase_context.find_symbol(symbol)
            
            if not results:
                console.print("[yellow]⚠️  No results found[/yellow]")
                return
            
            table = Table(title=f"Found {len(results)} result(s)", box=box.ROUNDED)
            table.add_column("File", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Line", style="yellow")
            
            for result in results:
                table.add_row(
                    result['file'],
                    result['type'],
                    str(result['line'])
                )
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
    
    async def handle_complete_command(self, code: str):
        """Handle code completion."""
        if not code:
            console.print("[red]❌ Usage: complete <code>[/red]")
            return
        
        console.print("\n[cyan]💡 Generating completions...[/cyan]")
        
        try:
            suggestions = await self.code_completion.suggest_completion(
                code_before=code,
                language="python"
            )
            
            if not suggestions:
                console.print("[yellow]⚠️  No suggestions[/yellow]")
                return
            
            for i, suggestion in enumerate(suggestions, 1):
                panel = Panel(
                    suggestion['code'],
                    title=f"Suggestion {i} - {suggestion['description']}",
                    border_style="green"
                )
                console.print(panel)
            
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
    
    async def process_command(self, command: str):
        """Process user command."""
        parts = command.strip().split(maxsplit=1)
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "help":
            self.show_help()
        
        elif cmd == "clear":
            console.clear()
            self.show_banner()
        
        elif cmd == "status":
            self.show_status()
        
        elif cmd == "exit" or cmd == "quit":
            console.print("\n[bold cyan]👋 Goodbye![/bold cyan]")
            self.running = False
        
        elif cmd == "workspace":
            if args:
                self.current_workspace = Path(args)
                self.codebase_context = CodebaseContext(str(self.current_workspace))
                console.print(f"[green]✅ Workspace changed to: {self.current_workspace}[/green]")
            else:
                console.print(f"[cyan]Current workspace: {self.current_workspace}[/cyan]")
        
        # Coding commands
        elif cmd in ["code", "implement"]:
            await self.handle_code_command(args)
        
        elif cmd == "index":
            await self.handle_index_command()
        
        elif cmd == "find":
            await self.handle_find_command(args)
        
        elif cmd == "complete":
            await self.handle_complete_command(args)
        
        elif cmd == "summary":
            summary = await self.codebase_context.get_codebase_summary()
            table = Table(title="📊 Codebase Summary", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            for key, value in summary.items():
                if isinstance(value, dict):
                    for k, v in value.items():
                        table.add_row(f"  {k}", str(v))
                else:
                    table.add_row(key.replace('_', ' ').title(), str(value))
            
            console.print(table)
        
        elif cmd == "search":
            results = await self.codebase_context.search_code(args)
            if results:
                table = Table(title=f"🔍 Search Results for '{args}'", box=box.ROUNDED)
                table.add_column("File", style="cyan")
                table.add_column("Type", style="green")
                table.add_column("Name", style="yellow")
                table.add_column("Line", style="dim")
                
                for r in results:
                    table.add_row(r['file'], r['type'], r['name'], str(r['line']))
                
                console.print(table)
            else:
                console.print("[yellow]⚠️  No results[/yellow]")
        
        else:
            console.print(f"[red]❌ Unknown command: {cmd}[/red]")
            console.print("[dim]Type 'help' for available commands[/dim]")
    
    async def run(self):
        """Main run loop."""
        console.clear()
        self.show_banner()
        
        await self.initialize()
        
        while self.running:
            try:
                # Prompt
                command = await asyncio.to_thread(
                    Prompt.ask,
                    "\n[bold green]rann>[/bold green]"
                )
                
                if command.strip():
                    await self.process_command(command)
            
            except KeyboardInterrupt:
                console.print("\n[yellow]⚠️  Use 'exit' to quit[/yellow]")
                continue
            
            except EOFError:
                break
            
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")


async def main():
    """Main entry point."""
    app = TerminalApp()
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold cyan]👋 Goodbye![/bold cyan]")
