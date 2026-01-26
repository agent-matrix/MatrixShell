"""Catalog Client for MatrixShell.

Generic connector for MCP server catalogs (ContextForge, etc.).
Provides normalized interfaces for server and tool discovery.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urljoin

import requests


def _catalog_config_path() -> Path:
    """Get path to catalog configuration file."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "matrixsh" / "catalog.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "matrixsh" / "catalog.json"


@dataclass
class CatalogConfig:
    """Configuration for catalog connection."""
    url: str = ""
    token: str = ""
    sync_mode: Literal["streamable-http", "stdio"] = "streamable-http"
    namespace: str = "catalog"
    enabled: bool = False

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "token": self.token,
            "sync_mode": self.sync_mode,
            "namespace": self.namespace,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CatalogConfig":
        return cls(
            url=data.get("url", ""),
            token=data.get("token", ""),
            sync_mode=data.get("sync_mode", "streamable-http"),
            namespace=data.get("namespace", "catalog"),
            enabled=data.get("enabled", False),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        path = path or _catalog_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "CatalogConfig":
        path = path or _catalog_config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except Exception:
            return cls()

    def is_configured(self) -> bool:
        """Check if catalog is configured with URL and token."""
        return bool(self.url and self.token and self.enabled)


@dataclass
class CatalogServer:
    """Normalized server representation."""
    id: str
    name: str
    active: bool
    mcp_url: str
    description: str = ""
    server_type: str = "mcp"

    @classmethod
    def from_api(cls, data: dict, base_url: str) -> "CatalogServer":
        server_id = data.get("id", data.get("server_id", ""))
        return cls(
            id=server_id,
            name=data.get("name", data.get("server_name", "")),
            active=data.get("active", data.get("is_active", True)),
            mcp_url=f"{base_url.rstrip('/')}/servers/{server_id}/mcp",
            description=data.get("description", ""),
            server_type=data.get("type", data.get("server_type", "mcp")),
        )


@dataclass
class CatalogTool:
    """Normalized tool representation."""
    server_id: str
    server_name: str
    tool: str
    description: str = ""

    @classmethod
    def from_api(cls, data: dict, server_id: str = "", server_name: str = "") -> "CatalogTool":
        return cls(
            server_id=server_id,
            server_name=server_name,
            tool=data.get("name", ""),
            description=data.get("description", ""),
        )


class CatalogError(Exception):
    """Error from catalog operations."""
    pass


class CatalogClient:
    """Client for MCP server catalogs.

    Provides a unified interface to catalog backends like ContextForge.
    All server/tool data is normalized to standard shapes.
    """

    def __init__(self, config: Optional[CatalogConfig] = None):
        self.config = config or CatalogConfig.load()
        self._session = requests.Session()
        self._update_auth_headers()

    def _update_auth_headers(self) -> None:
        """Update session headers with authentication."""
        self._session.headers.clear()
        self._session.headers["Content-Type"] = "application/json"
        self._session.headers["Accept"] = "application/json"

        if self.config.token:
            token = self.config.token
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            self._session.headers["Authorization"] = token

    def _url(self, path: str) -> str:
        """Build full URL for API endpoint."""
        return urljoin(self.config.url.rstrip("/") + "/", path.lstrip("/"))

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an API request."""
        if not self.config.url:
            raise CatalogError("Catalog URL not configured. Run 'matrixsh login' first.")

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
                raise CatalogError(f"API error: {error_detail}")
            raise CatalogError(f"HTTP error: {e}")
        except requests.exceptions.ConnectionError:
            raise CatalogError(f"Cannot connect to catalog at {self.config.url}")
        except Exception as e:
            raise CatalogError(f"Request failed: {e}")

    # --- Authentication ---

    def login(self, url: str, token: str) -> bool:
        """Login to catalog and save configuration."""
        self.config.url = url
        self.config.token = token
        self.config.enabled = True
        self._update_auth_headers()

        # Verify by listing servers
        try:
            self.list_servers()
            self.config.save()
            return True
        except CatalogError:
            self.config.enabled = False
            return False

    def logout(self) -> None:
        """Clear authentication and disable catalog."""
        self.config.token = ""
        self.config.enabled = False
        self.config.save()
        self._update_auth_headers()

    # --- Health & Status ---

    def is_reachable(self) -> bool:
        """Check if catalog is reachable."""
        if not self.config.is_configured():
            return False
        try:
            self.list_servers()
            return True
        except CatalogError:
            return False

    def health(self) -> dict:
        """Get catalog health status."""
        try:
            return self._request("GET", "/health")
        except CatalogError:
            return {"status": "unreachable"}

    # --- Server Management ---

    def list_servers(self, active_only: bool = False) -> List[CatalogServer]:
        """List all servers in the catalog."""
        data = self._request("GET", "/servers")
        servers = []

        # Handle different response formats
        items = data if isinstance(data, list) else data.get("servers", data.get("items", []))

        for item in items:
            server = CatalogServer.from_api(item, self.config.url)
            if active_only and not server.active:
                continue
            servers.append(server)

        return servers

    def get_server(self, server_id: str) -> CatalogServer:
        """Get a specific server by ID."""
        data = self._request("GET", f"/servers/{server_id}")
        return CatalogServer.from_api(data, self.config.url)

    def enable_server(self, server_id: str) -> bool:
        """Enable a server."""
        self._request("POST", f"/servers/{server_id}/state", params={"activate": "true"})
        return True

    def disable_server(self, server_id: str) -> bool:
        """Disable a server."""
        self._request("POST", f"/servers/{server_id}/state", params={"activate": "false"})
        return True

    # --- Tool Discovery ---

    def list_tools(self, server_id: Optional[str] = None) -> List[CatalogTool]:
        """List tools from a specific server or all servers."""
        if server_id:
            # Get tools for specific server
            try:
                data = self._request("GET", f"/servers/{server_id}/tools")
                items = data if isinstance(data, list) else data.get("tools", [])
                server = self.get_server(server_id)
                return [CatalogTool.from_api(t, server_id, server.name) for t in items]
            except CatalogError:
                return []
        else:
            # Get all tools from all active servers
            tools = []
            for server in self.list_servers(active_only=True):
                try:
                    data = self._request("GET", f"/servers/{server.id}/tools")
                    items = data if isinstance(data, list) else data.get("tools", [])
                    for t in items:
                        tools.append(CatalogTool.from_api(t, server.id, server.name))
                except CatalogError:
                    continue  # Skip servers with errors
            return tools

    # --- Statistics ---

    def get_stats(self) -> dict:
        """Get catalog statistics."""
        servers = self.list_servers()
        active = [s for s in servers if s.active]
        tools = self.list_tools()

        return {
            "total_servers": len(servers),
            "active_servers": len(active),
            "total_tools": len(tools),
        }
