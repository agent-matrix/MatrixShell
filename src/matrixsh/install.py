from __future__ import annotations

from typing import Optional

from rich.console import Console

from .config import Settings
from .llm import MatrixLLM
from .urls import root_url

console = Console()


def run_install(url: Optional[str], model: Optional[str], key: Optional[str], token: Optional[str] = None) -> int:
    """
    Writes config file and tests MatrixLLM gateway connectivity.
    Returns:
      0 = success
      2 = gateway health check failed
    """
    s = Settings.load()

    if url:
        s.base_url = url
    if model:
        s.model = model
    if key is not None:
        s.api_key = key
    if token is not None:
        s.token = token

    path = s.save()
    console.print(f"[green]✓ Wrote config:[/green] {path}")

    llm = MatrixLLM(s.base_url, s.api_key, token=s.token, timeout_s=s.timeout_s)

    ok = llm.health()
    if ok:
        console.print("[green]✓ Gateway health check OK[/green]")
        console.print(f"Base URL: {s.base_url}")
        console.print(f"Model: {s.model}")
        return 0

    console.print("[yellow]⚠ Gateway health check FAILED[/yellow]")
    console.print("Make sure MatrixLLM is running and reachable.")
    console.print(f"Tried: {root_url(s.base_url)}/health")
    return 2
