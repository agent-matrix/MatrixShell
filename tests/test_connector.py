"""Tests for the plugin connector module."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests as requests_module

from matrixsh.plugins.connector import (
    ToolInfo,
    ToolCallResult,
    MCPClientError,
    StreamableHTTPMCPClient,
    HTTPMCPClient,
    StdioMCPClient,
    PluginConnector,
)
from matrixsh.plugins.models import Plugin, TransportType


class TestToolInfo:
    """Tests for ToolInfo."""

    def test_full_name_with_namespace(self):
        """Test full name includes namespace."""
        tool = ToolInfo(name="search", namespace="github")
        assert tool.full_name == "github.search"

    def test_full_name_without_namespace(self):
        """Test full name without namespace."""
        tool = ToolInfo(name="search")
        assert tool.full_name == "search"


class TestToolCallResult:
    """Tests for ToolCallResult."""

    def test_success_result(self):
        """Test successful result."""
        result = ToolCallResult(success=True, result="done")
        assert result.success is True
        assert result.result == "done"
        assert result.error is None

    def test_error_result(self):
        """Test error result."""
        result = ToolCallResult(success=False, error="failed")
        assert result.success is False
        assert result.error == "failed"


class TestStreamableHTTPMCPClient:
    """Tests for StreamableHTTPMCPClient."""

    def test_init(self):
        """Test client initialization."""
        client = StreamableHTTPMCPClient(
            url="http://localhost:4444/mcp",
            headers={"Authorization": "Bearer token"},
            timeout_s=60.0,
        )
        assert client.url == "http://localhost:4444/mcp"
        assert client.timeout_s == 60.0
        assert "Authorization" in client.headers
        assert client.headers["Content-Type"] == "application/json"

    def test_next_id(self):
        """Test request ID incrementing."""
        client = StreamableHTTPMCPClient("http://localhost/mcp")
        assert client._next_id() == 1
        assert client._next_id() == 2
        assert client._next_id() == 3

    @patch("requests.post")
    def test_connect_success(self, mock_post):
        """Test successful connection."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "test-server", "version": "1.0"},
                "capabilities": {},
            },
        }
        mock_post.return_value = mock_response

        client = StreamableHTTPMCPClient("http://localhost/mcp")
        result = client.connect()

        assert result is True
        assert client.is_connected is True
        assert client.server_info["name"] == "test-server"

    @patch("requests.post")
    def test_connect_auth_failure(self, mock_post):
        """Test connection failure due to auth."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("401")
        mock_post.return_value = mock_response

        client = StreamableHTTPMCPClient("http://localhost/mcp")
        with pytest.raises(MCPClientError, match="Authentication failed"):
            client.connect()

    @patch("requests.post")
    def test_list_tools(self, mock_post):
        """Test listing tools."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {"name": "search", "description": "Search items", "inputSchema": {}},
                    {"name": "create", "description": "Create item", "inputSchema": {}},
                ]
            },
        }
        mock_post.return_value = mock_response

        client = StreamableHTTPMCPClient("http://localhost/mcp")
        client._connected = True
        tools = client.list_tools()

        assert len(tools) == 2
        assert tools[0].name == "search"
        assert tools[1].name == "create"

    @patch("requests.post")
    def test_call_tool_success(self, mock_post):
        """Test successful tool call."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {"type": "text", "text": "Search completed successfully"}
                ]
            },
        }
        mock_post.return_value = mock_response

        client = StreamableHTTPMCPClient("http://localhost/mcp")
        client._connected = True
        result = client.call_tool("search", {"query": "test"})

        assert result.success is True
        assert "Search completed" in result.result

    @patch("requests.post")
    def test_call_tool_jsonrpc_error(self, mock_post):
        """Test tool call with JSON-RPC error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32600,
                "message": "Invalid request",
            },
        }
        mock_post.return_value = mock_response

        client = StreamableHTTPMCPClient("http://localhost/mcp")
        client._connected = True
        result = client.call_tool("invalid", {})

        assert result.success is False
        assert "MCP error" in result.error

    @patch("requests.post")
    def test_timeout_handling(self, mock_post):
        """Test timeout error handling."""
        mock_post.side_effect = requests_module.exceptions.Timeout()

        client = StreamableHTTPMCPClient("http://localhost/mcp", timeout_s=5)
        with pytest.raises(MCPClientError, match="timeout"):
            client._send_jsonrpc("test", {})

    @patch("requests.post")
    def test_connection_error_handling(self, mock_post):
        """Test connection error handling."""
        mock_post.side_effect = requests_module.exceptions.ConnectionError()

        client = StreamableHTTPMCPClient("http://localhost/mcp")
        with pytest.raises(MCPClientError, match="Cannot connect"):
            client._send_jsonrpc("test", {})

    def test_disconnect(self):
        """Test disconnect."""
        client = StreamableHTTPMCPClient("http://localhost/mcp")
        client._connected = True
        client._tools = [ToolInfo(name="test")]

        client.disconnect()

        assert client.is_connected is False
        assert client._tools == []


