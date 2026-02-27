"""ContextForge Admin CLI.

Provides commands for managing ContextForge integration:
- matrixsh cforge login      - Authenticate with ContextForge
- matrixsh cforge status     - Show connection status
- matrixsh cforge servers    - List/manage servers
- matrixsh cforge tools      - List tools
- matrixsh cforge sync       - Sync servers to MatrixShell plugins
- matrixsh cforge agents     - List A2A agents
"""

from __future__ import annotations

import argparse
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .contextforge import (
    ContextForgeConfig,
    ContextForgeError,
    ContextForgeProvider,
)

console = Console()


def cmd_login(args: argparse.Namespace) -> int:
    """Login to ContextForge."""
    config = ContextForgeConfig.load()

    # Update URL if provided
    if args.url:
        config.base_url = args.url

    # Get token
    if args.token:
        token = args.token
    else:
        token = console.input("Enter JWT token (or user:password for basic auth): ").strip()

    if not token:
        console.print("[red]No token provided.[/red]")
        return 1

    # Determine auth type
    auth_type = "basic" if ":" in token and not token.startswith("ey") else "bearer"
    if args.basic:
        auth_type = "basic"

    provider = ContextForgeProvider(config)

    console.print(f"Connecting to {config.base_url}...")
    if provider.login(token, auth_type):
        console.print("[green]Login successful![/green]")
        console.print(f"Configuration saved to: {config.save()}")
        return 0
    else:
        console.print("[red]Login failed. Check your token and URL.[/red]")
        return 1


def cmd_logout(args: argparse.Namespace) -> int:
    """Logout from ContextForge."""
    provider = ContextForgeProvider()
    provider.logout()
    console.print("[green]Logged out from ContextForge.[/green]")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show ContextForge connection status."""
    config = ContextForgeConfig.load()
    provider = ContextForgeProvider(config)

    table = Table(title="ContextForge Status", show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("URL", config.base_url)
    table.add_row("Auth Type", config.auth_type)
    table.add_row("Has Token", "[green]Yes[/green]" if config.token else "[red]No[/red]")
    table.add_row("Namespace Prefix", config.namespace_prefix)
    table.add_row("Sync Mode", config.sync_mode)
    table.add_row("Auto Sync", "[green]Yes[/green]" if config.auto_sync else "[red]No[/red]")

    console.print(table)

    # Check connection
    console.print("\nTesting connection...", end=" ")
    if provider.is_connected():
        console.print("[green]Connected![/green]")
        try:
            health = provider.health()
            console.print(f"Health: {health.get('status', 'ok')}")
        except Exception:
            pass
        return 0
    else:
        console.print("[red]Not connected[/red]")
        console.print("\nRun [bold]matrixsh cforge login[/bold] to authenticate.")
        return 1


def cmd_servers_list(args: argparse.Namespace) -> int:
    """List servers in ContextForge."""
    provider = ContextForgeProvider()

    if not provider.is_connected():
        console.print("[red]Not connected to ContextForge.[/red]")
        console.print("Run [bold]matrixsh cforge login[/bold] first.")
        return 1

    try:
        servers = provider.list_servers(active_only=args.active)
    except ContextForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    if not servers:
        console.print("[yellow]No servers found.[/yellow]")
        return 0

    table = Table(title="ContextForge Servers")
    table.add_column("ID", style="cyan", max_width=36)
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Active", justify="center")
    table.add_column("Description", max_width=40)

    for server in servers:
        active = "[green]Yes[/green]" if server.active else "[red]No[/red]"
        table.add_row(
            server.id[:36] if len(server.id) > 36 else server.id,
            server.name,
            server.server_type,
            active,
            (server.description[:40] + "...") if len(server.description) > 40 else server.description,
        )

    console.print(table)
    console.print(f"\nTotal: {len(servers)} server(s)")
    return 0


def cmd_servers_enable(args: argparse.Namespace) -> int:
    """Enable a server in ContextForge."""
    provider = ContextForgeProvider()

    try:
        provider.activate_server(args.id)
        console.print(f"[green]Server '{args.id}' enabled.[/green]")
        return 0
    except ContextForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


def cmd_servers_disable(args: argparse.Namespace) -> int:
    """Disable a server in ContextForge."""
    provider = ContextForgeProvider()

    try:
        provider.deactivate_server(args.id)
        console.print(f"[yellow]Server '{args.id}' disabled.[/yellow]")
        return 0
    except ContextForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


def cmd_tools(args: argparse.Namespace) -> int:
    """List tools from ContextForge."""
    provider = ContextForgeProvider()

    if not provider.is_connected():
        console.print("[red]Not connected to ContextForge.[/red]")
        return 1

    try:
        if args.server:
            tools = provider.list_tools(args.server)
            title = f"Tools from server: {args.server}"
        else:
            tools = provider.get_all_tools_flat()
            title = "All ContextForge Tools"
    except ContextForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    if not tools:
        console.print("[yellow]No tools found.[/yellow]")
        return 0

    table = Table(title=title)
    table.add_column("Tool", style="cyan")
    if not args.server:
        table.add_column("Server")
        table.add_column("Namespace", style="magenta")
    table.add_column("Description", max_width=50)

    for tool in tools:
        if isinstance(tool, dict):
            if args.server:
                table.add_row(tool["name"], tool.get("description", ""))
            else:
                table.add_row(
                    tool["name"],
                    tool.get("server_name", ""),
                    tool.get("namespace", ""),
                    tool.get("description", ""),
                )
        else:
            if args.server:
                table.add_row(tool.name, tool.description)
            else:
                table.add_row(tool.name, "", "", tool.description)

    console.print(table)
    console.print(f"\nTotal: {len(tools)} tool(s)")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync ContextForge servers to MatrixShell plugins."""
    provider = ContextForgeProvider()

    if not provider.is_connected():
        console.print("[red]Not connected to ContextForge.[/red]")
        return 1

    console.print("Syncing ContextForge servers to MatrixShell plugins...")

    try:
        plugins = provider.sync_to_plugins(active_only=not args.all)
    except ContextForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    if not plugins:
        console.print("[yellow]No servers to sync.[/yellow]")
        return 0

    table = Table(title="Synced Plugins")
    table.add_column("Plugin ID", style="cyan")
    table.add_column("Name")
    table.add_column("Namespace", style="magenta")
    table.add_column("Transport")

    for plugin in plugins:
        table.add_row(
            plugin.id,
            plugin.name,
            plugin.namespace,
            plugin.transport.value,
        )

    console.print(table)
    console.print(f"\n[green]Synced {len(plugins)} plugin(s).[/green]")
    console.print("\nPlugins are now available. Use [bold]matrixsh plugin list[/bold] to see them.")
    return 0


