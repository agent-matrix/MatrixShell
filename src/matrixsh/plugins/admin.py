"""Plugin Admin CLI.

Provides commands for managing plugins:
- matrixsh plugin list
- matrixsh plugin add
- matrixsh plugin remove
- matrixsh plugin enable/disable
- matrixsh plugin tools
- matrixsh plugin doctor
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import Plugin, PluginConfig, TransportType, PermissionLevel, PluginPermissions
from .manager import PluginManager, create_stdio_plugin, create_http_plugin

console = Console()


def cmd_list(args: argparse.Namespace) -> int:
    """List all configured plugins."""
    manager = PluginManager()

    if not manager.config.plugins:
        console.print("[yellow]No plugins configured.[/yellow]")
        console.print("\nTo add a plugin, run:")
        console.print("  [bold]matrixsh plugin add --help[/bold]")
        return 0

    table = Table(title="Configured Plugins")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Namespace", style="magenta")
    table.add_column("Transport")
    table.add_column("Enabled", justify="center")
    table.add_column("Status")

    for plugin in manager.config.plugins:
        enabled = "[green]Yes[/green]" if plugin.enabled else "[red]No[/red]"

        # Check status
        if not plugin.enabled:
            status = "[dim]Disabled[/dim]"
        elif plugin.connected:
            status = f"[green]Connected ({len(plugin.available_tools)} tools)[/green]"
        elif plugin.error:
            status = f"[red]Error: {plugin.error}[/red]"
        else:
            status = "[yellow]Not connected[/yellow]"

        table.add_row(
            plugin.id,
            plugin.name,
            plugin.namespace,
            plugin.transport.value,
            enabled,
            status,
        )

    console.print(table)
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """Add a new plugin."""
    manager = PluginManager()

    # Check if plugin already exists
    if manager.get_plugin(args.id):
        if not args.force:
            console.print(f"[red]Plugin '{args.id}' already exists.[/red]")
            console.print("Use --force to overwrite.")
            return 1

    # Determine transport type
    if args.url:
        transport = TransportType.HTTP
    elif args.command:
        transport = TransportType.STDIO
    else:
        console.print("[red]Either --command or --url is required.[/red]")
        return 1

    # Parse allow/deny tools
    allow_tools = args.allow.split(",") if args.allow else []
    deny_tools = args.deny.split(",") if args.deny else []

    # Parse permission level
    try:
        level = PermissionLevel(args.permission)
    except ValueError:
        console.print(f"[red]Invalid permission level: {args.permission}[/red]")
        console.print("Valid options: read, write, admin")
        return 1

    # Create plugin
    plugin = Plugin(
        id=args.id,
        name=args.name or args.id,
        enabled=True,
        transport=transport,
        command=args.command.split() if args.command else [],
        url=args.url,
        namespace=args.namespace or args.id,
        allow_tools=allow_tools,
        deny_tools=deny_tools,
        permissions=PluginPermissions(
            level=level,
            requires_confirmation=not args.no_confirm,
        ),
    )

    manager.add_plugin(plugin)
    console.print(f"[green]Plugin '{args.id}' added successfully.[/green]")

    # Show summary
    table = Table(show_header=False, box=None)
    table.add_row("ID:", plugin.id)
    table.add_row("Name:", plugin.name)
    table.add_row("Namespace:", plugin.namespace)
    table.add_row("Transport:", plugin.transport.value)
    if plugin.command:
        table.add_row("Command:", " ".join(plugin.command))
    if plugin.url:
        table.add_row("URL:", plugin.url)
    table.add_row("Permission:", plugin.permissions.level.value)
    console.print(table)

    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove a plugin."""
    manager = PluginManager()

    if not manager.get_plugin(args.id):
        console.print(f"[red]Plugin '{args.id}' not found.[/red]")
        return 1

    if manager.remove_plugin(args.id):
        console.print(f"[green]Plugin '{args.id}' removed.[/green]")
        return 0
    else:
        console.print(f"[red]Failed to remove plugin '{args.id}'.[/red]")
        return 1


