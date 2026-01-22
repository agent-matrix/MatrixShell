from **future** import annotations

from dataclasses import asdict
from typing import Optional

from rich.console import Console

from .config import Settings

console = Console()

def run_install(url: Optional[str], model: Optional[str], key: Optional[str]) -> int:
s = Settings.load()

```
if url:
    s.base_url = url
if model:
    s.model = model
if key is not None:
    s.api_key = key

path = s.save()
console.print(f"[green]✓ Wrote config:[/green] {path}")

# Test gateway connection
from .llm import MatrixLLM
llm = MatrixLLM(s.base_url, s.api_key, timeout_s=s.timeout_s)

ok = llm.health()
if ok:
    console.print("[green]✓ Gateway health check OK[/green]")
    console.print(f"Base URL: {s.base_url}")
    console.print(f"Model: {s.model}")
    return 0

console.print("[yellow]⚠ Gateway health check FAILED[/yellow]")
console.print("Make sure MatrixLLM is running and reachable.")
console.print(f"Tried: {s.base_url.replace('/v1','')}/health")
return 2
```

