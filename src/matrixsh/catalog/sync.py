"""Catalog Sync Engine for MatrixShell.

Handles syncing catalog servers to plugins.json and tracking sync state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .client import CatalogClient, CatalogConfig, CatalogServer, CatalogError


@dataclass
class SyncStatus:
    """Status of catalog sync."""
    last_sync_ts: Optional[str] = None
    synced_plugin_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "last_sync_ts": self.last_sync_ts,
            "synced_plugin_ids": self.synced_plugin_ids,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SyncStatus":
        return cls(
            last_sync_ts=data.get("last_sync_ts"),
            synced_plugin_ids=data.get("synced_plugin_ids", []),
        )


@dataclass
class SyncedPlugin:
    """A plugin synced from the catalog."""
    id: str
    name: str
    enabled: bool
    tool_namespace: str
    transport: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_s: float = 30.0
    allow_tools: List[str] = field(default_factory=list)
    source: str = "catalog"
    catalog_server_id: str = ""

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "namespace": self.tool_namespace,  # Use 'namespace' to match Plugin model
            "transport": self.transport,
            "url": self.url,
            "headers": self.headers,
            "timeout_s": self.timeout_s,
            "allow_tools": self.allow_tools,
            "source": self.source,
            "catalog_server_id": self.catalog_server_id,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SyncedPlugin":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            tool_namespace=data.get("namespace", data.get("tool_namespace", "")),
            transport=data.get("transport", "streamable-http"),
            url=data.get("url", ""),
            headers=data.get("headers", {}),
            timeout_s=data.get("timeout_s", 30.0),
            allow_tools=data.get("allow_tools", []),
            source=data.get("source", ""),
            catalog_server_id=data.get("catalog_server_id", ""),
        )

    @classmethod
    def from_server(
        cls,
        server: CatalogServer,
        namespace_prefix: str,
        auth_token: Optional[str] = None,
    ) -> "SyncedPlugin":
        """Create a plugin entry from a catalog server.

        Args:
            server: CatalogServer from the catalog
            namespace_prefix: Prefix for tool namespace (e.g., "catalog")
            auth_token: JWT token for Authorization header
        """
        # Clean namespace: lowercase, replace spaces with underscores
        clean_name = server.name.lower().replace(" ", "_").replace("-", "_")
        namespace = f"{namespace_prefix}.{clean_name}" if namespace_prefix else clean_name

        # Build headers with auth if provided
        headers: Dict[str, str] = {}
        if auth_token:
            token = auth_token
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            headers["Authorization"] = token

        return cls(
            id=f"catalog-{server.id}",
            name=server.name,
            enabled=server.active,
            tool_namespace=namespace,
            transport="streamable-http",  # Proper MCP protocol
            url=server.mcp_url,
            headers=headers,
            timeout_s=30.0,
            source="catalog",
            catalog_server_id=server.id,
        )


def _plugins_config_path() -> Path:
    """Get path to plugins configuration file."""
    import os
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "matrixsh" / "plugins.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "matrixsh" / "plugins.json"


def _load_plugins_config() -> dict:
    """Load plugins.json configuration."""
    path = _plugins_config_path()
    if not path.exists():
        return {"plugins": [], "catalog_sync": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Ensure required keys exist
        if "plugins" not in data:
            data["plugins"] = []
        if "catalog_sync" not in data:
            data["catalog_sync"] = {}
        return data
    except Exception:
        return {"plugins": [], "catalog_sync": {}}


def _save_plugins_config(data: dict) -> Path:
    """Save plugins.json configuration."""
    path = _plugins_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def get_sync_status() -> SyncStatus:
    """Get current sync status."""
    config = _load_plugins_config()
    return SyncStatus.from_dict(config.get("catalog_sync", {}))


def sync_catalog(client: Optional[CatalogClient] = None) -> dict:
    """Sync catalog servers to plugins.json.

    Returns dict with:
    - synced: list of synced plugin IDs
    - added: count of new plugins
    - updated: count of updated plugins
    - removed: count of removed plugins (servers no longer in catalog)
    """
    if client is None:
        client = CatalogClient()

    if not client.config.is_configured():
        raise CatalogError("Catalog not configured. Run 'matrixsh login' first.")

    # Get active servers from catalog
    servers = client.list_servers(active_only=True)
    server_ids = {s.id for s in servers}

    # Load current config
    config = _load_plugins_config()
    plugins = config.get("plugins", [])

    # Track changes
    existing_catalog_plugins = {
        p["id"]: p for p in plugins
        if p.get("source") == "catalog"
    }
    non_catalog_plugins = [
        p for p in plugins
        if p.get("source") != "catalog"
    ]

    added = 0
    updated = 0
    removed = 0
    synced_ids = []

    # Create/update plugins for active servers
    # Pass auth token so plugins can connect to MCP endpoints
    auth_token = client.config.token
    new_plugins = []
    for server in servers:
        plugin = SyncedPlugin.from_server(
            server,
            client.config.namespace,
            auth_token=auth_token,
        )
        plugin_dict = plugin.to_dict()
        plugin_id = plugin_dict["id"]
        synced_ids.append(plugin_id)

        if plugin_id in existing_catalog_plugins:
            # Preserve user customizations (allow_tools, etc.)
            existing = existing_catalog_plugins[plugin_id]
            if existing.get("allow_tools"):
                plugin_dict["allow_tools"] = existing["allow_tools"]
            updated += 1
        else:
            added += 1

        new_plugins.append(plugin_dict)

    # Count removed (catalog plugins no longer in catalog)
    for plugin_id in existing_catalog_plugins:
        if plugin_id not in synced_ids:
            removed += 1

    # Merge: non-catalog plugins + new catalog plugins
    config["plugins"] = non_catalog_plugins + new_plugins

    # Update sync metadata
    config["catalog_sync"] = {
        "last_sync_ts": datetime.now(timezone.utc).isoformat(),
        "synced_plugin_ids": synced_ids,
    }

    # Save
    _save_plugins_config(config)

    return {
        "synced": synced_ids,
        "added": added,
        "updated": updated,
        "removed": removed,
    }


def unsync_catalog() -> dict:
    """Remove all catalog-synced plugins from plugins.json.

    Returns dict with:
    - removed: count of removed plugins
    - removed_ids: list of removed plugin IDs
    """
    config = _load_plugins_config()
    plugins = config.get("plugins", [])

    # Separate catalog and non-catalog plugins
    removed_ids = []
    remaining = []

    for plugin in plugins:
        if plugin.get("source") == "catalog":
            removed_ids.append(plugin.get("id", ""))
        else:
            remaining.append(plugin)

    # Update config
    config["plugins"] = remaining
    config["catalog_sync"] = {
        "last_sync_ts": None,
        "synced_plugin_ids": [],
    }

    # Save
    _save_plugins_config(config)

    return {
        "removed": len(removed_ids),
        "removed_ids": removed_ids,
    }


def get_synced_plugins() -> List[SyncedPlugin]:
    """Get all catalog-synced plugins."""
    config = _load_plugins_config()
    plugins = []

    for p in config.get("plugins", []):
        if p.get("source") == "catalog":
            plugins.append(SyncedPlugin.from_dict(p))

    return plugins


def get_all_plugins() -> List[dict]:
    """Get all plugins (both catalog and manual)."""
    config = _load_plugins_config()
    return config.get("plugins", [])
