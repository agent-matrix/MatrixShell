"""Tests for the catalog sync module."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from matrixsh.catalog.sync import (
    SyncStatus,
    SyncedPlugin,
    sync_catalog,
    unsync_catalog,
    get_sync_status,
    get_all_plugins,
)
from matrixsh.catalog.client import CatalogServer, CatalogConfig, CatalogClient


class TestSyncStatus:
    """Tests for SyncStatus."""

    def test_default_values(self):
        """Test default status values."""
        status = SyncStatus()
        assert status.last_sync_ts is None
        assert status.synced_plugin_ids == []

    def test_to_dict(self):
        """Test serialization."""
        status = SyncStatus(
            last_sync_ts="2024-01-01T00:00:00Z",
            synced_plugin_ids=["catalog-github", "catalog-slack"],
        )
        data = status.to_dict()
        assert data["last_sync_ts"] == "2024-01-01T00:00:00Z"
        assert data["synced_plugin_ids"] == ["catalog-github", "catalog-slack"]

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "last_sync_ts": "2024-01-01T00:00:00Z",
            "synced_plugin_ids": ["p1", "p2"],
        }
        status = SyncStatus.from_dict(data)
        assert status.last_sync_ts == "2024-01-01T00:00:00Z"
        assert status.synced_plugin_ids == ["p1", "p2"]


class TestSyncedPlugin:
    """Tests for SyncedPlugin."""

    def test_from_server_basic(self):
        """Test creating plugin from server."""
        server = CatalogServer(
            id="github",
            name="GitHub MCP",
            active=True,
            mcp_url="http://localhost:4444/servers/github/mcp",
        )
        plugin = SyncedPlugin.from_server(server, "catalog")

        assert plugin.id == "catalog-github"
        assert plugin.name == "GitHub MCP"
        assert plugin.enabled is True
        assert plugin.tool_namespace == "catalog.github_mcp"
        assert plugin.transport == "streamable-http"
        assert plugin.url == "http://localhost:4444/servers/github/mcp"
        assert plugin.source == "catalog"
        assert plugin.catalog_server_id == "github"

    def test_from_server_with_auth(self):
        """Test creating plugin with auth token."""
        server = CatalogServer(
            id="slack",
            name="Slack Integration",
            active=True,
            mcp_url="http://localhost:4444/servers/slack/mcp",
        )
        plugin = SyncedPlugin.from_server(server, "ext", auth_token="my-jwt-token")

        assert plugin.headers == {"Authorization": "Bearer my-jwt-token"}
        assert plugin.tool_namespace == "ext.slack_integration"

    def test_from_server_with_bearer_prefix(self):
        """Test auth token already has Bearer prefix."""
        server = CatalogServer(
            id="test",
            name="Test",
            active=True,
            mcp_url="http://localhost/mcp",
        )
        plugin = SyncedPlugin.from_server(server, "", auth_token="Bearer existing")

        assert plugin.headers == {"Authorization": "Bearer existing"}

    def test_from_server_empty_namespace(self):
        """Test creating plugin with empty namespace prefix."""
        server = CatalogServer(
            id="github",
            name="GitHub",
            active=True,
            mcp_url="http://localhost/mcp",
        )
        plugin = SyncedPlugin.from_server(server, "")

        assert plugin.tool_namespace == "github"

    def test_to_dict(self):
        """Test serialization to dict for plugins.json."""
        plugin = SyncedPlugin(
            id="catalog-github",
            name="GitHub",
            enabled=True,
            tool_namespace="catalog.github",
            transport="streamable-http",
            url="http://localhost/mcp",
            headers={"Authorization": "Bearer token"},
            timeout_s=30.0,
            source="catalog",
            catalog_server_id="github",
        )
        data = plugin.to_dict()

        assert data["id"] == "catalog-github"
        assert data["namespace"] == "catalog.github"  # Uses 'namespace' key
        assert data["transport"] == "streamable-http"
        assert data["headers"] == {"Authorization": "Bearer token"}
        assert data["timeout_s"] == 30.0
        assert data["source"] == "catalog"

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "id": "catalog-slack",
            "name": "Slack",
            "enabled": True,
            "namespace": "ext.slack",
            "transport": "streamable-http",
            "url": "http://localhost/mcp",
            "headers": {"Authorization": "Bearer xyz"},
            "timeout_s": 60.0,
            "source": "catalog",
            "catalog_server_id": "slack",
        }
        plugin = SyncedPlugin.from_dict(data)

        assert plugin.id == "catalog-slack"
        assert plugin.tool_namespace == "ext.slack"
        assert plugin.headers == {"Authorization": "Bearer xyz"}
        assert plugin.timeout_s == 60.0


class TestSyncCatalog:
    """Tests for sync_catalog function."""

    @patch("matrixsh.catalog.sync._save_plugins_config")
    @patch("matrixsh.catalog.sync._load_plugins_config")
    def test_sync_adds_new_plugins(self, mock_load, mock_save):
        """Test sync adds new plugins from catalog."""
        mock_load.return_value = {"plugins": [], "catalog_sync": {}}

        # Create mock client
        mock_client = MagicMock(spec=CatalogClient)
        mock_client.config = CatalogConfig(
            url="http://localhost:4444",
            token="test-token",
            namespace="catalog",
            enabled=True,
        )
        mock_client.list_servers.return_value = [
            CatalogServer(
                id="github",
                name="GitHub",
                active=True,
                mcp_url="http://localhost:4444/servers/github/mcp",
            ),
        ]

        result = sync_catalog(mock_client)

        assert result["added"] == 1
        assert result["updated"] == 0
        assert result["removed"] == 0
        assert "catalog-github" in result["synced"]

        # Check the saved data
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["plugins"]) == 1
        assert saved_data["plugins"][0]["transport"] == "streamable-http"
        assert saved_data["plugins"][0]["headers"]["Authorization"] == "Bearer test-token"

    @patch("matrixsh.catalog.sync._save_plugins_config")
    @patch("matrixsh.catalog.sync._load_plugins_config")
    def test_sync_updates_existing_plugins(self, mock_load, mock_save):
        """Test sync updates existing catalog plugins."""
        mock_load.return_value = {
            "plugins": [
                {
                    "id": "catalog-github",
                    "name": "Old Name",
                    "enabled": True,
                    "namespace": "catalog.github",
                    "transport": "http",  # Old transport
                    "url": "http://old-url/mcp",
                    "source": "catalog",
                    "allow_tools": ["specific_tool"],  # Should be preserved
                }
            ],
            "catalog_sync": {"synced_plugin_ids": ["catalog-github"]},
        }

        mock_client = MagicMock(spec=CatalogClient)
        mock_client.config = CatalogConfig(
            url="http://localhost:4444",
            token="new-token",
            namespace="catalog",
            enabled=True,
        )
        mock_client.list_servers.return_value = [
            CatalogServer(
                id="github",
                name="GitHub Updated",
                active=True,
                mcp_url="http://localhost:4444/servers/github/mcp",
            ),
        ]

        result = sync_catalog(mock_client)

        assert result["added"] == 0
        assert result["updated"] == 1

        saved_data = mock_save.call_args[0][0]
        plugin = saved_data["plugins"][0]
        assert plugin["transport"] == "streamable-http"  # Updated
        assert plugin["allow_tools"] == ["specific_tool"]  # Preserved

    @patch("matrixsh.catalog.sync._save_plugins_config")
    @patch("matrixsh.catalog.sync._load_plugins_config")
    def test_sync_preserves_manual_plugins(self, mock_load, mock_save):
        """Test sync doesn't remove manual plugins."""
        mock_load.return_value = {
            "plugins": [
                {
                    "id": "manual-custom",
                    "name": "Custom Plugin",
                    "enabled": True,
                    "transport": "stdio",
                    "command": ["python", "server.py"],
                    "source": "manual",
                },
            ],
            "catalog_sync": {},
        }

        mock_client = MagicMock(spec=CatalogClient)
        mock_client.config = CatalogConfig(
            url="http://localhost:4444",
            token="token",
            namespace="catalog",
            enabled=True,
        )
        mock_client.list_servers.return_value = []

        result = sync_catalog(mock_client)

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["plugins"]) == 1
        assert saved_data["plugins"][0]["id"] == "manual-custom"


