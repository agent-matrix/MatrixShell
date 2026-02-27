"""Tool execution UI components.

Provides visual feedback when tools are being used, matching Claude Code's
multi-agent display style with fun progress messages and tool counters.
"""

from __future__ import annotations

import random
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Generator, List, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


# Fun progress messages like Claude Code
PROGRESS_MESSAGES = [
    "Crafting...",
    "Getting a wriggle on...",
    "Synthesizing...",
    "Brewing...",
    "Contemplating...",
    "Finagling...",
    "Wandering...",
    "Pondering...",
    "Concocting...",
    "Assembling...",
    "Weaving...",
    "Orchestrating...",
    "Calibrating...",
    "Manifesting...",
    "Conjuring...",
    "Transmuting...",
    "Processing...",
    "Computing...",
    "Analyzing...",
    "Investigating...",
]


@dataclass
class ToolCall:
    """Represents a tool being called."""
    tool_name: str
    namespace: str
    description: str = ""
    status: str = "pending"  # pending, running, success, error
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def full_name(self) -> str:
        return f"{self.namespace}.{self.tool_name}"

    @property
    def duration_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None


@dataclass
class TaskSession:
    """Tracks a task session with multiple tool calls."""
    task_description: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    status: str = "running"  # running, completed, error
    current_message: str = ""

    @property
    def tools_used(self) -> int:
        return len([t for t in self.tool_calls if t.status in ("success", "error")])


