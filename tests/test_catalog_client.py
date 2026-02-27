"""Tests for the catalog client module."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from matrixsh.catalog.client import (
    CatalogConfig,
    CatalogServer,
    CatalogTool,
    CatalogClient,
    CatalogError,
)


class TestCatalogConfig:
    """Tests for CatalogConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CatalogConfig()
        assert config.url == ""
        assert config.token == ""
        assert config.sync_mode == "streamable-http"
        assert config.namespace == "catalog"
        assert config.enabled is False

    def test_to_dict(self):
        """Test serialization to dictionary."""
        config = CatalogConfig(
            url="http://localhost:4444",
            token="test-token",
            enabled=True,
        )
        data = config.to_dict()
        assert data["url"] == "http://localhost:4444"
        assert data["token"] == "test-token"
        assert data["enabled"] is True

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "url": "http://example.com",
            "token": "my-token",
            "sync_mode": "stdio",
            "namespace": "custom",
            "enabled": True,
        }
        config = CatalogConfig.from_dict(data)
        assert config.url == "http://example.com"
        assert config.token == "my-token"
        assert config.sync_mode == "stdio"
        assert config.namespace == "custom"
        assert config.enabled is True

    def test_is_configured(self):
        """Test is_configured method."""
        # Not configured
        config = CatalogConfig()
        assert config.is_configured() is False

        # Partially configured
        config.url = "http://localhost"
        assert config.is_configured() is False

        # Fully configured
        config.token = "token"
        config.enabled = True
        assert config.is_configured() is True

    def test_save_and_load(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "catalog.json"

            config = CatalogConfig(
                url="http://localhost:4444",
                token="test-token",
                enabled=True,
            )
            config.save(path)

            loaded = CatalogConfig.load(path)
            assert loaded.url == config.url
            assert loaded.token == config.token
            assert loaded.enabled == config.enabled


class TestCatalogServer:
    """Tests for CatalogServer."""

    def test_from_api(self):
        """Test creating server from API response."""
        data = {
            "id": "github",
            "name": "GitHub MCP",
            "active": True,
            "description": "GitHub integration",
        }
        server = CatalogServer.from_api(data, "http://localhost:4444")

        assert server.id == "github"
        assert server.name == "GitHub MCP"
        assert server.active is True
        assert server.description == "GitHub integration"
        assert server.mcp_url == "http://localhost:4444/servers/github/mcp"

    def test_from_api_alternate_keys(self):
        """Test handling alternate key names."""
        data = {
            "server_id": "slack",
            "server_name": "Slack MCP",
            "is_active": False,
        }
        server = CatalogServer.from_api(data, "http://localhost:4444")

        assert server.id == "slack"
        assert server.name == "Slack MCP"
        assert server.active is False


class TestCatalogTool:
    """Tests for CatalogTool."""

    def test_from_api(self):
        """Test creating tool from API response."""
        data = {
            "name": "search_issues",
            "description": "Search GitHub issues",
        }
        tool = CatalogTool.from_api(data, "github", "GitHub MCP")

        assert tool.tool == "search_issues"
        assert tool.description == "Search GitHub issues"
        assert tool.server_id == "github"
        assert tool.server_name == "GitHub MCP"


class TestCatalogClient:
    """Tests for CatalogClient."""

    def test_init_with_config(self):
        """Test initializing client with config."""
        config = CatalogConfig(
            url="http://localhost:4444",
            token="test-token",
            enabled=True,
        )
        client = CatalogClient(config)
        assert client.config.url == "http://localhost:4444"

    @patch("matrixsh.catalog.client.requests.Session")
    def test_login_success(self, mock_session_class):
        """Test successful login."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"servers": []}
        mock_response.content = b'{"servers": []}'
        mock_session.request.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "catalog.json"
            config = CatalogConfig()
            client = CatalogClient(config)

            with patch.object(client.config, 'save', return_value=config_path):
                result = client.login("http://localhost:4444", "test-token")

            assert result is True
            assert client.config.url == "http://localhost:4444"
            assert client.config.token == "test-token"
            assert client.config.enabled is True

    @patch("matrixsh.catalog.client.requests.Session")
    def test_login_failure(self, mock_session_class):
        """Test failed login."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_session.request.side_effect = Exception("Connection refused")

        config = CatalogConfig()
        client = CatalogClient(config)
        result = client.login("http://localhost:4444", "bad-token")

        assert result is False
        assert client.config.enabled is False

    def test_logout(self):
        """Test logout clears token and disables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "catalog.json"
            config = CatalogConfig(
                url="http://localhost:4444",
                token="test-token",
                enabled=True,
            )
            client = CatalogClient(config)

            with patch.object(client.config, 'save', return_value=config_path):
                client.logout()

            assert client.config.token == ""
            assert client.config.enabled is False

    @patch("matrixsh.catalog.client.requests.Session")
    def test_list_servers(self, mock_session_class):
        """Test listing servers."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "servers": [
                {"id": "github", "name": "GitHub", "active": True},
                {"id": "slack", "name": "Slack", "active": False},
            ]
        }
        mock_response.content = b'...'
        mock_session.request.return_value = mock_response

        config = CatalogConfig(url="http://localhost:4444", token="token", enabled=True)
        client = CatalogClient(config)

        servers = client.list_servers()
        assert len(servers) == 2
        assert servers[0].id == "github"
        assert servers[1].id == "slack"

        # Test active_only filter
        active_servers = client.list_servers(active_only=True)
        assert len(active_servers) == 1
        assert active_servers[0].id == "github"

    def test_request_without_url(self):
        """Test request fails without URL configured."""
        config = CatalogConfig()
        client = CatalogClient(config)

        with pytest.raises(CatalogError, match="not configured"):
            client._request("GET", "/servers")