class TestUnsyncCatalog:
    """Tests for unsync_catalog function."""

    @patch("matrixsh.catalog.sync._save_plugins_config")
    @patch("matrixsh.catalog.sync._load_plugins_config")
    def test_unsync_removes_catalog_plugins(self, mock_load, mock_save):
        """Test unsync removes all catalog-synced plugins."""
        mock_load.return_value = {
            "plugins": [
                {"id": "catalog-github", "source": "catalog"},
                {"id": "catalog-slack", "source": "catalog"},
                {"id": "manual-custom", "source": "manual"},
            ],
            "catalog_sync": {
                "synced_plugin_ids": ["catalog-github", "catalog-slack"],
            },
        }

        result = unsync_catalog()

        assert result["removed"] == 2
        assert "catalog-github" in result["removed_ids"]
        assert "catalog-slack" in result["removed_ids"]

        saved_data = mock_save.call_args[0][0]
        assert len(saved_data["plugins"]) == 1
        assert saved_data["plugins"][0]["id"] == "manual-custom"


class TestGetSyncStatus:
    """Tests for get_sync_status function."""

    @patch("matrixsh.catalog.sync._load_plugins_config")
    def test_get_status_empty(self, mock_load):
        """Test getting status when no sync has occurred."""
        mock_load.return_value = {"plugins": [], "catalog_sync": {}}

        status = get_sync_status()
        assert status.last_sync_ts is None
        assert status.synced_plugin_ids == []

    @patch("matrixsh.catalog.sync._load_plugins_config")
    def test_get_status_with_sync(self, mock_load):
        """Test getting status after sync."""
        mock_load.return_value = {
            "plugins": [],
            "catalog_sync": {
                "last_sync_ts": "2024-01-01T00:00:00Z",
                "synced_plugin_ids": ["p1", "p2"],
            },
        }

        status = get_sync_status()
        assert status.last_sync_ts == "2024-01-01T00:00:00Z"
        assert status.synced_plugin_ids == ["p1", "p2"]


class TestGetAllPlugins:
    """Tests for get_all_plugins function."""

    @patch("matrixsh.catalog.sync._load_plugins_config")
    def test_get_all_plugins(self, mock_load):
        """Test getting all plugins."""
        mock_load.return_value = {
            "plugins": [
                {"id": "p1", "source": "catalog"},
                {"id": "p2", "source": "manual"},
            ],
        }

        plugins = get_all_plugins()
        assert len(plugins) == 2