def cmd_unsync(args: argparse.Namespace) -> int:
    """Remove all ContextForge-synced plugins."""
    provider = ContextForgeProvider()

    if not args.force:
        answer = console.input("Remove all ContextForge plugins? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            console.print("[yellow]Cancelled.[/yellow]")
            return 0

    removed = provider.remove_synced_plugins()
    console.print(f"[green]Removed {removed} plugin(s).[/green]")
    return 0


def cmd_agents(args: argparse.Namespace) -> int:
    """List A2A agents from ContextForge."""
    provider = ContextForgeProvider()

    if not provider.is_connected():
        console.print("[red]Not connected to ContextForge.[/red]")
        return 1

    try:
        agents = provider.list_agents()
    except ContextForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    if not agents:
        console.print("[yellow]No A2A agents found (or A2A not enabled).[/yellow]")
        return 0

    table = Table(title="A2A Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Status")

    for agent in agents:
        table.add_row(
            agent.get("id", ""),
            agent.get("name", ""),
            agent.get("type", ""),
            agent.get("status", ""),
        )

    console.print(table)
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Configure ContextForge settings."""
    config = ContextForgeConfig.load()

    if args.url:
        config.base_url = args.url
    if args.namespace:
        config.namespace_prefix = args.namespace
    if args.sync_mode:
        config.sync_mode = args.sync_mode
    if args.auto_sync is not None:
        config.auto_sync = args.auto_sync

    config.save()

    console.print("[green]Configuration updated.[/green]")
    return cmd_status(args)


def create_cforge_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add ContextForge subcommands to the argument parser."""
    cforge_parser = subparsers.add_parser(
        "cforge",
        help="Manage ContextForge MCP gateway integration",
        description="Connect to IBM ContextForge to manage MCP servers and tools centrally.",
    )

    cforge_sub = cforge_parser.add_subparsers(dest="cforge_cmd")

    # login
    p_login = cforge_sub.add_parser("login", help="Login to ContextForge")
    p_login.add_argument("--url", help="ContextForge URL (e.g., http://localhost:4444)")
    p_login.add_argument("--token", help="JWT token or user:password")
    p_login.add_argument("--basic", action="store_true", help="Use basic auth")
    p_login.set_defaults(func=cmd_login)

    # logout
    p_logout = cforge_sub.add_parser("logout", help="Logout from ContextForge")
    p_logout.set_defaults(func=cmd_logout)

    # status
    p_status = cforge_sub.add_parser("status", help="Show connection status")
    p_status.set_defaults(func=cmd_status)

    # servers
    p_servers = cforge_sub.add_parser("servers", help="List servers")
    p_servers.add_argument("--active", "-a", action="store_true", help="Show only active servers")
    p_servers.set_defaults(func=cmd_servers_list)

    # servers enable
    p_enable = cforge_sub.add_parser("enable", help="Enable a server")
    p_enable.add_argument("id", help="Server ID")
    p_enable.set_defaults(func=cmd_servers_enable)

    # servers disable
    p_disable = cforge_sub.add_parser("disable", help="Disable a server")
    p_disable.add_argument("id", help="Server ID")
    p_disable.set_defaults(func=cmd_servers_disable)

    # tools
    p_tools = cforge_sub.add_parser("tools", help="List tools")
    p_tools.add_argument("--server", "-s", help="Filter by server ID")
    p_tools.set_defaults(func=cmd_tools)

    # sync
    p_sync = cforge_sub.add_parser("sync", help="Sync servers to MatrixShell plugins")
    p_sync.add_argument("--all", action="store_true", help="Include inactive servers")
    p_sync.set_defaults(func=cmd_sync)

    # unsync
    p_unsync = cforge_sub.add_parser("unsync", help="Remove all synced plugins")
    p_unsync.add_argument("--force", "-f", action="store_true", help="Skip confirmation")
    p_unsync.set_defaults(func=cmd_unsync)

    # agents
    p_agents = cforge_sub.add_parser("agents", help="List A2A agents")
    p_agents.set_defaults(func=cmd_agents)

    # config
    p_config = cforge_sub.add_parser("config", help="Configure ContextForge settings")
    p_config.add_argument("--url", help="ContextForge URL")
    p_config.add_argument("--namespace", help="Namespace prefix for tools")
    p_config.add_argument("--sync-mode", choices=["streamable-http", "stdio"], help="Connection mode")
    p_config.add_argument("--auto-sync", type=lambda x: x.lower() == "true", help="Auto-sync on startup")
    p_config.set_defaults(func=cmd_config)


def run_cforge_command(args: argparse.Namespace) -> int:
    """Run a ContextForge subcommand."""
    if not hasattr(args, "func") or args.func is None:
        # No subcommand given, show status
        return cmd_status(args)

    return args.func(args)
