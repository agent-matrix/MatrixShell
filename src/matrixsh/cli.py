"""MatrixShell CLI - AI-augmented shell wrapper.

Usage:
    matrixsh              # Start interactive shell (default, embedded tools)
    matrixsh setup        # Configure local MatrixLLM
    matrixsh install ...  # Configure remote MatrixLLM
    matrixsh plugin ...   # Manage MCP server plugins
    matrixsh --serve      # Expose tools via MCP (power users)

Catalog commands (flat top-level):
    matrixsh login        # Login to MCP server catalog
    matrixsh logout       # Logout from catalog
    matrixsh status       # Show comprehensive status
    matrixsh servers      # List catalog servers
    matrixsh enable <id>  # Enable a server
    matrixsh disable <id> # Disable a server
    matrixsh tools        # List catalog tools
    matrixsh sync         # Sync servers to plugins.json
    matrixsh unsync       # Remove catalog-synced plugins
    matrixsh plugins      # List all plugins
"""

from __future__ import annotations

import argparse
import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config import Settings
from .gateway import (
    ensure_matrixllm_installed,
    is_local_base_url,
    probe_health,
    start_matrixllm_pairing,
    wait_for_health,
)
from .install import run_install
from .llm import UnauthorizedError
from .pair import get_pair_info, submit_pair_code
from .safety import is_no, is_yes
from .shell import detect_default_mode, os_name, prompt_string

console = Console()


