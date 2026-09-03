"""
Terminal User Interface (TUI) for RANN Agent
Rich-based interactive terminal UI with chat, progress, and streaming.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from rann_agent.core.agent import Agent
from rann_agent.core.config import Config


logger = structlog.get_logger()


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_name: Optional[str] = None


class ChatPanel:
    """Scrollable chat panel with message history."""

    def __init__(self, console: Console, max_messages: int = 100):
        self.console = console
        self.max_messages = max_messages
        self.messages: list[ChatMessage] = []

    def add_user(self, content: str) -> None:
        self.messages.append(ChatMessage(role="user", content=content))
        self._trim()

    def add_assistant(self, content: str) -> None:
        self.messages.append(ChatMessage(role="assistant", content=content))
        self._trim()

    def add_tool(self, content: str, tool_name: str) -> None:
        self.messages.append(ChatMessage(role="tool", content=content, tool_name=tool_name))
        self._trim()

    def add_system(self, content: str) -> None:
        self.messages.append(ChatMessage(role="system", content=content))
        self._trim()

    def _trim(self) -> None:
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def clear(self) -> None:
        self.messages.clear()

    def render(self) -> Panel:
        if not self.messages:
            return Panel("[dim italic]No messages yet.[/dim italic]", title="Chat", border_style="blue")

        role_colors = {"user": "cyan", "assistant": "green", "tool": "yellow", "system": "dim"}
        role_labels = {"user": "👤 User", "assistant": "🤖 Agent", "tool": "🔧 Tool", "system": "⚙️ System"}

        lines = []
        for msg in self.messages:
            color = role_colors.get(msg.role, "white")
            label = role_labels.get(msg.role, msg.role.title())
            if msg.role == "tool" and msg.tool_name:
                label = f"🔧 {msg.tool_name}"
            ts = msg.timestamp.strftime("%H:%M:%S")
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            lines.append(f"[{color}]{label}[/{color}] [dim]{ts}[/dim]")
            lines.append(f"  {content}")

        return Panel("\n".join(lines), title=f"Chat ({len(self.messages)} msgs)", border_style="blue")


class ProgressPanel:
    """Shows agent activity: state, turn, tokens, active tool."""

    def __init__(self, console: Console):
        self.console = console
        self.state = "IDLE"
        self.turn = 0
        self.max_turns = 50
        self.active_tool: Optional[str] = None
        self.input_tokens = 0
        self.output_tokens = 0

    def update(self, state: str, turn: int = 0, tool: Optional[str] = None,
               in_tok: int = 0, out_tok: int = 0) -> None:
        self.state = state.upper()
        if turn:
            self.turn = turn
        if tool is not None:
            self.active_tool = tool
        if in_tok or out_tok:
            self.input_tokens, self.output_tokens = in_tok, out_tok

    def reset(self) -> None:
        self.__init__(self.console)

    def render(self) -> Panel:
        state_colors = {
            "IDLE": "dim", "INITIALIZING": "blue", "UNDERSTANDING": "cyan",
            "PLANNING": "magenta", "EXECUTING": "green", "OBSERVING": "yellow",
            "VERIFYING": "bright_blue", "COMPLETED": "bold green", "FAILED": "bold red",
        }
        color = state_colors.get(self.state, "white")
        lines = [
            f"[bold]State:[/bold] [{color}]{self.state}[/{color}]",
            f"[bold]Turn:[/bold] {self.turn}/{self.max_turns}",
        ]
        if self.active_tool:
            lines.append(f"[bold]Tool:[/bold] [yellow]{self.active_tool}[/yellow]")
        total = self.input_tokens + self.output_tokens
        if total:
            lines.append(f"[bold]Tokens:[/bold] {total:,} ([green]in:{self.input_tokens:,}[/green] [blue]out:{self.output_tokens:,}[/blue])")
        if self.max_turns:
            lines.append(f"[bold]Budget:[/bold] {(self.turn / self.max_turns) * 100:.1f}%")
        return Panel("\n".join(lines), title="Progress", border_style="blue", padding=(1, 2))


class StatusBar:
    """Bottom status bar with session info, time, and hints."""

    def __init__(self, console: Console):
        self.console = console
        self.session_id: Optional[str] = None
        self.provider = "anthropic"
        self.model = "claude-sonnet-4"
        self.running = False

    def set_session(self, session_id: str, provider: str, model: str) -> None:
        self.session_id, self.provider, self.model = session_id, provider, model

    def set_running(self, running: bool) -> None:
        self.running = running

    def render(self) -> Panel:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "[bold yellow]● RUNNING[/bold yellow]" if self.running else "[dim]○ IDLE[/dim]"
        parts = [
            f"[bold]⏱[/bold] {now}",
            f"[bold]📋[/bold] {self.session_id or 'No session'}",
            f"[bold]🤖[/bold] {self.provider}/{self.model}",
            status,
            "[dim]Ctrl+C: cancel | Ctrl+L: clear | /quit: exit[/dim]",
        ]
        return Panel("  |  ".join(parts), border_style="cyan", padding=(0, 1), height=3)


class TUI:
    """Main Terminal User Interface - composes ChatPanel, ProgressPanel, StatusBar."""

    def __init__(self, config: Optional[Config] = None, provider: Optional[str] = None, model: Optional[str] = None):
        self.config = config or Config.load()
        self.provider = provider or self.config.agent.llm.provider
        self.model = model or self.config.agent.llm.model
        self.console = Console(force_terminal=True)
        self.chat = ChatPanel(self.console)
        self.progress = ProgressPanel(self.console)
        self.status = StatusBar(self.console)
        self.agent: Optional[Agent] = None
        self._running = False
        self._cancel = asyncio.Event()
        logger.info("tui_init", provider=self.provider, model=self.model)

    def _render(self):
        """Build complete render group."""
        header = Panel(
            f"[bold cyan]🤖 RANN Agent[/bold cyan] [dim]v1.0.0[/dim]  |  {self.provider}/{self.model}",
            border_style="cyan", padding=(0, 2), height=3,
        )
        return header, self.chat.render(), self.progress.render(), self.status.render()

    async def _execute(self, goal: str, context: Optional[str] = None) -> None:
        """Execute task with streaming UI."""
        if not self.agent:
            self.agent = Agent(config=self.config, provider=self.provider, model=self.model)

        self.status.set_running(True)
        self.progress.reset()
        self.chat.add_user(goal)
        self.console.print(f"\n[bold green]>[/bold green] {goal}")

        try:
            tokens = []
            self.progress.update("EXECUTING")
            async for token in self.agent.stream(goal, context):
                if self._cancel.is_set():
                    self.chat.add_system("Task cancelled.")
                    break
                tokens.append(token)
                self.console.print(token, end="", style="green")

            if tokens and not self._cancel.is_set():
                self.chat.add_assistant("".join(tokens))
                self.progress.update("COMPLETED")
                self.console.print()
        except Exception as e:
            logger.error("tui_execute_error", error=str(e))
            self.chat.add_system(f"Error: {e}")
            self.progress.update("FAILED")
        finally:
            self.status.set_running(False)
            if self.agent.session_id:
                self.status.set_session(self.agent.session_id, self.provider, self.model)

    async def _read_line(self) -> Optional[str]:
        """Async line read from stdin."""
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, sys.stdin.readline)
        except Exception:
            return None

    async def run(self) -> None:
        """Interactive TUI loop: display -> read -> execute -> repeat."""
        self._running = True
        self.console.print(Panel.fit(
            "[bold cyan]🤖 RANN Agent TUI[/bold cyan]\nType task, Enter to execute. /quit to exit.",
            border_style="cyan",
        ))

        while self._running:
            try:
                self.console.print("\n[bold green]>[/bold green] ", end="")
                goal = await self._read_line()
                if not goal:
                    continue
                goal = goal.strip()
                if not goal:
                    continue

                # Handle commands
                if goal.lower() in ("/quit", "/exit", "q"):
                    self.console.print("[cyan]Goodbye![/cyan]")
                    break
                if goal.lower() in ("/clear", "c"):
                    self.chat.clear()
                    continue

                self._cancel.clear()
                await self._execute(goal)

            except KeyboardInterrupt:
                self._cancel.set()
                self.console.print("\n[yellow]Cancelled.[/yellow]")
                continue
            except EOFError:
                break
            except Exception as e:
                logger.error("tui_error", error=str(e))
                self.console.print(f"[red]Error: {e}[/red]")

        self._running = False

    def run_sync(self) -> None:
        """Sync entry point."""
        asyncio.run(self.run())


def main() -> None:
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="RANN Agent TUI")
    parser.add_argument("goal", nargs="?", help="Task to execute")
    parser.add_argument("--provider", "-p", help="LLM provider")
    parser.add_argument("--model", "-m", help="Model name")
    args = parser.parse_args()

    tui = TUI(provider=args.provider, model=args.model)
    if args.goal:
        asyncio.run(tui._execute(args.goal))
    else:
        tui.run_sync()


if __name__ == "__main__":
    main()