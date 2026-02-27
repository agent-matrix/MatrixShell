"""Embedded tool registry for MatrixShell.

This is the *default* architecture for MatrixShell:
- The CLI calls these tools in-process (zero IPC, no ports, no servers).
- The same registry can optionally be exposed over MCP via `matrixsh --serve`.
"""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

from ..config import Settings
from ..history import HistoryItem, append_history, load_recent
from ..llm import MatrixLLM, UnauthorizedError
from ..safety import denylist_match, is_command_not_found, looks_like_natural_language
from ..shell import ExecResult, detect_default_mode, execute, handle_cd, list_files, os_name


Decision = Literal["allow", "confirm", "block"]


@dataclass
class _ConfirmState:
    """Tracks confirmation tokens for policy enforcement."""
    tokens: Dict[str, float] = field(default_factory=dict)


class PolicyTools:
    """Central policy gate. Enforces denylist + confirmation for risky commands.

    In embedded mode, this replicates MatrixShell UX while enabling future MCP enforcement.
    """

    _HIGH_RISK_PATTERNS = [
        r"\brm\b\s+(-rf|-fr)\b",
        r"\bdel\b\s+/[fsq]\b",
        r"\bformat\b\s+",
        r"\bmkfs\b",
        r"\bdd\b\s+if=",
        r"\bsudo\b",
        r"\bchown\b",
        r"\bchmod\b\s+7",
        r"\breg\b\s+add\b",
        r"\bschtasks\b",
        r"\bshutdown\b",
        r"\breboot\b",
    ]

    def __init__(self, confirm_state: _ConfirmState) -> None:
        self._confirm = confirm_state

    def _issue_confirm_token(self, ttl_s: float = 120.0) -> str:
        tok = f"cnf_{secrets.token_urlsafe(18)}"
        self._confirm.tokens[tok] = time.time() + ttl_s
        return tok

    def consume_confirm_token(self, token: str) -> bool:
        exp = self._confirm.tokens.get(token)
        if not exp:
            return False
        if time.time() > exp:
            self._confirm.tokens.pop(token, None)
            return False
        self._confirm.tokens.pop(token, None)
        return True

    def evaluate(self, cwd: str, command: str) -> dict[str, Any]:
        """Evaluate a command and return policy decision."""
        blocked_reason = denylist_match(command)
        if blocked_reason:
            return {"decision": "block", "reason": blocked_reason, "risk": "blocked"}

        for pat in self._HIGH_RISK_PATTERNS:
            if re.search(pat, command, re.IGNORECASE):
                token = self._issue_confirm_token()
                return {
                    "decision": "confirm",
                    "reason": "Command appears potentially destructive or privileged; confirmation required.",
                    "risk": "high",
                    "confirm_token": token,
                }

        return {"decision": "allow", "reason": None, "risk": "low"}


class ShellTools:
    """Shell execution and navigation tools."""

    def __init__(self, shell_mode: str = "auto") -> None:
        self._shell_mode = shell_mode

    def get_mode(self) -> str:
        return self._shell_mode if self._shell_mode != "auto" else detect_default_mode()

    def os_name(self) -> str:
        return os_name()

    def default_mode(self) -> str:
        return detect_default_mode()

    def handle_cd(self, user_input: str, cwd: str) -> tuple[bool, str, str]:
        return handle_cd(user_input, cwd, self.get_mode())

    def list_files(self, cwd: str, limit: int = 200) -> list[str]:
        files = list_files(cwd)
        return files[:limit]

    def execute(
        self,
        command: str,
        cwd: str,
        confirm: bool = False,
        confirm_token: Optional[str] = None,
        policy: Optional[PolicyTools] = None,
    ) -> dict[str, Any]:
        """Execute a shell command with optional policy enforcement."""
        # Optional policy enforcement (used by CLI; MCP server enforces too)
        if policy is not None:
            pol = policy.evaluate(cwd=cwd, command=command)
            if pol["decision"] == "block":
                return {"exit_code": 126, "stdout": "", "stderr": pol.get("reason") or "blocked"}
            if pol["decision"] == "confirm":
                if not confirm:
                    return {"exit_code": 126, "stdout": "", "stderr": "confirmation_required"}
                if not confirm_token or not policy.consume_confirm_token(confirm_token):
                    return {"exit_code": 126, "stdout": "", "stderr": "invalid_confirm_token"}

        res = execute(command, self.get_mode(), cwd)
        return {"exit_code": res.code, "stdout": res.stdout, "stderr": res.stderr}

    def execute_direct(self, command: str, cwd: str) -> ExecResult:
        """Execute without policy checks (for CLI direct commands)."""
        return execute(command, self.get_mode(), cwd)