def _prompt_yes_no(msg: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    ans = console.input(f"{msg} {suffix} ").strip().lower()
    if not ans:
        return default_yes
    return ans in ("y", "yes", "s", "si", "sì", "oui", "ja")


def _pair_flow(settings: Settings, pairing_code_hint: str | None = None) -> bool:
    """Pair with local MatrixLLM pairing mode."""
    info = get_pair_info(settings.base_url)
    if not info or not info.pairing:
        console.print("[yellow]Pairing is not enabled on this MatrixLLM instance.[/yellow]")
        return False

    if not is_local_base_url(settings.base_url):
        console.print("[yellow]Remote gateway detected. Pairing disabled for security.[/yellow]")
        return False

    if pairing_code_hint:
        console.print(f"[cyan]Pairing code shown by MatrixLLM:[/cyan] {pairing_code_hint}")

    code = console.input("Enter pairing code (e.g. 483-921): ").strip()
    if not code:
        console.print("[yellow]No code entered.[/yellow]")
        return False

    try:
        token = submit_pair_code(settings.base_url, code=code, client_name="matrixsh")
    except Exception as e:
        console.print(f"[red]Pairing failed:[/red] {e}")
        return False

    settings.token = token
    settings.save()
    console.print("[green]Paired. Token saved.[/green]")
    return True


def run_setup(url: str | None, model: str | None, port: int | None) -> int:
    """Consumer-friendly setup: install, start, and pair with MatrixLLM."""
    s = Settings.load()

    if url:
        s.base_url = url
    if model:
        s.model = model

    if not is_local_base_url(s.base_url):
        console.print("[red]Setup only supports local base_url (localhost/127.0.0.1).[/red]")
        console.print("Use `matrixsh install --key ... --url ...` for remote gateways.")
        return 2

    if not ensure_matrixllm_installed(prefer_uv=True):
        return 2

    if probe_health(s.base_url):
        console.print("[green]MatrixLLM is already running.[/green]")
        info = get_pair_info(s.base_url)
        if info and info.pairing:
            ok = _pair_flow(s)
            return 0 if ok else 2
        console.print("[yellow]MatrixLLM is running but not in pairing mode.[/yellow]")
        console.print("Restart it with: matrixllm start --auth pairing --host 127.0.0.1 --port 11435")
        return 2

    parsed_port = port or 11435
    gw = start_matrixllm_pairing(base_url=s.base_url, model=s.model, host="127.0.0.1", port=parsed_port)

    if not wait_for_health(s.base_url, total_timeout_s=25.0):
        console.print("[red]MatrixLLM did not become healthy in time.[/red]")
        console.print("Check MatrixLLM output above for errors.")
        return 2

    console.print("[green]MatrixLLM is running (pairing mode).[/green]")
    ok = _pair_flow(s, pairing_code_hint=gw.pairing_code)
    return 0 if ok else 2


def _show_setup_hint() -> None:
    """Show a friendly hint when LLM isn't configured."""
    console.print(
        Panel(
            "[yellow]AI features are not configured.[/yellow]\n\n"
            "To enable AI suggestions, run:\n"
            "  [bold cyan]matrixsh setup[/bold cyan]\n\n"
            "You can still use MatrixShell for normal commands.",
            title="Setup Required",
            border_style="yellow",
        )
    )


def _run_serve_mode(transport: str) -> None:
    """Start MCP server mode (power users)."""
    # Check if MCP is available first
    try:
        import mcp  # noqa: F401
    except ImportError:
        console.print(
            Panel(
                "[red]MCP server dependencies are not installed.[/red]\n\n"
                "Install with:\n"
                "  [bold]pip install \"matrixsh\\[mcp]\"[/bold]",
                title="MCP not available",
                border_style="red",
            )
        )
        raise SystemExit(2)

    from .mcp.server import serve_from_registry
    from .mcp.registry import ToolRegistry

    registry = ToolRegistry()
    serve_from_registry(registry, transport=transport)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="matrixsh",
        description="MatrixShell: AI-augmented shell wrapper powered by MatrixLLM",
    )

    sub = parser.add_subparsers(dest="subcmd")

    # install subcommand
    p_install = sub.add_parser("install", help="Configure MatrixLLM gateway URL + auth")
    p_install.add_argument("--url", help="MatrixLLM base URL (e.g. http://localhost:11435/v1)")
    p_install.add_argument("--model", help="Default model name")
    p_install.add_argument("--key", help="API key (sk-...)")
    p_install.add_argument("--token", help="Pairing token (mtx_...)")

    # setup subcommand
    p_setup = sub.add_parser("setup", help="Install/start MatrixLLM locally and pair automatically")
    p_setup.add_argument("--url", help="Local MatrixLLM base URL (default http://localhost:11435/v1)")
    p_setup.add_argument("--model", help="Default model name")
    p_setup.add_argument("--port", type=int, help="Port to run MatrixLLM on (default 11435)")

    # plugin subcommand (admin)
    from .plugins.admin import create_plugin_parser
    create_plugin_parser(sub)

    # Catalog commands (flat top-level: login, logout, status, servers, etc.)
    from .catalog.commands import add_catalog_commands
    add_catalog_commands(parser, sub)

    # Main CLI arguments
    parser.add_argument(
        "--mode",
        choices=["auto", "cmd", "powershell", "bash"],
        default="auto",
        help="Shell mode",
    )
    parser.add_argument("--url", help="MatrixLLM base URL override")
    parser.add_argument("--model", help="Model override")
    parser.add_argument("--key", help="API key override")

    # Power user: MCP server mode
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Expose MatrixShell tools via MCP (for IDE/agents). Normal use does not require this.",
    )
    parser.add_argument(
        "--serve-transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport when using --serve (default: stdio).",
    )

    args = parser.parse_args()

    # Handle MCP server mode (power users)
    if args.serve:
        _run_serve_mode(args.serve_transport)
        return

    # Handle subcommands
    if args.subcmd == "install":
        raise SystemExit(run_install(args.url, args.model, args.key, args.token))

    if args.subcmd == "setup":
        raise SystemExit(run_setup(args.url, args.model, args.port))

    if args.subcmd == "plugin":
        from .plugins.admin import run_plugin_command
        raise SystemExit(run_plugin_command(args))

    # Handle catalog commands (login, logout, status, servers, enable, disable, tools, sync, unsync, plugins)
    from .catalog.commands import run_catalog_command
    catalog_result = run_catalog_command(args)
    if catalog_result != -1:
        raise SystemExit(catalog_result)

    # Load settings and apply overrides
    settings = Settings.load()
    if args.url:
        settings.base_url = args.url
    if args.model:
        settings.model = args.model
    if args.key:
        settings.api_key = args.key

    # Initialize embedded tool registry
    from .mcp.registry import ToolRegistry
    tools = ToolRegistry(settings=settings, shell_mode=args.mode)

    mode = tools.shell.get_mode()

    # Check AI availability and show appropriate message
    ai_available = False
    setup_shown = False

    if not tools.llm.is_configured():
        # No credentials configured
        _show_setup_hint()
        setup_shown = True
    elif is_local_base_url(settings.base_url) and not probe_health(settings.base_url):
        # Local gateway not running - offer to start
        if _prompt_yes_no("MatrixLLM not running. Start it now?", default_yes=True):
            rc = run_setup(settings.base_url, settings.model, None)
            if rc == 0:
                # Reload settings after setup
                settings = Settings.load()
                tools = ToolRegistry(settings=settings, shell_mode=args.mode)
                ai_available = True
        else:
            console.print("[yellow]MatrixLLM not started. AI features disabled.[/yellow]")
    else:
        # Check health
        health = tools.llm.health()
        if health["healthy"]:
            ai_available = True
        else:
            console.print(
                f"[yellow]Warning:[/yellow] MatrixLLM gateway not reachable at {settings.base_url}\n"
                "AI features disabled. You can still use normal commands.\n"
            )

    # Show welcome banner
    ai_status = "[green]Ready[/green]" if ai_available else "[yellow]Disabled[/yellow]"
    if not setup_shown:
        console.print(
            Panel.fit(
                f"[bold cyan]MatrixShell[/bold cyan]\n"
                f"OS: {os_name()}  |  Mode: {mode}\n"
                f"AI: {ai_status}\n\n"
                "[bold]Tips[/bold]\n"
                " - Type normal commands as usual.\n"
                " - Natural language queries trigger AI suggestions.\n"
                " - Use /exit to quit.",
                title="matrixsh",
            )
        )

    cwd = os.getcwd()

    while True:
        try:
            user_input = console.input(Text(prompt_string(mode, cwd), style="bold green")).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]Bye.[/cyan]")
            return

        if not user_input:
            continue

        if user_input.lower() in ("/exit", "/quit"):
            console.print("[cyan]Bye.[/cyan]")
            return

        # Handle cd command (persists cwd)
        handled, new_cwd, cd_msg = tools.shell.handle_cd(user_input, cwd)
        if handled:
            if cd_msg:
                console.print(f"[red]{cd_msg}[/red]")
            else:
                cwd = new_cwd
            continue

        # Check if input is natural language
        is_nl = tools.safety.looks_like_natural_language(user_input)

        if not is_nl:
            # Direct command execution
            res = tools.shell.execute_direct(user_input, cwd)
            if res.stdout:
                console.print(res.stdout, end="")
            if res.stderr:
                console.print(res.stderr, end="", style="red")

            if res.code == 0:
                continue

            # Check for command-not-found (fall through to AI if available)
            if not tools.safety.is_command_not_found(res.stderr, mode):
                continue

            # If AI not available, just continue
            if not ai_available:
                continue

        # AI suggestion flow
        if not ai_available:
            # Graceful fallback: hint user to run setup
            if is_nl:
                console.print(
                    "[yellow]AI features not available.[/yellow] "
                    "Run [bold]matrixsh setup[/bold] to enable."
                )
            continue

        # Record user input in history
        tools.history.append(cwd, "user", user_input)

        # Gather context
        files = tools.shell.list_files(cwd)
        recent = tools.history.load(cwd, limit=12)
        history_context = "\n".join(
            [f"{h.kind}: {h.text}" for h in recent if h.kind in ("user", "assistant")]
        )

        try:
            suggestion = tools.llm.suggest_raw(user_input, cwd, files, history_context)
        except UnauthorizedError as e:
            console.print(f"[yellow]{e}[/yellow]")
            # Offer to re-pair if local
            if is_local_base_url(settings.base_url):
                info = get_pair_info(settings.base_url)
                if info and info.pairing:
                    if _prompt_yes_no("Re-pair now?", default_yes=True):
                        if _pair_flow(settings):
                            tools.llm.update_token(settings.token)
                            continue
            continue
        except Exception as e:
            console.print(f"[red]MatrixLLM error:[/red] {e}")
            continue

        # Show suggestion
        tools.history.append(cwd, "assistant", suggestion.explanation)
        console.print(Panel(suggestion.explanation, title="MatrixLLM", border_style="cyan"))
        console.print("[bold]Suggested command:[/bold]")
        console.print(suggestion.command)
        console.print(f"Risk: [bold]{suggestion.risk}[/bold]\n")

        # Safety check (denylist)
        reason = tools.safety.denylist_match(suggestion.command)
        if reason:
            console.print(f"[red]Refusing to execute:[/red] {reason}")
            console.print("[yellow]You can copy the command manually if you really intend it.[/yellow]")
            continue

        # Confirmation
        answer = console.input("Execute it? (yes/no) ").strip()
        if is_no(answer) or not is_yes(answer):
            console.print("[cyan]Cancelled.[/cyan]")
            continue

        # Execute
        tools.history.append(cwd, "exec", suggestion.command)
        res = tools.shell.execute_direct(suggestion.command, cwd)

        if res.stdout:
            console.print(res.stdout, end="")
        if res.stderr:
            console.print(res.stderr, end="", style="red")

        if res.code == 0:
            console.print("[green]Done.[/green]")
        else:
            console.print(f"[red]Command failed (exit code {res.code}).[/red]")


if __name__ == "__main__":
    main()