class TestHTTPMCPClient:
    """Tests for legacy HTTPMCPClient."""

    def test_init(self):
        """Test client initialization."""
        client = HTTPMCPClient(
            url="http://localhost:8080",
            headers={"X-API-Key": "secret"},
            timeout_s=45.0,
        )
        assert client.url == "http://localhost:8080"
        assert client.headers == {"X-API-Key": "secret"}
        assert client.timeout_s == 45.0

    @patch("requests.post")
    def test_connect_success(self, mock_post):
        """Test successful connection via /tools/list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = HTTPMCPClient("http://localhost:8080")
        result = client.connect()

        assert result is True
        assert client.is_connected is True
        mock_post.assert_called_with(
            "http://localhost:8080/tools/list",
            json={},
            headers={},
            timeout=30.0,
        )


class TestPluginConnector:
    """Tests for PluginConnector."""

    def test_connect_stdio(self):
        """Test connecting to stdio plugin."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport=TransportType.STDIO,
            command=["python", "-m", "test_server"],
        )
        connector = PluginConnector(plugin)

        # We won't actually connect, just verify the client type
        with patch.object(StdioMCPClient, 'connect', return_value=True):
            with patch.object(StdioMCPClient, 'list_tools', return_value=[]):
                connector.connect()
                assert isinstance(connector._client, StdioMCPClient)

    def test_connect_streamable_http(self):
        """Test connecting to streamable-http plugin."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport=TransportType.STREAMABLE_HTTP,
            url="http://localhost:4444/mcp",
            headers={"Authorization": "Bearer token"},
            timeout_s=60.0,
        )
        connector = PluginConnector(plugin)

        with patch.object(StreamableHTTPMCPClient, 'connect', return_value=True):
            with patch.object(StreamableHTTPMCPClient, 'list_tools', return_value=[]):
                connector.connect()
                assert isinstance(connector._client, StreamableHTTPMCPClient)
                assert connector._client.headers["Authorization"] == "Bearer token"

    def test_connect_legacy_http(self):
        """Test connecting to legacy http plugin."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport=TransportType.HTTP,
            url="http://localhost:8080",
        )
        connector = PluginConnector(plugin)

        with patch.object(HTTPMCPClient, 'connect', return_value=True):
            with patch.object(HTTPMCPClient, 'list_tools', return_value=[]):
                connector.connect()
                assert isinstance(connector._client, HTTPMCPClient)

    def test_connect_missing_command(self):
        """Test error when stdio plugin missing command."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport=TransportType.STDIO,
            command=[],  # Empty command
        )
        connector = PluginConnector(plugin)

        result = connector.connect()
        assert result is False
        assert "No command" in plugin.error

    def test_connect_missing_url(self):
        """Test error when http plugin missing URL."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport=TransportType.STREAMABLE_HTTP,
            url=None,
        )
        connector = PluginConnector(plugin)

        result = connector.connect()
        assert result is False
        assert "No URL" in plugin.error

    def test_tool_filtering(self):
        """Test that tool allow/deny lists are respected."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport=TransportType.STREAMABLE_HTTP,
            url="http://localhost/mcp",
            allow_tools=["search"],  # Only allow search
        )
        connector = PluginConnector(plugin)

        mock_tools = [
            ToolInfo(name="search", description="Search"),
            ToolInfo(name="delete", description="Delete"),  # Not allowed
        ]

        with patch.object(StreamableHTTPMCPClient, 'connect', return_value=True):
            with patch.object(StreamableHTTPMCPClient, 'list_tools', return_value=mock_tools):
                connector.connect()
                # Only 'search' should be in available tools
                assert len(connector._tools) == 1
                assert connector._tools[0].name == "search"

    def test_call_tool_not_connected(self):
        """Test calling tool when not connected."""
        plugin = Plugin(id="test", name="Test")
        connector = PluginConnector(plugin)

        result = connector.call_tool("test", {})
        assert result.success is False
        assert "Not connected" in result.error

    def test_call_tool_not_allowed(self):
        """Test calling disallowed tool."""
        plugin = Plugin(
            id="test",
            name="Test",
            transport=TransportType.STREAMABLE_HTTP,
            url="http://localhost/mcp",
            deny_tools=["dangerous"],
        )
        connector = PluginConnector(plugin)

        # Fake connection
        connector._client = MagicMock()
        connector._client.is_connected = True

        result = connector.call_tool("dangerous", {})
        assert result.success is False
        assert "not allowed" in result.error
