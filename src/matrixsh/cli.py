from **future** import annotations

import argparse
import os

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config import Settings
from .history import append_history, load_recent
from .install import run_install
from .llm import MatrixLLM
from .safety import denylist_match, is_command_not_found, is_no, is_yes, looks_like_natural_language
from .shell import detect_default_mode, execute, handle_cd, list_files, os_name, prompt_string

console = Console()

def main() -> None:
parser = argparse.ArgumentParser(prog="matrixsh", description="MatrixShell: AI-augmented shell wrapper powered by MatrixLLM")

```
sub = parser.add_subparsers(dest="subcmd")

p_install = sub.add_parser("install", help="Write config file and test gateway connection")
p_install.add_argument("--url", help="MatrixLLM base URL (e.g. http://localhost:11435/v1)")
p_install.add_argument("--model", help="Default model name")
p_install.add_argument("--key", help="API key (optional)")

parser.add_argument("--mode", choices=["auto", "cmd", "powershell", "bash"], default="auto", help="Shell mode")
parser.add_argument("--url", help="MatrixLLM base URL override")
parser.add_argument("--model", help="Model override")
parser.add_argument("--key", help="API key override")
parser.add_argument("--no-healthcheck", action="store_true", help="Skip health check")
parser.add_argument("--stream", action="store_true", help="Stream assistant output (OpenAI-compatible SSE)")
args = parser.parse_args()

if args.subcmd == "install":
    raise SystemExit(run_install(args.url, args.model, args.key))

settings = Settings.load()
if args.url:
    settings.base_url = args.url
if args.model:
    settings.model = args.model
if args.key:
    settings.api_key = args.key

mode = detect_default_mode() if args.mode == "auto" else args.mode
llm = MatrixLLM(settings.base_url, settings.api_key, timeout_s=settings.timeout_s)

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

    # cd persists
    handled, new_cwd, cd_msg = handle_cd(user_input, cwd, mode)
    if handled:
        if cd_msg:
            console.print(f"[red]{cd_msg}[/red]")
        cwd = new_cwd
        continue

    # Heuristic: NL -> AI
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

    # AI fallback
    files = list_files(cwd)
    append_history(cwd, "user", user_input)

    # Include some recent context from history
    recent = load_recent(cwd, limit=12)
    history_context = "\n".join([f"{h.kind}: {h.text}" for h in recent if h.kind in ("user", "assistant")])

    try:
        # We use the structured "suggest" API (JSON response)
        suggestion = llm.suggest(
            model=settings.model,
            os_name=os_name(),
            shell_mode=mode,
            cwd=cwd,
            files=files,
            user_input=user_input + ("\n\nRecent history:\n" + history_context if history_context else ""),
        )
    except Exception as e:
        console.print(f"[red]MatrixLLM error:[/red] {e}")
        continue

    append_history(cwd, "assistant", suggestion.explanation)
    console.print(Panel(suggestion.explanation, title="🤖 MatrixLLM", border_style="cyan"))
    console.print("[bold]Suggested command:[/bold]")
    console.print(suggestion.command)
    console.print(f"Risk: [bold]{suggestion.risk}[/bold]\n")

    # HARD safety denylist: refuse execution no matter what
    reason = denylist_match(suggestion.command)
    if reason:
        console.print(f"[red]⛔ Refusing to execute:[/red] {reason}")
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
        console.print("[green]✔ Done.[/green]")
    else:
        console.print(f"[red]Command failed (exit code {res2.code}).[/red]")
```

