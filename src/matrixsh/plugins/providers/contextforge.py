"""ContextForge Provider for MatrixShell.

Integrates IBM's MCP Context Forge (mcp-context-forge) as a centralized
catalog and gateway for MCP servers. This allows MatrixShell to:

1. Discover and sync MCP servers from ContextForge
2. Manage server activation/deactivation
3. Control tool access through unified policies
4. Act as the admin interface for all connected tools/agents

ContextForge endpoints used:
- GET /servers          - List all servers
- POST /servers         - Create a server
- GET /servers/{id}     - Get server details
- PUT /servers/{id}     - Update server
- DELETE /servers/{id}  - Delete server
- POST /servers/{id}/state?activate=true|false - Enable/disable
- GET /servers/{id}/tools - List tools for a server
- /servers/{id}/mcp     - MCP protocol endpoint (streamable-http)

References:
- https://github.com/IBM/mcp-context-forge
- https://ibm.github.io/mcp-context-forge/
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urljoin

import requests

from ..models import Plugin, PluginConfig, PluginPermissions, TransportType, PermissionLevel


@dataclass
class ContextForgeServer:
    """A server registered in ContextForge."""
    id: str
    name: str
    description: str = ""
    active: bool = True
    server_type: str = "mcp"  # mcp, rest, virtual, a2a
    transport: str = "streamable-http"
    tools: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> "ContextForgeServer":
        return cls(
            id=data.get("id", data.get("server_id", "")),
            name=data.get("name", data.get("server_name", "")),
            description=data.get("description", ""),
            active=data.get("active", data.get("is_active", True)),
            server_type=data.get("type", data.get("server_type", "mcp")),
            transport=data.get("transport", "streamable-http"),
            metadata=data,
        )


@dataclass
class ContextForgeTool:
    """A tool available from a ContextForge server."""
    name: str
    description: str = ""
    server_id: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict, server_id: str = "") -> "ContextForgeTool":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            server_id=server_id,
            input_schema=data.get("inputSchema", data.get("input_schema", {})),
        )


def _contextforge_config_path() -> Path:
    """Get path to ContextForge configuration file."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "matrixsh" / "contextforge.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "matrixsh" / "contextforge.json"