class ToolExecutionUI:
    """Visual feedback for tool execution.

    Displays panels showing tool usage in Claude Code style:
    - Task header with description
    - "Used X tools" counter
    - Fun progress messages
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._current_session: Optional[TaskSession] = None
        self._message_index = 0

    def _get_progress_message(self) -> str:
        """Get a random fun progress message."""
        return random.choice(PROGRESS_MESSAGES)

    def _render_task_panel(self) -> Panel:
        """Render the main task panel like Claude Code."""
        if not self._current_session:
            return Panel("No active task")

        session = self._current_session

        # Build content
        content_parts = []

        # Task description with spinner
        if session.status == "running":
            spinner_text = Text()
            spinner_text.append("" + " ", style="cyan")  # Spinner dot
            spinner_text.append(session.current_message or self._get_progress_message(), style="dim italic")
            content_parts.append(spinner_text)
        elif session.status == "completed":
            done_text = Text()
            done_text.append("Completed", style="green")
            content_parts.append(done_text)
        elif session.status == "error":
            error_text = Text()
            error_text.append("Failed", style="red")
            content_parts.append(error_text)

        # Show current tool if running
        running_tools = [t for t in session.tool_calls if t.status == "running"]
        if running_tools:
            tool = running_tools[-1]
            tool_text = Text()
            tool_text.append("\nUsing: ", style="dim")
            tool_text.append(tool.full_name, style="yellow")
            if tool.description:
                tool_text.append(f" - {tool.description}", style="dim")
            content_parts.append(tool_text)

        content = Text()
        for part in content_parts:
            content.append_text(part)

        # Title with task name
        title = Text()
        title.append("Task", style="bold cyan")

        # Subtitle with tool count
        subtitle = Text()
        subtitle.append(f"Used {session.tools_used} tool", style="dim")
        if session.tools_used != 1:
            subtitle.append("s", style="dim")

        return Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style="cyan" if session.status == "running" else ("green" if session.status == "completed" else "red"),
            padding=(0, 1),
        )

    def _render_live_panel(self, session: TaskSession, tool_call: Optional[ToolCall] = None) -> Panel:
        """Render panel for live display."""
        content = Text()

        # Progress message with spinner effect
        if session.status == "running":
            content.append(session.current_message, style="dim italic")

        # Current tool info
        if tool_call and tool_call.status == "running":
            content.append("\n")
            content.append("Using: ", style="dim")
            content.append(tool_call.full_name, style="yellow bold")
            if tool_call.description:
                content.append(f"\n{tool_call.description}", style="dim")

        # Title
        title = Text()
        title.append("Task", style="bold cyan")
        title.append(" ", style="")
        title.append(session.task_description, style="bold white")

        # Subtitle with counter
        subtitle = Text()
        subtitle.append(f"Used {session.tools_used} tool", style="dim")
        if session.tools_used != 1:
            subtitle.append("s", style="dim")

        return Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style="cyan",
            padding=(0, 1),
        )

    @contextmanager
    def task_session(self, description: str) -> Generator[TaskSession, None, None]:
        """Start a task session that tracks multiple tool calls.

        Usage:
            with tool_ui.task_session("Searching for files") as session:
                with tool_ui.tool_call("find_files", "storagepilot"):
                    result = call_tool(...)
        """
        session = TaskSession(
            task_description=description,
            current_message=self._get_progress_message(),
        )
        self._current_session = session

        with Live(
            self._render_live_panel(session),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        ) as live:
            self._live = live

            # Update messages periodically
            def update_message():
                if session.status == "running":
                    session.current_message = self._get_progress_message()
                    live.update(self._render_live_panel(session))

            try:
                yield session
                session.status = "completed"
            except Exception as e:
                session.status = "error"
                raise
            finally:
                # Final update
                live.update(self._render_live_panel(session))
                self._live = None
                self._current_session = None

        # Show final result
        self._show_task_complete(session)

    @contextmanager
    def tool_call(
        self,
        tool_name: str,
        namespace: str,
        description: str = "",
    ) -> Generator[ToolCall, None, None]:
        """Track a single tool call within a task session.

        Usage:
            with tool_ui.tool_call("find_files", "storagepilot") as tc:
                result = broker.call_tool(...)
                tc.result = result
        """
        tool = ToolCall(
            tool_name=tool_name,
            namespace=namespace,
            description=description,
            status="running",
            start_time=time.time(),
        )

        if self._current_session:
            self._current_session.tool_calls.append(tool)
            # Update the live display
            if hasattr(self, "_live") and self._live:
                self._current_session.current_message = self._get_progress_message()
                self._live.update(self._render_live_panel(self._current_session, tool))

        try:
            yield tool
            tool.status = "success"
            tool.end_time = time.time()
        except Exception as e:
            tool.status = "error"
            tool.error = str(e)
            tool.end_time = time.time()
            raise
        finally:
            # Update display after tool completes
            if hasattr(self, "_live") and self._live and self._current_session:
                self._current_session.current_message = self._get_progress_message()
                self._live.update(self._render_live_panel(self._current_session))

    def _show_task_complete(self, session: TaskSession) -> None:
        """Show task completion summary."""
        if session.status == "completed":
            text = Text()
            text.append("Task ", style="bold")
            text.append(session.task_description, style="cyan")
            text.append(" completed", style="green")
            text.append(f" (used {session.tools_used} tool", style="dim")
            if session.tools_used != 1:
                text.append("s", style="dim")
            text.append(")", style="dim")
            self.console.print(text)
        elif session.status == "error":
            text = Text()
            text.append("Task ", style="bold")
            text.append(session.task_description, style="cyan")
            text.append(" failed", style="red")
            self.console.print(text)

    def show_tool_execution(
        self,
        tool_name: str,
        namespace: str,
        description: str = "",
        execute_fn: Optional[Callable[[], Any]] = None,
    ) -> Optional[Any]:
        """Simple one-shot tool execution with visual feedback.

        Usage:
            result = tool_ui.show_tool_execution(
                "find_files",
                "storagepilot",
                "Finding large files",
                lambda: broker.call_tool("storagepilot.find_files", args)
            )
        """
        full_name = f"{namespace}.{tool_name}"

        with Live(
            self._render_single_tool_panel(full_name, description, "running"),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        ) as live:
            start_time = time.time()
            result = None
            error = None

            # Cycle through messages
            message_cycle = 0
            try:
                if execute_fn:
                    # Run the actual function
                    result = execute_fn()

                duration_ms = (time.time() - start_time) * 1000
                live.update(self._render_single_tool_panel(
                    full_name, description, "success", duration_ms=duration_ms
                ))
                time.sleep(0.2)
                return result

            except Exception as e:
                error = str(e)
                live.update(self._render_single_tool_panel(
                    full_name, description, "error", error=error
                ))
                time.sleep(0.3)
                raise

    def _render_single_tool_panel(
        self,
        full_name: str,
        description: str,
        status: str,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> Panel:
        """Render a single tool execution panel."""
        content = Text()

        if status == "running":
            content.append(self._get_progress_message(), style="dim italic")
        elif status == "success":
            content.append("Completed", style="green")
            if duration_ms:
                content.append(f" ({duration_ms:.0f}ms)", style="dim")
        elif status == "error":
            content.append("Failed: ", style="red")
            content.append(error or "Unknown error", style="red dim")

        if description and status == "running":
            content.append(f"\n{description}", style="dim")

        title = Text()
        title.append("Using tool: ", style="bold cyan")
        title.append(full_name, style="bold yellow")

        border = "cyan" if status == "running" else ("green" if status == "success" else "red")

        return Panel(
            content,
            title=title,
            border_style=border,
            padding=(0, 1),
        )


def show_available_tools(console: Console, tools: List[Any], title: str = "Available Tools") -> None:
    """Display a table of available tools grouped by namespace."""
    if not tools:
        console.print("[dim]No external tools available.[/dim]")
        return

    # Group by namespace
    by_namespace = {}
    for tool in tools:
        ns = getattr(tool, "namespace", "unknown")
        if ns not in by_namespace:
            by_namespace[ns] = []
        by_namespace[ns].append(tool)

    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Namespace", style="yellow")
    table.add_column("Tool", style="green")
    table.add_column("Description", style="dim", max_width=40)

    for namespace in sorted(by_namespace.keys()):
        for i, tool in enumerate(by_namespace[namespace]):
            name = getattr(tool, "name", str(tool))
            desc = getattr(tool, "description", "")
            if len(desc) > 40:
                desc = desc[:37] + "..."
            # Only show namespace on first tool of each group
            ns_display = namespace if i == 0 else ""
            table.add_row(ns_display, name, desc)

    console.print(table)
    console.print()


def show_plugins_summary(console: Console, plugins: List[Any]) -> None:
    """Show a compact summary of connected plugins."""
    if not plugins:
        return

    enabled = [p for p in plugins if getattr(p, "enabled", False)]
    if not enabled:
        return

    text = Text()
    text.append("Connected plugins: ", style="bold")

    for i, p in enumerate(enabled):
        if i > 0:
            text.append(", ", style="dim")
        name = getattr(p, "name", "?")
        text.append(name, style="cyan")

    console.print(text)


def show_tool_discovery(console: Console, broker: Any) -> None:
    """Show tool discovery summary when starting MatrixShell."""
    tools = broker.get_all_tools() if hasattr(broker, "get_all_tools") else []

    # Count by source
    builtin = [t for t in tools if getattr(t, "source", "") == "builtin"]
    plugin = [t for t in tools if getattr(t, "source", "") == "plugin"]

    if plugin:
        text = Text()
        text.append("Tools: ", style="bold")
        text.append(f"{len(builtin)} built-in", style="dim")
        text.append(" + ", style="dim")
        text.append(f"{len(plugin)} from plugins", style="cyan")

        # Show plugin namespaces
        namespaces = set(getattr(t, "namespace", "") for t in plugin)
        namespaces.discard("")
        if namespaces:
            text.append(" (", style="dim")
            text.append(", ".join(sorted(namespaces)), style="yellow")
            text.append(")", style="dim")

        console.print(text)
