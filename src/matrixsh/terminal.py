"""Terminal input module with readline-like features.

Provides:
- Command history with up/down arrow navigation
- Tab completion for files and directories
- Standard line editing (Ctrl+A, Ctrl+E, Ctrl+K, etc.)
- Persistent history across sessions
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.completion import Completer, Completion, PathCompleter, merge_completers
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


def _get_history_path() -> Path:
    """Get path to command history file."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "matrixsh" / "history"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "matrixsh" / "history"


class CommandCompleter(Completer):
    """Completer for shell commands and MatrixShell built-in commands."""

    BUILTIN_COMMANDS = [
        "/exit",
        "/quit",
        "/help",
        "/history",
        "/clear",
    ]

    COMMON_COMMANDS = [
        "ls", "cd", "pwd", "cat", "grep", "find", "mkdir", "rm", "cp", "mv",
        "echo", "head", "tail", "less", "more", "wc", "sort", "uniq",
        "git", "docker", "npm", "python", "pip", "make", "curl", "wget",
        "ssh", "scp", "tar", "gzip", "zip", "unzip",
    ]

    def __init__(self, cwd_getter: Optional[Callable[[], str]] = None):
        self.cwd_getter = cwd_getter or os.getcwd
        self._path_completer = PathCompleter(expanduser=True)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        word = document.get_word_before_cursor()

        # Complete built-in commands starting with /
        if text.startswith("/"):
            for cmd in self.BUILTIN_COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
            return

        # If at start of line, complete commands
        if not text.strip() or text == word:
            for cmd in self.COMMON_COMMANDS:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))

        # Path completion for arguments
        # Check if we're completing a path (contains / or starts with . or ~)
        words = text.split()
        if words:
            last_word = words[-1] if text.endswith(" ") is False else ""
            if last_word and (
                "/" in last_word or
                last_word.startswith(".") or
                last_word.startswith("~")
            ):
                # Use path completer
                yield from self._path_completer.get_completions(document, complete_event)


class TerminalInput:
    """Enhanced terminal input with history and completion.

    Usage:
        terminal = TerminalInput()
        while True:
            user_input = terminal.prompt("$ ")
            if user_input is None:  # EOF/Ctrl+D
                break
            process(user_input)
    """

    def __init__(
        self,
        cwd_getter: Optional[Callable[[], str]] = None,
        history_enabled: bool = True,
    ):
        self.cwd_getter = cwd_getter or os.getcwd
        self._session: Optional[PromptSession] = None
        self._history_enabled = history_enabled

        if HAS_PROMPT_TOOLKIT:
            self._setup_prompt_toolkit()
        else:
            self._session = None

    def _setup_prompt_toolkit(self) -> None:
        """Initialize prompt_toolkit session."""
        history = None
        if self._history_enabled:
            history_path = _get_history_path()
            history_path.parent.mkdir(parents=True, exist_ok=True)
            history = FileHistory(str(history_path))

        # Custom completer combining commands and paths
        completer = merge_completers([
            CommandCompleter(self.cwd_getter),
            PathCompleter(expanduser=True),
        ])

        # Style for the prompt
        style = Style.from_dict({
            "prompt": "bold green",
            "path": "cyan",
        })

        # Key bindings
        bindings = KeyBindings()

        @bindings.add("c-l")
        def clear_screen(event):
            """Clear the screen."""
            event.app.renderer.clear()

        self._session = PromptSession(
            history=history,
            completer=completer,
            complete_while_typing=False,  # Only complete on Tab
            style=style,
            key_bindings=bindings,
            enable_history_search=True,  # Ctrl+R for reverse search
        )

    def prompt(
        self,
        prompt_text: str = "$ ",
        default: str = "",
    ) -> Optional[str]:
        """Get input from user with history and completion.

        Returns:
            User input string, or None on EOF (Ctrl+D)
        """
        if HAS_PROMPT_TOOLKIT and self._session:
            try:
                return self._session.prompt(prompt_text, default=default)
            except EOFError:
                return None
            except KeyboardInterrupt:
                return None
        else:
            # Fallback to basic input
            try:
                return input(prompt_text)
            except EOFError:
                return None
            except KeyboardInterrupt:
                return None

    def prompt_html(
        self,
        html_prompt: str,
        default: str = "",
    ) -> Optional[str]:
        """Get input with HTML-formatted prompt.

        Example:
            terminal.prompt_html("<green><b>user@host</b></green>:<blue>~/dir</blue>$ ")
        """
        if HAS_PROMPT_TOOLKIT and self._session:
            try:
                return self._session.prompt(HTML(html_prompt), default=default)
            except (EOFError, KeyboardInterrupt):
                return None
        else:
            # Strip HTML tags for fallback
            import re
            plain = re.sub(r"<[^>]+>", "", html_prompt)
            try:
                return input(plain)
            except (EOFError, KeyboardInterrupt):
                return None

    def add_to_history(self, command: str) -> None:
        """Manually add a command to history."""
        if HAS_PROMPT_TOOLKIT and self._session and self._session.history:
            self._session.history.append_string(command)

    @property
    def has_advanced_features(self) -> bool:
        """Check if advanced terminal features are available."""
        return HAS_PROMPT_TOOLKIT and self._session is not None


def create_terminal(cwd_getter: Optional[Callable[[], str]] = None) -> TerminalInput:
    """Factory function to create a terminal input instance."""
    return TerminalInput(cwd_getter=cwd_getter)


# Simple API for basic usage
_default_terminal: Optional[TerminalInput] = None


def get_input(prompt_text: str = "$ ") -> Optional[str]:
    """Get input using the default terminal instance."""
    global _default_terminal
    if _default_terminal is None:
        _default_terminal = TerminalInput()
    return _default_terminal.prompt(prompt_text)