class SafetyTools:
    """Safety validation tools."""

    def looks_like_natural_language(self, text: str) -> bool:
        return looks_like_natural_language(text)

    def denylist_match(self, command: str) -> str | None:
        return denylist_match(command)

    def is_command_not_found(self, stderr: str, mode: str) -> bool:
        return is_command_not_found(stderr, mode)


class HistoryTools:
    """History persistence tools."""

    def append(self, cwd: str, kind: Literal["user", "assistant", "exec"], text: str) -> None:
        append_history(cwd, kind, text)

    def load(self, cwd: str, limit: int = 50) -> list[HistoryItem]:
        return load_recent(cwd, limit=limit)


class LLMTools:
    """LLM communication tools."""

    def __init__(self, settings: Settings, shell: ShellTools, history: HistoryTools):
        self._settings = settings
        self._shell = shell
        self._history = history
        self._llm: Optional[MatrixLLM] = None
        self._healthy: Optional[bool] = None

    def _get_llm(self) -> MatrixLLM:
        if self._llm is None:
            self._llm = MatrixLLM(
                self._settings.base_url,
                self._settings.api_key,
                token=self._settings.token,
                timeout_s=self._settings.timeout_s,
            )
        return self._llm

    def update_token(self, token: str) -> None:
        """Update the pairing token (used after re-pairing)."""
        self._settings.token = token
        if self._llm:
            self._llm.token = token

    def health(self) -> dict[str, Any]:
        """Check LLM gateway health."""
        llm = self._get_llm()
        t0 = time.time()
        ok = llm.health()
        self._healthy = ok
        return {"healthy": bool(ok), "latency_ms": int((time.time() - t0) * 1000)}

    def is_healthy(self) -> bool:
        """Quick health status check."""
        if self._healthy is None:
            self.health()
        return self._healthy or False

    def is_configured(self) -> bool:
        """Check if LLM has credentials configured."""
        return bool(self._settings.token or self._settings.api_key)

    def suggest(self, user_input: str, cwd: str) -> dict[str, Any]:
        """Get AI suggestion for shell command."""
        llm = self._get_llm()
        files = self._shell.list_files(cwd)
        recent = self._history.load(cwd, limit=12)
        history_context = "\n".join(
            [f"{h.kind}: {h.text}" for h in recent if getattr(h, "kind", "") in ("user", "assistant")]
        )

        suggestion = llm.suggest(
            model=self._settings.model,
            os_name=self._shell.os_name(),
            shell_mode=self._shell.get_mode(),
            cwd=cwd,
            files=files,
            user_input=user_input + ("\n\nRecent history:\n" + history_context if history_context else ""),
        )
        return {"explanation": suggestion.explanation, "command": suggestion.command, "risk": suggestion.risk}

    def suggest_raw(self, user_input: str, cwd: str, files: list[str], history_context: str):
        """Get raw Suggestion object (for CLI compatibility)."""
        llm = self._get_llm()
        return llm.suggest(
            model=self._settings.model,
            os_name=self._shell.os_name(),
            shell_mode=self._shell.get_mode(),
            cwd=cwd,
            files=files,
            user_input=user_input + ("\n\nRecent history:\n" + history_context if history_context else ""),
        )


class ConfigTools:
    """Configuration management tools."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def get(self) -> dict[str, Any]:
        s = self._settings
        return {
            "base_url": s.base_url,
            "model": s.model,
            "timeout_s": s.timeout_s,
            "has_api_key": bool(s.api_key),
            "has_token": bool(s.token),
        }

    def set(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        timeout_s: Optional[int] = None,
    ) -> dict[str, Any]:
        s = self._settings
        if base_url is not None:
            s.base_url = base_url
        if model is not None:
            s.model = model
        if api_key is not None:
            s.api_key = api_key
        if token is not None:
            s.token = token
        if timeout_s is not None:
            s.timeout_s = int(timeout_s)
        s.save()
        from ..config import config_path
        return {"success": True, "config_path": str(config_path())}


class ToolRegistry:
    """Single-process tool registry.

    This is the *default* architecture for MatrixShell:
    - The CLI calls these tools in-process (zero IPC, no ports, no servers).
    - The same registry can optionally be exposed over MCP via `matrixsh --serve`.
    """

    def __init__(self, settings: Optional[Settings] = None, shell_mode: str = "auto") -> None:
        self.settings = settings or Settings.load()
        self._confirm = _ConfirmState()
        self.shell = ShellTools(shell_mode=shell_mode)
        self.safety = SafetyTools()
        self.history = HistoryTools()
        self.policy = PolicyTools(confirm_state=self._confirm)
        self.llm = LLMTools(settings=self.settings, shell=self.shell, history=self.history)
        self.config = ConfigTools(settings=self.settings)