def cmd_enable(args: argparse.Namespace) -> int:
    """Enable a plugin."""
    manager = PluginManager()

    if not manager.get_plugin(args.id):
        console.print(f"[red]Plugin '{args.id}' not found.[/red]")
        return 1

    manager.enable_plugin(args.id)
    console.print(f"[green]Plugin '{args.id}' enabled.[/green]")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    """Disable a plugin."""
    manager = PluginManager()

    if not manager.get_plugin(args.id):
        console.print(f"[red]Plugin '{args.id}' not found.[/red]")
        return 1

    manager.disable_plugin(args.id)
    console.print(f"[yellow]Plugin '{args.id}' disabled.[/yellow]")
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    """List tools from a plugin."""
    manager = PluginManager()

    plugin = manager.get_plugin(args.id)
    if not plugin:
        console.print(f"[red]Plugin '{args.id}' not found.[/red]")
        return 1

    if not plugin.enabled:
        console.print(f"[yellow]Plugin '{args.id}' is disabled.[/yellow]")
        return 1

    # Connect to get tools
    console.print(f"Connecting to plugin '{args.id}'...")
    success, error = manager.connect_plugin(args.id)

    if not success:
        console.print(f"[red]Failed to connect: {error}[/red]")
        return 1

    tools = manager.get_plugin_tools(args.id)

    if not tools:
        console.print("[yellow]No tools available from this plugin.[/yellow]")
        return 0

    table = Table(title=f"Tools from '{plugin.name}' ({plugin.namespace}.*)")
    table.add_column("Tool", style="cyan")
    table.add_column("Full Name", style="magenta")
    table.add_column("Description")

    for tool in tools:
        table.add_row(
            tool.name,
            tool.full_name,
            tool.description or "[dim]No description[/dim]",
        )

    console.print(table)

    # Disconnect
    manager.disconnect_plugin(args.id)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check health of all plugins."""
    manager = PluginManager()

    if not manager.config.plugins:
        console.print("[yellow]No plugins configured.[/yellow]")
        return 0

    console.print("[bold]Plugin Health Check[/bold]\n")

    # First, try to connect all enabled plugins
    for plugin in manager.config.get_enabled_plugins():
        console.print(f"Checking '{plugin.id}'...", end=" ")
        success, error = manager.connect_plugin(plugin.id)
        if success:
            console.print("[green]OK[/green]")
        else:
            console.print(f"[red]FAIL[/red] - {error}")

    console.print()

    # Show detailed status
    results = manager.doctor()

    table = Table(title="Plugin Status")
    table.add_column("Plugin", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    for result in results:
        status = result["status"]
        if status == "connected":
            status_str = "[green]Connected[/green]"
        elif status == "disabled":
            status_str = "[dim]Disabled[/dim]"
        elif status == "error":
            status_str = "[red]Error[/red]"
        else:
            status_str = "[yellow]Disconnected[/yellow]"

        table.add_row(
            result["name"],
            status_str,
            result["message"],
        )

    console.print(table)

    # Disconnect all
    manager.disconnect_all()
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    """Test connection to a plugin."""
    manager = PluginManager()

    plugin = manager.get_plugin(args.id)
    if not plugin:
        console.print(f"[red]Plugin '{args.id}' not found.[/red]")
        return 1

    console.print(f"Connecting to '{args.id}'...")
    success, error = manager.connect_plugin(args.id)

    if success:
        tools = manager.get_plugin_tools(args.id)
        console.print(f"[green]Connected successfully![/green]")
        console.print(f"Available tools: {len(tools)}")

        if tools and args.verbose:
            for tool in tools:
                console.print(f"  - {tool.full_name}")

        manager.disconnect_plugin(args.id)
    else:
        console.print(f"[red]Connection failed: {error}[/red]")
        return 1

    return 0


def create_plugin_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add plugin subcommands to the argument parser."""
    plugin_parser = subparsers.add_parser(
        "plugin",
        help="Manage MCP server plugins",
        description="Add, remove, and manage external MCP server plugins.",
    )

    plugin_sub = plugin_parser.add_subparsers(dest="plugin_cmd")

    # list
    p_list = plugin_sub.add_parser("list", help="List all plugins")
    p_list.set_defaults(func=cmd_list)

    # add
    p_add = plugin_sub.add_parser("add", help="Add a new plugin")
    p_add.add_argument("id", help="Unique plugin ID")
    p_add.add_argument("--name", help="Human-readable name")
    p_add.add_argument("--namespace", help="Tool namespace (default: same as ID)")
    p_add.add_argument("--command", help="Command to start MCP server (for stdio transport)")
    p_add.add_argument("--url", help="HTTP URL for MCP server (for http transport)")
    p_add.add_argument("--allow", help="Comma-separated list of allowed tools")
    p_add.add_argument("--deny", help="Comma-separated list of denied tools")
    p_add.add_argument("--permission", choices=["read", "write", "admin"], default="read",
                       help="Permission level (default: read)")
    p_add.add_argument("--no-confirm", action="store_true",
                       help="Don't require confirmation for tool calls")
    p_add.add_argument("--force", action="store_true", help="Overwrite if exists")
    p_add.set_defaults(func=cmd_add)

    # remove
    p_remove = plugin_sub.add_parser("remove", help="Remove a plugin")
    p_remove.add_argument("id", help="Plugin ID to remove")
    p_remove.set_defaults(func=cmd_remove)

    # enable
    p_enable = plugin_sub.add_parser("enable", help="Enable a plugin")
    p_enable.add_argument("id", help="Plugin ID to enable")
    p_enable.set_defaults(func=cmd_enable)

    # disable
    p_disable = plugin_sub.add_parser("disable", help="Disable a plugin")
    p_disable.add_argument("id", help="Plugin ID to disable")
    p_disable.set_defaults(func=cmd_disable)

    # tools
    p_tools = plugin_sub.add_parser("tools", help="List tools from a plugin")
    p_tools.add_argument("id", help="Plugin ID")
    p_tools.set_defaults(func=cmd_tools)

    # doctor
    p_doctor = plugin_sub.add_parser("doctor", help="Check health of all plugins")
    p_doctor.set_defaults(func=cmd_doctor)

    # connect (test)
    p_connect = plugin_sub.add_parser("connect", help="Test connection to a plugin")
    p_connect.add_argument("id", help="Plugin ID")
    p_connect.add_argument("-v", "--verbose", action="store_true", help="Show tool list")
    p_connect.set_defaults(func=cmd_connect)


def run_plugin_command(args: argparse.Namespace) -> int:
    """Run a plugin subcommand."""
    if not hasattr(args, "func"):
        # No subcommand given, show list by default
        return cmd_list(args)

    return args.func(args)