@dataclass
class ContextForgeConfig:
    """Configuration for ContextForge connection."""
    base_url: str = "http://localhost:4444"
    token: str = ""  # JWT token or "Basic user:pass"
    auth_type: Literal["bearer", "basic", "none"] = "bearer"
    namespace_prefix: str = "cforge"
    sync_mode: Literal["streamable-http", "stdio"] = "streamable-http"
    auto_sync: bool = True
    sync_active_only: bool = True
    default_permission: PermissionLevel = PermissionLevel.READ
    require_confirmation: bool = True

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "token": self.token,
            "auth_type": self.auth_type,
            "namespace_prefix": self.namespace_prefix,
            "sync_mode": self.sync_mode,
            "auto_sync": self.auto_sync,
            "sync_active_only": self.sync_active_only,
            "default_permission": self.default_permission.value,
            "require_confirmation": self.require_confirmation,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextForgeConfig":
        return cls(
            base_url=data.get("base_url", "http://localhost:4444"),
            token=data.get("token", ""),
            auth_type=data.get("auth_type", "bearer"),
            namespace_prefix=data.get("namespace_prefix", "cforge"),
            sync_mode=data.get("sync_mode", "streamable-http"),
            auto_sync=data.get("auto_sync", True),
            sync_active_only=data.get("sync_active_only", True),
            default_permission=PermissionLevel(data.get("default_permission", "read")),
            require_confirmation=data.get("require_confirmation", True),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        path = path or _contextforge_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ContextForgeConfig":
        path = path or _contextforge_config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except Exception:
            return cls()


class ContextForgeError(Exception):
    """Error from ContextForge operations."""
    pass


class ContextForgeProvider:
    """Provider that connects to ContextForge gateway.

    ContextForge is an MCP gateway/registry that manages multiple MCP servers.
    This provider syncs servers from ContextForge into MatrixShell's plugin system,
    allowing centralized management of all tools and agents.

    Usage:
        provider = ContextForgeProvider(config)
        provider.login(token)  # or use basic auth
        servers = provider.list_servers()
        provider.sync_to_plugins()  # Populate MatrixShell plugins
    """

    def __init__(self, config: Optional[ContextForgeConfig] = None):
        self.config = config or ContextForgeConfig.load()
        self._session = requests.Session()
        self._update_auth_headers()

    def _update_auth_headers(self) -> None:
        """Update session headers with authentication."""
        self._session.headers.clear()
        self._session.headers["Content-Type"] = "application/json"
        self._session.headers["Accept"] = "application/json"

        if self.config.auth_type == "bearer" and self.config.token:
            token = self.config.token
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            self._session.headers["Authorization"] = token
        elif self.config.auth_type == "basic" and self.config.token:
            # Token format: "user:password" or already base64 encoded
            self._session.headers["Authorization"] = f"Basic {self.config.token}"

    def _url(self, path: str) -> str:
        """Build full URL for API endpoint."""
        return urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/"))

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an API request."""
        try:
            response = self._session.request(method, self._url(path), timeout=30, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                try:
                    error_detail = e.response.json().get("detail", str(e))
                except Exception:
                    error_detail = e.response.text or str(e)
                raise ContextForgeError(f"API error: {error_detail}")
            raise ContextForgeError(f"HTTP error: {e}")
        except requests.exceptions.ConnectionError:
            raise ContextForgeError(f"Cannot connect to ContextForge at {self.config.base_url}")
        except Exception as e:
            raise ContextForgeError(f"Request failed: {e}")

    # --- Authentication ---

    def login(self, token: str, auth_type: Literal["bearer", "basic"] = "bearer") -> bool:
        """Set authentication token and verify connection."""
        self.config.token = token
        self.config.auth_type = auth_type
        self._update_auth_headers()

        # Verify by checking health
        try:
            self.health()
            self.config.save()
            return True
        except ContextForgeError:
            return False

    def logout(self) -> None:
        """Clear authentication."""
        self.config.token = ""
        self.config.save()
        self._update_auth_headers()

    # --- Health & Status ---

    def health(self) -> dict:
        """Check ContextForge health."""
        return self._request("GET", "/health")

    def is_connected(self) -> bool:
        """Check if we can connect to ContextForge."""
        try:
            self.health()
            return True
        except ContextForgeError:
            return False

    # --- Server Management ---

    def list_servers(self, active_only: bool = False) -> List[ContextForgeServer]:
        """List all servers registered in ContextForge."""
        data = self._request("GET", "/servers")
        servers = []

        # Handle different response formats
        items = data if isinstance(data, list) else data.get("servers", data.get("items", []))

        for item in items:
            server = ContextForgeServer.from_api(item)
            if active_only and not server.active:
                continue
            servers.append(server)

        return servers

    def get_server(self, server_id: str) -> ContextForgeServer:
        """Get details of a specific server."""
        data = self._request("GET", f"/servers/{server_id}")
        return ContextForgeServer.from_api(data)

    def create_server(
        self,
        name: str,
        server_type: str = "mcp",
        url: Optional[str] = None,
        command: Optional[List[str]] = None,
        description: str = "",
        **kwargs,
    ) -> ContextForgeServer:
        """Create a new server in ContextForge."""
        payload = {
            "name": name,
            "type": server_type,
            "description": description,
            **kwargs,
        }
        if url:
            payload["url"] = url
        if command:
            payload["command"] = command

        data = self._request("POST", "/servers", json=payload)
        return ContextForgeServer.from_api(data)

    def update_server(self, server_id: str, **updates) -> ContextForgeServer:
        """Update a server's configuration."""
        data = self._request("PUT", f"/servers/{server_id}", json=updates)
        return ContextForgeServer.from_api(data)

    def delete_server(self, server_id: str) -> bool:
        """Delete a server from ContextForge."""
        self._request("DELETE", f"/servers/{server_id}")
        return True

    def activate_server(self, server_id: str) -> bool:
        """Activate a server."""
        self._request("POST", f"/servers/{server_id}/state", params={"activate": "true"})
        return True

    def deactivate_server(self, server_id: str) -> bool:
        """Deactivate a server."""
        self._request("POST", f"/servers/{server_id}/state", params={"activate": "false"})
        return True

    # --- Tool Discovery ---

    def list_tools(self, server_id: Optional[str] = None) -> List[ContextForgeTool]:
        """List tools from a specific server or all servers."""
        if server_id:
            data = self._request("GET", f"/servers/{server_id}/tools")
            items = data if isinstance(data, list) else data.get("tools", [])
            return [ContextForgeTool.from_api(t, server_id) for t in items]
        else:
            # Get all tools across all servers
            data = self._request("GET", "/tools")
            items = data if isinstance(data, list) else data.get("tools", [])
            return [ContextForgeTool.from_api(t) for t in items]

    def get_server_tools(self, server_id: str) -> List[ContextForgeTool]:
        """Get tools for a specific server."""
        return self.list_tools(server_id)

    # --- MCP Endpoint ---

    def get_mcp_url(self, server_id: str) -> str:
        """Get the MCP endpoint URL for a server."""
        return self._url(f"/servers/{server_id}/mcp")

    def get_mcp_headers(self) -> Dict[str, str]:
        """Get headers needed for MCP connection."""
        headers = {"Content-Type": "application/json"}
        if self.config.auth_type == "bearer" and self.config.token:
            token = self.config.token
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            headers["Authorization"] = token
        elif self.config.auth_type == "basic" and self.config.token:
            headers["Authorization"] = f"Basic {self.config.token}"
        return headers

    # --- Sync to MatrixShell Plugins ---

    def server_to_plugin(self, server: ContextForgeServer) -> Plugin:
        """Convert a ContextForge server to a MatrixShell plugin."""
        namespace = f"{self.config.namespace_prefix}.{server.name}".replace(" ", "_").lower()
        plugin_id = f"cforge-{server.id}"

        if self.config.sync_mode == "streamable-http":
            # Direct HTTP connection to MCP endpoint
            return Plugin(
                id=plugin_id,
                name=f"ContextForge: {server.name}",
                enabled=server.active,
                transport=TransportType.HTTP,
                url=self.get_mcp_url(server.id),
                namespace=namespace,
                allow_tools=[],  # Allow all by default
                permissions=PluginPermissions(
                    level=self.config.default_permission,
                    requires_confirmation=self.config.require_confirmation,
                ),
            )
        else:
            # Use stdio wrapper
            return Plugin(
                id=plugin_id,
                name=f"ContextForge: {server.name}",
                enabled=server.active,
                transport=TransportType.STDIO,
                command=["python", "-m", "mcpgateway.wrapper"],
                env={
                    "MCP_SERVER_URL": self.get_mcp_url(server.id),
                    "MCP_AUTH": self.get_mcp_headers().get("Authorization", ""),
                },
                namespace=namespace,
                allow_tools=[],
                permissions=PluginPermissions(
                    level=self.config.default_permission,
                    requires_confirmation=self.config.require_confirmation,
                ),
            )

    def sync_to_plugins(
        self,
        plugin_config: Optional[PluginConfig] = None,
        active_only: Optional[bool] = None,
    ) -> List[Plugin]:
        """Sync ContextForge servers to MatrixShell plugin config.

        This creates/updates plugin entries for each ContextForge server,
        allowing MatrixShell to use them as tool sources.

        Returns list of synced plugins.
        """
        if active_only is None:
            active_only = self.config.sync_active_only

        # Load or use provided config
        config = plugin_config or PluginConfig.load()

        # Get servers from ContextForge
        servers = self.list_servers(active_only=active_only)

        # Convert to plugins
        synced_plugins = []
        for server in servers:
            plugin = self.server_to_plugin(server)

            # Check if plugin already exists
            existing = config.get_plugin(plugin.id)
            if existing:
                # Update existing plugin, preserve user customizations
                plugin.allow_tools = existing.allow_tools or plugin.allow_tools
                plugin.deny_tools = existing.deny_tools
                plugin.permissions = existing.permissions

            config.add_plugin(plugin)
            synced_plugins.append(plugin)

        # Save config
        config.save()

        return synced_plugins

    def remove_synced_plugins(self, plugin_config: Optional[PluginConfig] = None) -> int:
        """Remove all ContextForge-synced plugins from config.

        Returns count of removed plugins.
        """
        config = plugin_config or PluginConfig.load()
        removed = 0

        # Remove plugins with cforge- prefix
        for plugin in list(config.plugins):
            if plugin.id.startswith("cforge-"):
                config.remove_plugin(plugin.id)
                removed += 1

        config.save()
        return removed

    # --- A2A Agent Management (if available) ---

    def list_agents(self) -> List[dict]:
        """List A2A agents registered in ContextForge."""
        try:
            data = self._request("GET", "/a2a")
            return data if isinstance(data, list) else data.get("agents", [])
        except ContextForgeError:
            return []  # A2A might not be enabled

    def get_agent(self, agent_id: str) -> dict:
        """Get details of an A2A agent."""
        return self._request("GET", f"/a2a/{agent_id}")

    # --- Convenience Methods ---

    def get_all_tools_flat(self) -> List[Dict[str, Any]]:
        """Get all tools from all servers as a flat list with server info."""
        all_tools = []
        for server in self.list_servers(active_only=True):
            try:
                tools = self.list_tools(server.id)
                for tool in tools:
                    all_tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "server_id": server.id,
                        "server_name": server.name,
                        "namespace": f"{self.config.namespace_prefix}.{server.name}".replace(" ", "_").lower(),
                        "full_name": f"{self.config.namespace_prefix}.{server.name}.{tool.name}".replace(" ", "_").lower(),
                    })
            except ContextForgeError:
                continue  # Skip servers with errors
        return all_tools
