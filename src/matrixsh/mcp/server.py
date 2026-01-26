"""Optional MCP server for MatrixShell (power users only).

Normal users do not need this. `matrixsh` runs single-process with embedded tools.
This module is only loaded when `matrixsh --serve` or `matrixsh-mcp` is invoked.
"""

from __future__ import annotations

import os
from typing import Any, Literal, Optional

from .registry import ToolRegistry


def serve_from_registry(registry: ToolRegistry, transport: str = "stdio") -> None:
    """Expose the embedded ToolRegistry over MCP.

    This is for power users who want to access MatrixShell tools from
    IDE extensions, other agents, or external clients.
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("MatrixShell", json_response=True)

    # ----------------------------
    # Shell tools
    # ----------------------------
    @mcp.tool()
    def shell_execute(
        command: str,
        cwd: Optional[str] = None,
        confirm: bool = False,
        confirm_token: Optional[str] = None,
        enforce_policy: bool = True,
    ) -> dict[str, Any]:
        """Execute a shell command with optional policy enforcement."""
        cwd2 = cwd or os.getcwd()
        policy = registry.policy if enforce_policy else None
        return registry.shell.execute(
            command=command,
            cwd=cwd2,
            confirm=confirm,
            confirm_token=confirm_token,
            policy=policy,
        )

    @mcp.tool()
    def shell_change_directory(path: str, current_cwd: str) -> dict[str, Any]:
        """Change working directory with validation."""
        handled, new_cwd, msg = registry.shell.handle_cd(f"cd {path}", current_cwd)
        if not handled or msg:
            return {"success": False, "new_cwd": current_cwd, "error": msg or "Invalid directory"}
        return {"success": True, "new_cwd": new_cwd, "error": None}

    @mcp.tool()
    def shell_list_files(cwd: Optional[str] = None, limit: int = 200) -> dict[str, Any]:
        """List files in directory for context."""
        cwd2 = cwd or os.getcwd()
        files = registry.shell.list_files(cwd2, limit=limit)
        return {"files": files, "truncated": len(files) >= limit}

    @mcp.tool()
    def shell_get_system_info() -> dict[str, Any]:
        """Get OS and shell information."""
        return {
            "os": registry.shell.os_name(),
            "default_shell": registry.shell.default_mode(),
            "home_dir": os.path.expanduser("~"),
        }

    # ----------------------------
    # Safety / policy tools
    # ----------------------------
    @mcp.tool()
    def safety_classify_input(text: str) -> dict[str, Any]:
        """Determine if input is natural language or shell command."""
        return {"is_natural_language": registry.safety.looks_like_natural_language(text)}

    @mcp.tool()
    def safety_validate_command(command: str, cwd: Optional[str] = None) -> dict[str, Any]:
        """Check if command is safe to execute."""
        cwd2 = cwd or os.getcwd()
        res = registry.policy.evaluate(cwd=cwd2, command=command)
        return {
            "decision": res["decision"],
            "risk_level": res["risk"],
            "reason": res.get("reason"),
            "confirm_token": res.get("confirm_token"),
        }

    @mcp.tool()
    def safety_parse_shell_error(stderr: str) -> dict[str, Any]:
        """Parse shell error to detect command-not-found."""
        return {
            "is_command_not_found": registry.safety.is_command_not_found(
                stderr, registry.shell.get_mode()
            )
        }

    # ----------------------------
    # LLM tools
    # ----------------------------
    @mcp.tool()
    def llm_suggest_command(user_input: str, cwd: Optional[str] = None) -> dict[str, Any]:
        """Get AI suggestion for shell command based on natural language."""
        cwd2 = cwd or os.getcwd()
        return registry.llm.suggest(user_input=user_input, cwd=cwd2)

    @mcp.tool()
    def llm_health_check() -> dict[str, Any]:
        """Check LLM gateway health."""
        return registry.llm.health()

    # ----------------------------
    # History tools
    # ----------------------------
    @mcp.tool()
    def history_append(
        cwd: str, kind: Literal["user", "assistant", "exec"], text: str
    ) -> dict[str, Any]:
        """Log an interaction to history."""
        registry.history.append(cwd, kind, text)
        return {"success": True}

    @mcp.tool()
    def history_load(cwd: str, limit: int = 50) -> dict[str, Any]:
        """Load recent history for directory."""
        items = registry.history.load(cwd, limit=limit)
        shaped = []
        for h in items:
            shaped.append({
                "ts": getattr(h, "ts", None),
                "cwd": getattr(h, "cwd", cwd),
                "kind": getattr(h, "kind", None),
                "text": getattr(h, "text", ""),
            })
        return {"items": shaped, "total_count": len(shaped)}

    # ----------------------------
    # Config tools
    # ----------------------------
    @mcp.tool()
    def config_get() -> dict[str, Any]:
        """Get current configuration (sanitized)."""
        return registry.config.get()

    @mcp.tool()
    def config_set(
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        timeout_s: Optional[int] = None,
    ) -> dict[str, Any]:
        """Update configuration."""
        return registry.config.set(
            base_url=base_url,
            model=model,
            api_key=api_key,
            token=token,
            timeout_s=timeout_s,
        )

    # ----------------------------
    # Read-only resources
    # ----------------------------
    @mcp.resource("matrixsh://system/info")
    def resource_system_info() -> dict[str, Any]:
        """Current system information."""
        return {
            "os": registry.shell.os_name(),
            "cwd": os.getcwd(),
            "default_shell": registry.shell.default_mode(),
        }

    @mcp.resource("matrixsh://config")
    def resource_config() -> dict[str, Any]:
        """Current configuration (sanitized)."""
        return registry.config.get()

    # Run the server
    mcp.run(transport=transport)


def main() -> None:
    """Entry point for `matrixsh-mcp` command (power users)."""
    registry = ToolRegistry()
    serve_from_registry(registry, transport="stdio")


if __name__ == "__main__":
    main()
