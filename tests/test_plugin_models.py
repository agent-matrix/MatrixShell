"""Tests for the plugin models module."""

import json
import pytest
from pathlib import Path
import tempfile

from matrixsh.plugins.models import (
    PermissionLevel,
    TransportType,
    PluginPermissions,
    Plugin,
    AgentProfile,
    PluginConfig,
)


class TestTransportType:
    """Tests for TransportType enum."""

    def test_values(self):
        """Test enum values."""
        assert TransportType.STDIO.value == "stdio"
        assert TransportType.HTTP.value == "http"
        assert TransportType.STREAMABLE_HTTP.value == "streamable-http"


class TestPluginPermissions:
    """Tests for PluginPermissions."""

    def test_default_values(self):
        """Test default permission values."""
        perms = PluginPermissions()
        assert perms.level == PermissionLevel.READ
        assert perms.requires_confirmation is True
        assert perms.max_calls_per_minute == 60

    def test_to_dict(self):
        """Test serialization."""
        perms = PluginPermissions(
            level=PermissionLevel.WRITE,
            requires_confirmation=False,
            max_calls_per_minute=100,
        )
        data = perms.to_dict()
        assert data["level"] == "write"
        assert data["requires_confirmation"] is False
        assert data["max_calls_per_minute"] == 100

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "level": "admin",
            "requires_confirmation": False,
            "max_calls_per_minute": 1000,
        }
        perms = PluginPermissions.from_dict(data)
        assert perms.level == PermissionLevel.ADMIN
        assert perms.requires_confirmation is False


class TestPlugin:
    """Tests for Plugin model."""

    def test_default_values(self):
        """Test default plugin values."""
        plugin = Plugin(id="test", name="Test Plugin")
        assert plugin.enabled is True
        assert plugin.transport == TransportType.STDIO
        assert plugin.namespace == "test"  # Defaults to id
        assert plugin.source == "manual"
        assert plugin.headers == {}
        assert plugin.timeout_s == 30.0

    def test_new_fields(self):
        """Test new fields (headers, timeout_s, source, catalog_server_id)."""
        plugin = Plugin(
            id="github",
            name="GitHub",
            transport=TransportType.STREAMABLE_HTTP,
            url="http://localhost/mcp",
            headers={"Authorization": "Bearer token"},
            timeout_s=60.0,
            source="catalog",
            catalog_server_id="github-server-123",
        )
        assert plugin.headers == {"Authorization": "Bearer token"}
        assert plugin.timeout_s == 60.0
        assert plugin.source == "catalog"
        assert plugin.catalog_server_id == "github-server-123"

    def test_to_dict(self):
        """Test serialization."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport=TransportType.STREAMABLE_HTTP,
            url="http://localhost/mcp",
            headers={"Authorization": "Bearer xyz"},
            timeout_s=45.0,
            source="catalog",
            catalog_server_id="test-123",
        )
        data = plugin.to_dict()

        assert data["id"] == "test"
        assert data["transport"] == "streamable-http"
        assert data["headers"] == {"Authorization": "Bearer xyz"}
        assert data["timeout_s"] == 45.0
        assert data["source"] == "catalog"
        assert data["catalog_server_id"] == "test-123"

    def test_to_dict_without_catalog_server_id(self):
        """Test serialization without catalog_server_id."""
        plugin = Plugin(id="test", name="Test")
        data = plugin.to_dict()

        assert "catalog_server_id" not in data

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "id": "github",
            "name": "GitHub",
            "enabled": True,
            "transport": "streamable-http",
            "url": "http://localhost/mcp",
            "headers": {"Authorization": "Bearer token"},
            "timeout_s": 60.0,
            "namespace": "gh",
            "source": "catalog",
            "catalog_server_id": "gh-123",
        }
        plugin = Plugin.from_dict(data)

        assert plugin.id == "github"
        assert plugin.transport == TransportType.STREAMABLE_HTTP
        assert plugin.headers == {"Authorization": "Bearer token"}
        assert plugin.timeout_s == 60.0
        assert plugin.source == "catalog"
        assert plugin.catalog_server_id == "gh-123"

    def test_from_dict_defaults(self):
        """Test deserialization with defaults."""
        data = {"id": "minimal"}
        plugin = Plugin.from_dict(data)

        assert plugin.name == "minimal"  # Defaults to id
        assert plugin.transport == TransportType.STDIO
        assert plugin.headers == {}
        assert plugin.timeout_s == 30.0
        assert plugin.source == "manual"
        assert plugin.catalog_server_id is None

    def test_transport_string_conversion(self):
        """Test transport string is converted to enum."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport="streamable-http",  # String instead of enum
        )
        assert plugin.transport == TransportType.STREAMABLE_HTTP

    def test_permissions_dict_conversion(self):
        """Test permissions dict is converted to object."""
        plugin = Plugin(
            id="test",
            name="Test",
            permissions={"level": "write", "requires_confirmation": False},
        )
        assert isinstance(plugin.permissions, PluginPermissions)
        assert plugin.permissions.level == PermissionLevel.WRITE

    def test_is_tool_allowed(self):
        """Test tool allow/deny logic."""
        plugin = Plugin(
            id="test",
            name="Test",
            allow_tools=["search", "list"],
            deny_tools=["delete"],
        )

        assert plugin.is_tool_allowed("search") is True
        assert plugin.is_tool_allowed("list") is True
        assert plugin.is_tool_allowed("delete") is False  # Deny takes precedence
        assert plugin.is_tool_allowed("unknown") is False  # Not in allow list

    def test_is_tool_allowed_empty_lists(self):
        """Test tool allowed when lists are empty."""
        plugin = Plugin(id="test", name="Test")

        assert plugin.is_tool_allowed("anything") is True

    def test_is_tool_allowed_deny_only(self):
        """Test deny list without allow list."""
        plugin = Plugin(
            id="test",
            name="Test",
            deny_tools=["dangerous"],
        )

        assert plugin.is_tool_allowed("safe") is True
        assert plugin.is_tool_allowed("dangerous") is False


