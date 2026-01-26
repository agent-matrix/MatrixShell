"""Catalog CLI Commands for MatrixShell.

Top-level commands for catalog management:
- login/logout/status
- servers/enable/disable
- tools
- sync/unsync
- plugins
"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .client import CatalogClient, CatalogConfig, CatalogError
from .sync import (
    get_all_plugins,
    get_sync_status,
    get_synced_plugins,
    sync_catalog,
    unsync_catalog,
)

console = Console()


# --- Authentication Commands ---

def cmd_login(args: argparse.Namespace) -> int:
    """Login to catalog."""
    config = CatalogConfig.load()

    # Get URL
    url = args.url or config.url
    if not url:
        url = console.input("Catalog URL (e.g., http://localhost:4444): ").strip()

    if not url:
        console.print("[red]URL is required.[/red]")
        return 1

    # Get token
    token = args.token
    if not token:
        token = console.input("JWT Token: ").strip()

    if not token:
        console.print("[red]Token is required.[/red]")
        return 1

    # Try to login
    client = CatalogClient(config)
    console.print(f"Connecting to {url}...")

    if client.login(url, token):
        console.print("[green]Login successful![/green]")

        # Show stats
        try:
            stats = client.get_stats()
            console.print(f"Servers: {stats['active_servers']}/{stats['total_servers']} active")
            console.print(f"Tools: {stats['total_tools']} available")
        except CatalogError:
            pass

        console.print("\nRun [bold]matrixsh sync[/bold] to populate plugins.")
        return 0
    else:
        console.print("[red]Login failed. Check URL and token.[/red]")
        return 1


def cmd_logout(args: argparse.Namespace) -> int:
    """Logout from catalog."""
    client = CatalogClient()
    client.logout()
    console.print("[green]Logged out from catalog.[/green]")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show comprehensive status."""
    from ..config import Settings
    from ..gateway import probe_health

    config = CatalogConfig.load()
    settings = Settings.load()
    sync_status = get_sync_status()
    plugins = get_all_plugins()

    # Build status display
    lines = []

    # Catalog status
    if config.is_configured():
        lines.append(f"[bold]Catalog:[/bold] [green]Configured[/green] ({config.url})")

        client = CatalogClient(config)
        if client.is_reachable():
            try:
                stats = client.get_stats()
                lines.append(f"  Servers: {stats['active_servers']}/{stats['total_servers']} active")
                lines.append("  Status: [green]Reachable[/green]")
            except CatalogError:
                lines.append("  Status: [yellow]Reachable (limited)[/yellow]")
        else:
            lines.append("  Status: [red]Unreachable[/red]")
    else:
        lines.append("[bold]Catalog:[/bold] [yellow]Not configured[/yellow]")
        lines.append("  Run [bold]matrixsh login[/bold] to connect")

    lines.append("")

    # Sync status
    synced_plugins = [p for p in plugins if p.get("source") == "catalog"]
    manual_plugins = [p for p in plugins if p.get("source") != "catalog"]

    lines.append(f"[bold]Synced Plugins:[/bold] {len(synced_plugins)}")
    if sync_status.last_sync_ts:
        try:
            ts = datetime.fromisoformat(sync_status.last_sync_ts.replace("Z", "+00:00"))
            lines.append(f"  Last sync: {ts.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            lines.append(f"  Last sync: {sync_status.last_sync_ts}")
    else:
        lines.append("  Last sync: [dim]Never[/dim]")

    lines.append(f"[bold]Manual Plugins:[/bold] {len(manual_plugins)}")

    lines.append("")

    # MatrixLLM status
    lines.append(f"[bold]MatrixLLM:[/bold] {settings.base_url}")
    if probe_health(settings.base_url):
        lines.append("  Status: [green]Healthy[/green]")
    else:
        lines.append("  Status: [yellow]Not running[/yellow]")

    # Plugin health summary
    enabled_plugins = [p for p in plugins if p.get("enabled", True)]
    lines.append("")
    lines.append(f"[bold]Plugins:[/bold] {len(enabled_plugins)} enabled, {len(plugins)} total")

    console.print(Panel("\n".join(lines), title="MatrixShell Status", border_style="cyan"))
    return 0


# --- Server Commands ---

def cmd_servers(args: argparse.Namespace) -> int:
    """List servers in catalog."""
    client = CatalogClient()

    if not client.config.is_configured():
        console.print("[yellow]Catalog not configured.[/yellow]")
        console.print("Run [bold]matrixsh login[/bold] first.")
        return 1

    try:
        servers = client.list_servers(active_only=args.active)
    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    if not servers:
        msg = "No active servers found." if args.active else "No servers found."
        console.print(f"[yellow]{msg}[/yellow]")
        return 0

    table = Table(title="Catalog Servers")
    table.add_column("ID", style="cyan", max_width=20)
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Active", justify="center")

    for server in servers:
        active = "[green]Yes[/green]" if server.active else "[red]No[/red]"
        # Truncate long IDs
        server_id = server.id[:20] + "..." if len(server.id) > 20 else server.id
        table.add_row(server_id, server.name, server.server_type, active)

    console.print(table)
    console.print(f"\nTotal: {len(servers)} server(s)")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    """Enable a server."""
    client = CatalogClient()

    if not client.config.is_configured():
        console.print("[yellow]Catalog not configured.[/yellow]")
        return 1

    try:
        client.enable_server(args.id)
        console.print(f"[green]Server '{args.id}' enabled.[/green]")
        console.print("Run [bold]matrixsh sync[/bold] to update plugins.")
        return 0
    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


def cmd_disable(args: argparse.Namespace) -> int:
    """Disable a server."""
    client = CatalogClient()

    if not client.config.is_configured():
        console.print("[yellow]Catalog not configured.[/yellow]")
        return 1

    try:
        client.disable_server(args.id)
        console.print(f"[yellow]Server '{args.id}' disabled.[/yellow]")
        console.print("Run [bold]matrixsh sync[/bold] to update plugins.")
        return 0
    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


# --- Tool Commands ---

def cmd_tools(args: argparse.Namespace) -> int:
    """List tools from catalog."""
    client = CatalogClient()

    if not client.config.is_configured():
        console.print("[yellow]Catalog not configured.[/yellow]")
        return 1

    try:
        tools = client.list_tools(server_id=args.server)
    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    if not tools:
        console.print("[yellow]No tools found.[/yellow]")
        return 0

    # Group by server
    by_server = {}
    for tool in tools:
        key = tool.server_name or tool.server_id
        if key not in by_server:
            by_server[key] = []
        by_server[key].append(tool)

    for server_name, server_tools in sorted(by_server.items()):
        console.print(f"\n[bold cyan]{server_name}[/bold cyan]")
        for tool in server_tools:
            desc = f" - {tool.description}" if tool.description else ""
            console.print(f"  {tool.tool}{desc}")

    console.print(f"\n[bold]Total:[/bold] {len(tools)} tool(s) from {len(by_server)} server(s)")
    return 0


# --- Sync Commands ---

def cmd_sync(args: argparse.Namespace) -> int:
    """Sync catalog servers to plugins."""
    client = CatalogClient()

    if not client.config.is_configured():
        console.print("[yellow]Catalog not configured.[/yellow]")
        console.print("Run [bold]matrixsh login[/bold] first.")
        return 1

    console.print("Syncing catalog servers to plugins...")

    try:
        result = sync_catalog(client)
    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    console.print(f"[green]Sync complete![/green]")
    console.print(f"  Added: {result['added']}")
    console.print(f"  Updated: {result['updated']}")
    console.print(f"  Removed: {result['removed']}")
    console.print(f"  Total synced: {len(result['synced'])}")

    return 0


def cmd_unsync(args: argparse.Namespace) -> int:
    """Remove all catalog-synced plugins."""
    if not args.force:
        answer = console.input("Remove all catalog-synced plugins? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            console.print("[yellow]Cancelled.[/yellow]")
            return 0

    result = unsync_catalog()
    console.print(f"[green]Removed {result['removed']} plugin(s).[/green]")
    return 0


# --- Plugin Commands ---

def cmd_plugins(args: argparse.Namespace) -> int:
    """List all plugins with health status."""
    plugins = get_all_plugins()

    if not plugins:
        console.print("[yellow]No plugins configured.[/yellow]")
        console.print("Run [bold]matrixsh sync[/bold] to sync from catalog,")
        console.print("or [bold]matrixsh plugin add[/bold] to add manually.")
        return 0

    table = Table(title="Plugins")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Namespace", style="magenta")
    table.add_column("Enabled", justify="center")
    table.add_column("Source")
    table.add_column("Transport")

    for p in plugins:
        enabled = "[green]Yes[/green]" if p.get("enabled", True) else "[red]No[/red]"
        source = p.get("source", "manual")
        source_display = "[cyan]catalog[/cyan]" if source == "catalog" else "[dim]manual[/dim]"
        namespace = p.get("tool_namespace", p.get("namespace", ""))

        table.add_row(
            p.get("id", ""),
            p.get("name", ""),
            namespace,
            enabled,
            source_display,
            p.get("transport", ""),
        )

    console.print(table)

    # Summary
    synced = len([p for p in plugins if p.get("source") == "catalog"])
    manual = len(plugins) - synced
    console.print(f"\n[bold]Total:[/bold] {len(plugins)} ({synced} synced, {manual} manual)")
    return 0


# --- Parser Setup ---

def add_catalog_commands(parser: argparse.ArgumentParser, subparsers: argparse._SubParsersAction) -> None:
    """Add catalog-related commands to the main parser."""

    # login
    p_login = subparsers.add_parser("login", help="Login to MCP server catalog")
    p_login.add_argument("--url", help="Catalog URL (e.g., http://localhost:4444)")
    p_login.add_argument("--token", help="JWT authentication token")
    p_login.set_defaults(func=cmd_login)

    # logout
    p_logout = subparsers.add_parser("logout", help="Logout from catalog")
    p_logout.set_defaults(func=cmd_logout)

    # status
    p_status = subparsers.add_parser("status", help="Show MatrixShell status")
    p_status.set_defaults(func=cmd_status)

    # servers
    p_servers = subparsers.add_parser("servers", help="List catalog servers")
    p_servers.add_argument("--active", "-a", action="store_true", help="Show only active servers")
    p_servers.set_defaults(func=cmd_servers)

    # enable
    p_enable = subparsers.add_parser("enable", help="Enable a catalog server")
    p_enable.add_argument("id", help="Server ID")
    p_enable.set_defaults(func=cmd_enable)

    # disable
    p_disable = subparsers.add_parser("disable", help="Disable a catalog server")
    p_disable.add_argument("id", help="Server ID")
    p_disable.set_defaults(func=cmd_disable)

    # tools
    p_tools = subparsers.add_parser("tools", help="List catalog tools")
    p_tools.add_argument("--server", "-s", help="Filter by server ID")
    p_tools.set_defaults(func=cmd_tools)

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync catalog servers to plugins")
    p_sync.set_defaults(func=cmd_sync)

    # unsync
    p_unsync = subparsers.add_parser("unsync", help="Remove catalog-synced plugins")
    p_unsync.add_argument("--force", "-f", action="store_true", help="Skip confirmation")
    p_unsync.set_defaults(func=cmd_unsync)

    # plugins
    p_plugins = subparsers.add_parser("plugins", help="List all plugins")
    p_plugins.set_defaults(func=cmd_plugins)


def run_catalog_command(args: argparse.Namespace) -> int:
    """Run a catalog command if func is set."""
    if hasattr(args, "func") and args.func:
        return args.func(args)
    return -1  # Not a catalog command
