"""Plugin Manager.

Handles loading, connecting, and managing external MCP server plugins.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .models import Plugin, PluginConfig, TransportType, PermissionLevel
from .connector import PluginConnector, ToolInfo, ToolCallResult


@dataclass
class PluginStatus:
    """Status information for a plugin."""
    id: str
    name: str
    enabled: bool
    connected: bool
    transport: str
    tool_count: int
    error: Optional[str] = None


class PluginManager:
    """Manages plugin lifecycle and connections.

    Responsibilities:
    - Load plugin configuration
    - Connect/disconnect plugins
    - Track plugin status
    - Provide unified tool catalog
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        self._config = config or PluginConfig.load()
        self._connectors: Dict[str, PluginConnector] = {}
        self._on_status_change: Optional[Callable[[str, PluginStatus], None]] = None

    @property
    def config(self) -> PluginConfig:
        return self._config

    def reload_config(self) -> None:
        """Reload configuration from disk."""
        self._config = PluginConfig.load()

    def save_config(self) -> None:
        """Save configuration to disk."""
        self._config.save()

    def get_all_plugins(self) -> List[Plugin]:
        """Get all configured plugins."""
        return self._config.plugins

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a plugin by ID."""
        return self._config.get_plugin(plugin_id)

    def add_plugin(self, plugin: Plugin, save: bool = True) -> None:
        """Add or update a plugin."""
        self._config.add_plugin(plugin)
        if save:
            self.save_config()

    def remove_plugin(self, plugin_id: str, save: bool = True) -> bool:
        """Remove a plugin."""
        # Disconnect first
        self.disconnect_plugin(plugin_id)

        if self._config.remove_plugin(plugin_id):
            if save:
                self.save_config()
            return True
        return False

    def enable_plugin(self, plugin_id: str, save: bool = True) -> bool:
        """Enable a plugin."""
        plugin = self._config.get_plugin(plugin_id)
        if plugin:
            plugin.enabled = True
            if save:
                self.save_config()
            return True
        return False

    def disable_plugin(self, plugin_id: str, save: bool = True) -> bool:
        """Disable a plugin and disconnect it."""
        plugin = self._config.get_plugin(plugin_id)
        if plugin:
            plugin.enabled = False
            self.disconnect_plugin(plugin_id)
            if save:
                self.save_config()
            return True
        return False

    def connect_plugin(self, plugin_id: str) -> Tuple[bool, Optional[str]]:
        """Connect to a plugin's MCP server.

        Returns (success, error_message).
        """
        plugin = self._config.get_plugin(plugin_id)
        if not plugin:
            return False, f"Plugin '{plugin_id}' not found"

        if not plugin.enabled:
            return False, f"Plugin '{plugin_id}' is disabled"

        # Check if command exists for stdio transport
        if plugin.transport == TransportType.STDIO and plugin.command:
            cmd = plugin.command[0]
            if not shutil.which(cmd):
                plugin.error = f"Command not found: {cmd}"
                return False, plugin.error

        # Create connector if needed
        if plugin_id not in self._connectors:
            self._connectors[plugin_id] = PluginConnector(plugin)

        connector = self._connectors[plugin_id]

        if connector.is_connected:
            return True, None

        try:
            success = connector.connect()
            if success:
                return True, None
            return False, plugin.error or "Connection failed"
        except Exception as e:
            return False, str(e)

    def disconnect_plugin(self, plugin_id: str) -> None:
        """Disconnect from a plugin's MCP server."""
        if plugin_id in self._connectors:
            self._connectors[plugin_id].disconnect()
            del self._connectors[plugin_id]

    def connect_all_enabled(self) -> Dict[str, Tuple[bool, Optional[str]]]:
        """Connect to all enabled plugins.

        Returns dict of {plugin_id: (success, error)}.
        """
        results = {}
        for plugin in self._config.get_enabled_plugins():
            results[plugin.id] = self.connect_plugin(plugin.id)
        return results

    def disconnect_all(self) -> None:
        """Disconnect from all plugins."""
        for plugin_id in list(self._connectors.keys()):
            self.disconnect_plugin(plugin_id)

    def get_plugin_status(self, plugin_id: str) -> Optional[PluginStatus]:
        """Get status of a plugin."""
        plugin = self._config.get_plugin(plugin_id)
        if not plugin:
            return None

        connector = self._connectors.get(plugin_id)
        return PluginStatus(
            id=plugin.id,
            name=plugin.name,
            enabled=plugin.enabled,
            connected=connector.is_connected if connector else False,
            transport=plugin.transport.value,
            tool_count=len(plugin.available_tools),
            error=plugin.error,
        )

    def get_all_statuses(self) -> List[PluginStatus]:
        """Get status of all plugins."""
        statuses = []
        for plugin in self._config.plugins:
            status = self.get_plugin_status(plugin.id)
            if status:
                statuses.append(status)
        return statuses

    def get_plugin_tools(self, plugin_id: str) -> List[ToolInfo]:
        """Get available tools from a connected plugin."""
        connector = self._connectors.get(plugin_id)
        if connector and connector.is_connected:
            return connector.get_tools()
        return []

    def get_all_tools(self) -> List[ToolInfo]:
        """Get all available tools from all connected plugins."""
        tools = []
        for connector in self._connectors.values():
            if connector.is_connected:
                tools.extend(connector.get_tools())
        return tools

    def call_tool(
        self,
        plugin_id: str,
        tool_name: str,
        arguments: Dict,
    ) -> ToolCallResult:
        """Call a tool on a connected plugin."""
        connector = self._connectors.get(plugin_id)
        if not connector:
            return ToolCallResult(success=False, error=f"Plugin '{plugin_id}' not connected")

        return connector.call_tool(tool_name, arguments)

    def call_namespaced_tool(
        self,
        full_name: str,
        arguments: Dict,
    ) -> ToolCallResult:
        """Call a tool by its full namespaced name (e.g., 'github.create_issue').

        Automatically routes to the correct plugin.
        """
        if "." not in full_name:
            return ToolCallResult(success=False, error=f"Invalid tool name: {full_name}. Expected 'namespace.tool'")

        namespace, tool_name = full_name.split(".", 1)

        # Find plugin with matching namespace
        for plugin in self._config.plugins:
            if plugin.namespace == namespace and plugin.enabled:
                return self.call_tool(plugin.id, tool_name, arguments)

        return ToolCallResult(success=False, error=f"No plugin found for namespace '{namespace}'")

    def doctor(self) -> List[Dict]:
        """Check health of all plugins.

        Returns list of {plugin_id, status, message} dicts.
        """
        results = []

        for plugin in self._config.plugins:
            result = {"plugin_id": plugin.id, "name": plugin.name}

            if not plugin.enabled:
                result["status"] = "disabled"
                result["message"] = "Plugin is disabled"
                results.append(result)
                continue

            # Check command availability for stdio
            if plugin.transport == TransportType.STDIO and plugin.command:
                cmd = plugin.command[0]
                if not shutil.which(cmd):
                    result["status"] = "error"
                    result["message"] = f"Command not found: {cmd}"
                    results.append(result)
                    continue

            # Check connectivity
            connector = self._connectors.get(plugin.id)
            if connector and connector.is_connected:
                result["status"] = "connected"
                result["message"] = f"Connected with {len(plugin.available_tools)} tools"
            else:
                result["status"] = "disconnected"
                result["message"] = plugin.error or "Not connected"

            results.append(result)

        return results


