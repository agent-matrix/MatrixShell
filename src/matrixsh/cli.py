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
from .history import append_history, load_recent
from .install import run_install
from .llm import MatrixLLM, UnauthorizedError
from .pair import get_pair_info, submit_pair_code
from .safety import denylist_match, is_command_not_found, is_no, is_yes, looks_like_natural_language
from .shell import detect_default_mode, execute, handle_cd, list_files, os_name, prompt_string

console = Console()


def _prompt_yes_no(msg: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    ans = console.input(f"{msg} {suffix} ").strip().lower()
    if not ans:
        return default_yes
    return ans in ("y", "yes", "s", "si", "si", "oui", "ja")


def _pair_flow(settings: Settings, pairing_code_hint: str | None = None) -> bool:
    """
    Pair with local MatrixLLM pairing mode:
      - GET /pair/info must indicate pairing enabled
      - user enters pairing code
      - POST /pair -> token
    """
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
    """
    Consumer-friendly setup:
      - ensure matrixllm installed
      - start local gateway in pairing mode
      - pair and save token
    """
    s = Settings.load()

    if url:
        s.base_url = url
    if model:
        s.model = model

    # Safety: setup is intended for local
    if not is_local_base_url(s.base_url):
        console.print("[red]Setup only supports local base_url (localhost/127.0.0.1).[/red]")
        console.print("Use `matrixsh install --key ... --url ...` for remote gateways.")
        return 2

    # Install matrixllm if missing
    if not ensure_matrixllm_installed(prefer_uv=True):
        return 2

    # If already running, attempt pairing directly
    if probe_health(s.base_url):
        console.print("[green]MatrixLLM is already running.[/green]")
        # If pairing enabled, pair now
        info = get_pair_info(s.base_url)
        if info and info.pairing:
            ok = _pair_flow(s)
            return 0 if ok else 2
        console.print("[yellow]MatrixLLM is running but not in pairing mode.[/yellow]")
        console.print("Restart it with: matrixllm start --auth pairing --host 127.0.0.1 --port 11435")
        return 2

    # Start gateway
    parsed_port = port or 11435
    gw = start_matrixllm_pairing(base_url=s.base_url, model=s.model, host="127.0.0.1", port=parsed_port)

    if not wait_for_health(s.base_url, total_timeout_s=25.0):
        console.print("[red]MatrixLLM did not become healthy in time.[/red]")
        console.print("Check MatrixLLM output above for errors.")
        return 2

    console.print("[green]MatrixLLM is running (pairing mode).[/green]")

    # Pair using the parsed code (if we captured it)
    ok = _pair_flow(s, pairing_code_hint=gw.pairing_code)
    return 0 if ok else 2


def main() -> None:
    parser = argparse.ArgumentParser(prog="matrixsh", description="MatrixShell: AI-augmented shell wrapper powered by MatrixLLM")

    sub = parser.add_subparsers(dest="subcmd")

    p_install = sub.add_parser("install", help="Write config file and test gateway connection")
    p_install.add_argument("--url", help="MatrixLLM base URL (e.g. http://localhost:11435/v1)")
    p_install.add_argument("--model", help="Default model name")
    p_install.add_argument("--key", help="API key (sk-...)")
    p_install.add_argument("--token", help="Pairing token (mtx_...)")

    p_setup = sub.add_parser("setup", help="Install/start MatrixLLM locally and pair automatically")
    p_setup.add_argument("--url", help="Local MatrixLLM base URL (default http://localhost:11435/v1)")
    p_setup.add_argument("--model", help="Default model name")
    p_setup.add_argument("--port", type=int, help="Port to run MatrixLLM on (default 11435)")

    parser.add_argument("--mode", choices=["auto", "cmd", "powershell", "bash"], default="auto", help="Shell mode")
    parser.add_argument("--url", help="MatrixLLM base URL override")
    parser.add_argument("--model", help="Model override")
    parser.add_argument("--key", help="API key override")
    parser.add_argument("--no-healthcheck", action="store_true", help="Skip health check")
    parser.add_argument("--stream", action="store_true", help="Stream assistant output (if supported)")

    args = parser.parse_args()

    if args.subcmd == "install":
        raise SystemExit(run_install(args.url, args.model, args.key, args.token))

    if args.subcmd == "setup":
        raise SystemExit(run_setup(args.url, args.model, args.port))

    settings = Settings.load()
    if args.url:
        settings.base_url = args.url
    if args.model:
        settings.model = args.model
    if args.key:
        settings.api_key = args.key

    mode = detect_default_mode() if args.mode == "auto" else args.mode

    # If local and gateway not running, offer to start + pair
    if is_local_base_url(settings.base_url) and not probe_health(settings.base_url):
        if _prompt_yes_no("MatrixLLM not running. Start it now?", default_yes=True):
            rc = run_setup(settings.base_url, settings.model, None)
            if rc != 0:
                console.print("[red]Setup failed.[/red]")
        else:
            console.print("[yellow]MatrixLLM not started. You can still run normal commands.[/yellow]")

    llm = MatrixLLM(settings.base_url, settings.api_key, token=settings.token, timeout_s=settings.timeout_s)

    if not args.no_healthcheck and not llm.health():
        console.print("[yellow]Warning:[/yellow] MatrixLLM gateway health check failed.")
        console.print(f"Expected gateway at: {settings.base_url}")
        console.print("You can still use MatrixShell for normal commands.\n")

    cwd = os.getcwd()

    console.print(
        Panel.fit(
            f"[bold cyan]MatrixShell[/bold cyan] (powered by MatrixLLM)\n"
            f"OS: {os_name()}  |  Mode: {mode}\n"
            f"Gateway: {settings.base_url}\n"
            f"Model: {settings.model}\n\n"
            "[bold]Tips[/bold]\n"
            " - Type normal commands as usual.\n"
            " - If you type natural language OR an unknown command, MatrixShell will ask MatrixLLM.\n"
            " - Use /exit to quit.\n",
            title="matrixsh",
        )
    )

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

        handled, new_cwd, cd_msg = handle_cd(user_input, cwd, mode)
        if handled:
            if cd_msg:
                console.print(f"[red]{cd_msg}[/red]")
            cwd = new_cwd
            continue

        nl = looks_like_natural_language(user_input)

        if not nl:
            res = execute(user_input, mode, cwd)
            if res.stdout:
                console.print(res.stdout, end="")
            if res.stderr:
                console.print(res.stderr, end="", style="red")

            if res.code == 0:
                continue

            if not is_command_not_found(res.stderr, mode):
                continue

        files = list_files(cwd)
        append_history(cwd, "user", user_input)

        recent = load_recent(cwd, limit=12)
        history_context = "\n".join([f"{h.kind}: {h.text}" for h in recent if h.kind in ("user", "assistant")])

        try:
            suggestion = llm.suggest(
                model=settings.model,
                os_name=os_name(),
                shell_mode=mode,
                cwd=cwd,
                files=files,
                user_input=user_input + ("\n\nRecent history:\n" + history_context if history_context else ""),
            )
        except UnauthorizedError as e:
            console.print(f"[yellow]{e}[/yellow]")
            # If local and pairing enabled, offer re-pair
            if is_local_base_url(settings.base_url):
                info = get_pair_info(settings.base_url)
                if info and info.pairing:
                    if _prompt_yes_no("Your pairing token may be invalid/expired. Re-pair now?", default_yes=True):
                        if _pair_flow(settings):
                            llm.token = settings.token
                            continue
            continue
        except Exception as e:
            console.print(f"[red]MatrixLLM error:[/red] {e}")
            continue

        append_history(cwd, "assistant", suggestion.explanation)
        console.print(Panel(suggestion.explanation, title="MatrixLLM", border_style="cyan"))
        console.print("[bold]Suggested command:[/bold]")
        console.print(suggestion.command)
        console.print(f"Risk: [bold]{suggestion.risk}[/bold]\n")

        reason = denylist_match(suggestion.command)
        if reason:
            console.print(f"[red]Refusing to execute:[/red] {reason}")
            console.print("[yellow]You can still copy the command manually if you really intend it.[/yellow]")
            continue

        answer = console.input("Execute it? (yes/no) ").strip()
        if is_no(answer) or not is_yes(answer):
            console.print("[cyan]Cancelled.[/cyan]")
            continue

        append_history(cwd, "exec", suggestion.command)

        res2 = execute(suggestion.command, mode, cwd)
        if res2.stdout:
            console.print(res2.stdout, end="")
        if res2.stderr:
            console.print(res2.stderr, end="", style="red")
        if res2.code == 0:
            console.print("[green]Done.[/green]")
        else:
            console.print(f"[red]Command failed (exit code {res2.code}).[/red]")


if __name__ == "__main__":
    main()