class TestAgentProfile:
    """Tests for AgentProfile."""

    def test_default_values(self):
        """Test default values."""
        profile = AgentProfile(id="default", name="Default")
        assert profile.max_steps == 50
        assert profile.requires_confirmation is True

    def test_to_dict(self):
        """Test serialization."""
        profile = AgentProfile(
            id="custom",
            name="Custom Agent",
            allowed_namespaces=["github", "slack"],
            max_steps=100,
        )
        data = profile.to_dict()

        assert data["id"] == "custom"
        assert data["allowed_namespaces"] == ["github", "slack"]
        assert data["max_steps"] == 100

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "id": "test",
            "name": "Test Agent",
            "denied_namespaces": ["dangerous"],
            "max_steps": 25,
        }
        profile = AgentProfile.from_dict(data)

        assert profile.id == "test"
        assert profile.denied_namespaces == ["dangerous"]
        assert profile.max_steps == 25


class TestPluginConfig:
    """Tests for PluginConfig."""

    def test_default_values(self):
        """Test default config."""
        config = PluginConfig()
        assert config.plugins == []
        assert config.agents == []

    def test_add_plugin(self):
        """Test adding plugin."""
        config = PluginConfig()
        plugin = Plugin(id="test", name="Test")
        config.add_plugin(plugin)

        assert len(config.plugins) == 1
        assert config.plugins[0].id == "test"

    def test_add_plugin_update(self):
        """Test updating existing plugin."""
        config = PluginConfig()
        config.add_plugin(Plugin(id="test", name="Old Name"))
        config.add_plugin(Plugin(id="test", name="New Name"))

        assert len(config.plugins) == 1
        assert config.plugins[0].name == "New Name"

    def test_get_plugin(self):
        """Test getting plugin by ID."""
        config = PluginConfig()
        config.add_plugin(Plugin(id="test", name="Test"))

        assert config.get_plugin("test") is not None
        assert config.get_plugin("nonexistent") is None

    def test_remove_plugin(self):
        """Test removing plugin."""
        config = PluginConfig()
        config.add_plugin(Plugin(id="test", name="Test"))

        assert config.remove_plugin("test") is True
        assert len(config.plugins) == 0
        assert config.remove_plugin("nonexistent") is False

    def test_get_enabled_plugins(self):
        """Test getting enabled plugins."""
        config = PluginConfig()
        config.add_plugin(Plugin(id="enabled", name="Enabled", enabled=True))
        config.add_plugin(Plugin(id="disabled", name="Disabled", enabled=False))

        enabled = config.get_enabled_plugins()
        assert len(enabled) == 1
        assert enabled[0].id == "enabled"

    def test_save_and_load(self):
        """Test saving and loading config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plugins.json"

            config = PluginConfig()
            config.add_plugin(Plugin(
                id="test",
                name="Test",
                transport=TransportType.STREAMABLE_HTTP,
                url="http://localhost/mcp",
                headers={"Authorization": "Bearer token"},
                source="catalog",
            ))
            config.save(path)

            loaded = PluginConfig.load(path)
            assert len(loaded.plugins) == 1
            plugin = loaded.plugins[0]
            assert plugin.id == "test"
            assert plugin.transport == TransportType.STREAMABLE_HTTP
            assert plugin.headers == {"Authorization": "Bearer token"}
            assert plugin.source == "catalog"

    def test_to_dict(self):
        """Test serialization."""
        config = PluginConfig()
        config.add_plugin(Plugin(id="p1", name="Plugin 1"))
        config.agents.append(AgentProfile(id="a1", name="Agent 1"))

        data = config.to_dict()
        assert len(data["plugins"]) == 1
        assert len(data["agents"]) == 1

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "plugins": [{"id": "p1", "name": "Plugin 1"}],
            "agents": [{"id": "a1", "name": "Agent 1"}],
        }
        config = PluginConfig.from_dict(data)

        assert len(config.plugins) == 1
        assert len(config.agents) == 1