# Convenience functions for quick plugin creation
def create_stdio_plugin(
    plugin_id: str,
    command: List[str],
    name: Optional[str] = None,
    namespace: Optional[str] = None,
    allow_tools: Optional[List[str]] = None,
    requires_confirmation: bool = True,
) -> Plugin:
    """Create a stdio-based plugin configuration."""
    from .models import PluginPermissions
    return Plugin(
        id=plugin_id,
        name=name or plugin_id,
        transport=TransportType.STDIO,
        command=command,
        namespace=namespace or plugin_id,
        allow_tools=allow_tools or [],
        permissions=PluginPermissions(
            level=PermissionLevel.READ,
            requires_confirmation=requires_confirmation,
        ),
    )


def create_http_plugin(
    plugin_id: str,
    url: str,
    name: Optional[str] = None,
    namespace: Optional[str] = None,
    allow_tools: Optional[List[str]] = None,
    requires_confirmation: bool = True,
) -> Plugin:
    """Create an HTTP-based plugin configuration."""
    from .models import PluginPermissions
    return Plugin(
        id=plugin_id,
        name=name or plugin_id,
        transport=TransportType.HTTP,
        url=url,
        namespace=namespace or plugin_id,
        allow_tools=allow_tools or [],
        permissions=PluginPermissions(
            level=PermissionLevel.READ,
            requires_confirmation=requires_confirmation,
        ),
    )
