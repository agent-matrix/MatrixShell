"""Plugin configuration models and schemas.

Defines the data structures for plugin configuration, permissions,
and the unified tool catalog.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


class PermissionLevel(str, Enum):
    """Permission levels for plugins."""
    READ = "read"           # Read-only operations
    WRITE = "write"         # Can modify state
    ADMIN = "admin"         # Full access (dangerous)


class TransportType(str, Enum):
    """MCP transport types."""
    STDIO = "stdio"                 # Subprocess with stdio
    HTTP = "http"                   # HTTP endpoint
    STREAMABLE_HTTP = "streamable-http"  # Streamable HTTP


@dataclass
class PluginPermissions:
    """Permission settings for a plugin."""
    level: PermissionLevel = PermissionLevel.READ
    requires_confirmation: bool = True
    max_calls_per_minute: int = 60
    allowed_paths: List[str] = field(default_factory=list)  # Empty = all paths
    denied_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "requires_confirmation": self.requires_confirmation,
            "max_calls_per_minute": self.max_calls_per_minute,
            "allowed_paths": self.allowed_paths,
            "denied_paths": self.denied_paths,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PluginPermissions":
        return cls(
            level=PermissionLevel(data.get("level", "read")),
            requires_confirmation=data.get("requires_confirmation", True),
            max_calls_per_minute=data.get("max_calls_per_minute", 60),
            allowed_paths=data.get("allowed_paths", []),
            denied_paths=data.get("denied_paths", []),
        )


@dataclass
class Plugin:
    """Configuration for an external MCP server plugin."""
    id: str                                     # Unique identifier
    name: str                                   # Human-readable name
    enabled: bool = True                        # Is plugin active
    transport: TransportType = TransportType.STDIO

    # For stdio transport
    command: List[str] = field(default_factory=list)  # Command to start server
    env: Dict[str, str] = field(default_factory=dict)  # Environment variables

    # For http/streamable-http transport
    url: Optional[str] = None                   # HTTP endpoint URL
    headers: Dict[str, str] = field(default_factory=dict)  # HTTP headers (auth, etc.)
    timeout_s: float = 30.0                     # Request timeout in seconds

    # Tool configuration
    namespace: str = ""                         # Tool namespace (e.g., "github")
    allow_tools: List[str] = field(default_factory=list)  # Allowlist (empty = all)
    deny_tools: List[str] = field(default_factory=list)   # Denylist

    # Permissions
    permissions: PluginPermissions = field(default_factory=PluginPermissions)

    # Source tracking (for catalog-synced plugins)
    source: Literal["manual", "catalog"] = "manual"
    catalog_server_id: Optional[str] = None     # Original server ID in catalog

    # Runtime state (not persisted)
    connected: bool = field(default=False, repr=False)
    error: Optional[str] = field(default=None, repr=False)
    available_tools: List[str] = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.namespace:
            self.namespace = self.id
        if isinstance(self.transport, str):
            self.transport = TransportType(self.transport)
        if isinstance(self.permissions, dict):
            self.permissions = PluginPermissions.from_dict(self.permissions)

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        data = {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "transport": self.transport.value,
            "command": self.command,
            "env": self.env,
            "url": self.url,
            "headers": self.headers,
            "timeout_s": self.timeout_s,
            "namespace": self.namespace,
            "allow_tools": self.allow_tools,
            "deny_tools": self.deny_tools,
            "permissions": self.permissions.to_dict(),
            "source": self.source,
        }
        # Only include catalog_server_id if set
        if self.catalog_server_id:
            data["catalog_server_id"] = self.catalog_server_id
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Plugin":
        """Deserialize from dictionary."""
        permissions = data.get("permissions", {})
        if isinstance(permissions, dict):
            permissions = PluginPermissions.from_dict(permissions)

        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            enabled=data.get("enabled", True),
            transport=TransportType(data.get("transport", "stdio")),
            command=data.get("command", []),
            env=data.get("env", {}),
            url=data.get("url"),
            headers=data.get("headers", {}),
            timeout_s=data.get("timeout_s", 30.0),
            namespace=data.get("namespace", data["id"]),
            allow_tools=data.get("allow_tools", []),
            deny_tools=data.get("deny_tools", []),
            permissions=permissions,
            source=data.get("source", "manual"),
            catalog_server_id=data.get("catalog_server_id"),
        )

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed based on allow/deny lists."""
        # Deny list takes precedence
        if tool_name in self.deny_tools:
            return False
        # If allow list is empty, allow all (except denied)
        if not self.allow_tools:
            return True
        # Otherwise, must be in allow list
        return tool_name in self.allow_tools


@dataclass
class AgentProfile:
    """Permission profile for an agent."""
    id: str
    name: str
    allowed_namespaces: List[str] = field(default_factory=list)  # Empty = all
    denied_namespaces: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)  # "namespace.tool"
    denied_tools: List[str] = field(default_factory=list)
    max_steps: int = 50
    requires_confirmation: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "allowed_namespaces": self.allowed_namespaces,
            "denied_namespaces": self.denied_namespaces,
            "allowed_tools": self.allowed_tools,
            "denied_tools": self.denied_tools,
            "max_steps": self.max_steps,
            "requires_confirmation": self.requires_confirmation,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentProfile":
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            allowed_namespaces=data.get("allowed_namespaces", []),
            denied_namespaces=data.get("denied_namespaces", []),
            allowed_tools=data.get("allowed_tools", []),
            denied_tools=data.get("denied_tools", []),
            max_steps=data.get("max_steps", 50),
            requires_confirmation=data.get("requires_confirmation", True),
        )


def plugins_config_path() -> Path:
    """Get path to plugins configuration file."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "matrixsh" / "plugins.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "matrixsh" / "plugins.json"


@dataclass
class PluginConfig:
    """Root configuration for all plugins."""
    plugins: List[Plugin] = field(default_factory=list)
    agents: List[AgentProfile] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "plugins": [p.to_dict() for p in self.plugins],
            "agents": [a.to_dict() for a in self.agents],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PluginConfig":
        return cls(
            plugins=[Plugin.from_dict(p) for p in data.get("plugins", [])],
            agents=[AgentProfile.from_dict(a) for a in data.get("agents", [])],
        )

    def save(self, path: Optional[Path] = None) -> Path:
        """Save configuration to file."""
        path = path or plugins_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "PluginConfig":
        """Load configuration from file."""
        path = path or plugins_config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except Exception:
            return cls()

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get plugin by ID."""
        for p in self.plugins:
            if p.id == plugin_id:
                return p
        return None

    def add_plugin(self, plugin: Plugin) -> None:
        """Add or update a plugin."""
        for i, p in enumerate(self.plugins):
            if p.id == plugin.id:
                self.plugins[i] = plugin
                return
        self.plugins.append(plugin)

    def remove_plugin(self, plugin_id: str) -> bool:
        """Remove a plugin by ID."""
        for i, p in enumerate(self.plugins):
            if p.id == plugin_id:
                self.plugins.pop(i)
                return True
        return False

    def get_enabled_plugins(self) -> List[Plugin]:
        """Get all enabled plugins."""
        return [p for p in self.plugins if p.enabled]
