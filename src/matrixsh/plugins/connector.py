"""MCP Client Connector.

Connects to external MCP servers via stdio or HTTP transport.
Provides a unified interface for discovering and calling tools.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Plugin


@dataclass
class ToolInfo:
    """Information about an available tool."""
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    namespace: str = ""

    @property
    def full_name(self) -> str:
        """Get namespaced tool name."""
        if self.namespace:
            return f"{self.namespace}.{self.name}"
        return self.name


@dataclass
class ToolCallResult:
    """Result of a tool call."""
    success: bool
    result: Any = None
    error: Optional[str] = None


class MCPClientError(Exception):
    """Error from MCP client operations."""
    pass


class StdioMCPClient:
    """MCP client that communicates with a server via stdio.

    This is a simplified implementation that works without the full MCP SDK.
    It uses JSON-RPC 2.0 over stdio.
    """

    def __init__(self, command: List[str], env: Optional[Dict[str, str]] = None):
        self.command = command
        self.env = {**os.environ, **(env or {})}
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._tools: List[ToolInfo] = []

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send a JSON-RPC request and get response."""
        if not self.process or self.process.poll() is not None:
            raise MCPClientError("MCP server process not running")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            request["params"] = params

        try:
            # Write request
            request_line = json.dumps(request) + "\n"
            self.process.stdin.write(request_line)
            self.process.stdin.flush()

            # Read response
            response_line = self.process.stdout.readline()
            if not response_line:
                raise MCPClientError("No response from MCP server")

            response = json.loads(response_line)
            if "error" in response:
                raise MCPClientError(f"MCP error: {response['error']}")

            return response.get("result", {})
        except json.JSONDecodeError as e:
            raise MCPClientError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise MCPClientError(f"Communication error: {e}")

    def connect(self) -> bool:
        """Start the MCP server process and initialize."""
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                text=True,
                bufsize=1,
            )

            # Initialize connection
            result = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "matrixsh",
                    "version": "0.1.0"
                }
            })

            # Send initialized notification
            self._send_request("notifications/initialized", {})

            return True
        except Exception as e:
            self.disconnect()
            raise MCPClientError(f"Failed to connect: {e}")

    def disconnect(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None

    def list_tools(self) -> List[ToolInfo]:
        """Get list of available tools from the server."""
        try:
            result = self._send_request("tools/list", {})
            tools = []
            for tool in result.get("tools", []):
                tools.append(ToolInfo(
                    name=tool.get("name", ""),
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {}),
                ))
            self._tools = tools
            return tools
        except Exception as e:
            raise MCPClientError(f"Failed to list tools: {e}")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """Call a tool on the server."""
        try:
            result = self._send_request("tools/call", {
                "name": name,
                "arguments": arguments,
            })

            # Parse content from result
            content = result.get("content", [])
            if content and isinstance(content, list):
                # Get text content
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                return ToolCallResult(success=True, result="\n".join(texts) if texts else content)

            return ToolCallResult(success=True, result=result)
        except MCPClientError as e:
            return ToolCallResult(success=False, error=str(e))
        except Exception as e:
            return ToolCallResult(success=False, error=f"Tool call failed: {e}")

    @property
    def is_connected(self) -> bool:
        return self.process is not None and self.process.poll() is None


class HTTPMCPClient:
    """MCP client that communicates with a server via HTTP (legacy /tools/list API).

    Simplified implementation using requests for non-standard HTTP endpoints.
    """

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None, timeout_s: float = 30.0):
        self.url = url.rstrip("/")
        self.headers = headers or {}
        self.timeout_s = timeout_s
        self._tools: List[ToolInfo] = []
        self._connected = False

    def connect(self) -> bool:
        """Verify connection to the HTTP MCP server."""
        import requests
        try:
            # Try to list tools as a health check
            response = requests.post(
                f"{self.url}/tools/list",
                json={},
                headers=self.headers,
                timeout=self.timeout_s,
            )
            if response.status_code == 200:
                self._connected = True
                return True
            return False
        except Exception:
            return False

    def disconnect(self) -> None:
        """No-op for HTTP client."""
        self._connected = False

    def list_tools(self) -> List[ToolInfo]:
        """Get list of available tools from the server."""
        import requests
        try:
            response = requests.post(
                f"{self.url}/tools/list",
                json={},
                headers=self.headers,
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            result = response.json()
            tools = []
            for tool in result.get("tools", []):
                tools.append(ToolInfo(
                    name=tool.get("name", ""),
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {}),
                ))
            self._tools = tools
            return tools
        except Exception as e:
            raise MCPClientError(f"Failed to list tools: {e}")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """Call a tool on the server."""
        import requests
        try:
            response = requests.post(
                f"{self.url}/tools/call",
                json={"name": name, "arguments": arguments},
                headers=self.headers,
                timeout=max(self.timeout_s, 120),  # Tool calls may take longer
            )
            response.raise_for_status()
            result = response.json()

            content = result.get("content", [])
            if content and isinstance(content, list):
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                return ToolCallResult(success=True, result="\n".join(texts) if texts else content)

            return ToolCallResult(success=True, result=result)
        except Exception as e:
            return ToolCallResult(success=False, error=f"Tool call failed: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected


class StreamableHTTPMCPClient:
    """MCP client that speaks the Streamable HTTP protocol (JSON-RPC over HTTP).

    This is the proper MCP protocol used by ContextForge and other compliant gateways.
    Sends JSON-RPC 2.0 messages to a single MCP endpoint URL.
    """

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None, timeout_s: float = 30.0):
        """Initialize client.

        Args:
            url: MCP endpoint URL (e.g., http://localhost:4444/servers/<id>/mcp)
            headers: HTTP headers including Authorization
            timeout_s: Request timeout in seconds
        """
        self.url = url.rstrip("/")
        self.timeout_s = timeout_s
        self._request_id = 0
        self._tools: List[ToolInfo] = []
        self._connected = False
        self._server_info: Dict[str, Any] = {}

        # Build headers with content-type for JSON-RPC
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **(headers or {}),
        }

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_jsonrpc(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send a JSON-RPC 2.0 request and get the response.

        Args:
            method: MCP method name (e.g., "initialize", "tools/list")
            params: Method parameters

        Returns:
            The 'result' field from the JSON-RPC response

        Raises:
            MCPClientError: On communication or protocol errors
        """
        import requests

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            request["params"] = params

        try:
            response = requests.post(
                self.url,
                json=request,
                headers=self.headers,
                timeout=self.timeout_s,
            )

            # Handle HTTP errors
            if response.status_code == 401:
                raise MCPClientError("Authentication failed - check your token")
            if response.status_code == 403:
                raise MCPClientError("Access denied - insufficient permissions")
            if response.status_code == 404:
                raise MCPClientError(f"MCP endpoint not found: {self.url}")

            response.raise_for_status()

            # Parse JSON-RPC response
            result = response.json()

            # Handle JSON-RPC error
            if "error" in result:
                error = result["error"]
                msg = error.get("message", str(error))
                code = error.get("code", "")
                raise MCPClientError(f"MCP error ({code}): {msg}")

            return result.get("result", {})

        except requests.exceptions.Timeout:
            raise MCPClientError(f"Request timeout after {self.timeout_s}s")
        except requests.exceptions.ConnectionError:
            raise MCPClientError(f"Cannot connect to {self.url}")
        except requests.exceptions.HTTPError as e:
            raise MCPClientError(f"HTTP error: {e}")
        except json.JSONDecodeError:
            raise MCPClientError("Invalid JSON response from server")

    def connect(self) -> bool:
        """Initialize connection with MCP handshake.

        Performs the MCP initialize/initialized handshake.

        Returns:
            True if connected successfully

        Raises:
            MCPClientError: On connection failure
        """
        try:
            # Step 1: Send initialize request
            result = self._send_jsonrpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "clientInfo": {
                    "name": "matrixsh",
                    "version": "0.1.0",
                },
            })

            self._server_info = result.get("serverInfo", {})

            # Step 2: Send initialized notification (no response expected, but we send it)
            # Some servers expect this, others don't - we do it for compliance
            try:
                notify_req = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                }
                import requests
                requests.post(
                    self.url,
                    json=notify_req,
                    headers=self.headers,
                    timeout=5,
                )
            except Exception:
                pass  # Notification failures are OK

            self._connected = True
            return True

        except MCPClientError:
            self._connected = False
            raise
        except Exception as e:
            self._connected = False
            raise MCPClientError(f"Failed to connect: {e}")

    def disconnect(self) -> None:
        """Disconnect from the server."""
        self._connected = False
        self._tools = []

    def list_tools(self) -> List[ToolInfo]:
        """Get list of available tools from the server.

        Returns:
            List of ToolInfo objects

        Raises:
            MCPClientError: On failure
        """
        try:
            result = self._send_jsonrpc("tools/list", {})
            tools = []
            for tool in result.get("tools", []):
                tools.append(ToolInfo(
                    name=tool.get("name", ""),
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {}),
                ))
            self._tools = tools
            return tools
        except MCPClientError:
            raise
        except Exception as e:
            raise MCPClientError(f"Failed to list tools: {e}")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """Call a tool on the server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            ToolCallResult with success status and result/error
        """
        # Use longer timeout for tool calls
        original_timeout = self.timeout_s
        try:
            self.timeout_s = max(self.timeout_s, 120)  # At least 2 minutes for tool calls

            result = self._send_jsonrpc("tools/call", {
                "name": name,
                "arguments": arguments,
            })

            # Parse content from MCP result
            content = result.get("content", [])
            if content and isinstance(content, list):
                # Extract text content
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                if texts:
                    return ToolCallResult(success=True, result="\n".join(texts))
                # Return raw content if no text
                return ToolCallResult(success=True, result=content)

            # Handle isError flag
            if result.get("isError"):
                return ToolCallResult(success=False, error=str(result))

            return ToolCallResult(success=True, result=result)

        except MCPClientError as e:
            return ToolCallResult(success=False, error=str(e))
        except Exception as e:
            return ToolCallResult(success=False, error=f"Tool call failed: {e}")
        finally:
            self.timeout_s = original_timeout

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def server_info(self) -> Dict[str, Any]:
        """Get server information from initialization."""
        return self._server_info


class PluginConnector:
    """Manages connection to a plugin's MCP server."""

    def __init__(self, plugin: "Plugin"):
        self.plugin = plugin
        self._client: Optional[StdioMCPClient | HTTPMCPClient | StreamableHTTPMCPClient] = None
        self._tools: List[ToolInfo] = []

    def connect(self) -> bool:
        """Connect to the plugin's MCP server."""
        from .models import TransportType

        try:
            if self.plugin.transport == TransportType.STDIO:
                if not self.plugin.command:
                    self.plugin.error = "No command specified for stdio transport"
                    return False
                self._client = StdioMCPClient(self.plugin.command, self.plugin.env)

            elif self.plugin.transport == TransportType.STREAMABLE_HTTP:
                # Proper MCP Streamable HTTP (JSON-RPC over HTTP)
                if not self.plugin.url:
                    self.plugin.error = "No URL specified for streamable-http transport"
                    return False
                self._client = StreamableHTTPMCPClient(
                    url=self.plugin.url,
                    headers=self.plugin.headers,
                    timeout_s=self.plugin.timeout_s,
                )

            elif self.plugin.transport == TransportType.HTTP:
                # Legacy HTTP with /tools/list endpoints
                if not self.plugin.url:
                    self.plugin.error = "No URL specified for HTTP transport"
                    return False
                self._client = HTTPMCPClient(
                    url=self.plugin.url,
                    headers=self.plugin.headers,
                    timeout_s=self.plugin.timeout_s,
                )

            else:
                self.plugin.error = f"Unknown transport: {self.plugin.transport}"
                return False

            self._client.connect()

            # Get available tools
            tools = self._client.list_tools()

            # Filter by allow/deny lists and add namespace
            self._tools = []
            for tool in tools:
                if self.plugin.is_tool_allowed(tool.name):
                    tool.namespace = self.plugin.namespace
                    self._tools.append(tool)

            self.plugin.available_tools = [t.name for t in self._tools]
            self.plugin.connected = True
            self.plugin.error = None
            return True

        except Exception as e:
            self.plugin.error = str(e)
            self.plugin.connected = False
            self.disconnect()
            return False

    def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._client:
            self._client.disconnect()
            self._client = None
        self.plugin.connected = False

    def get_tools(self) -> List[ToolInfo]:
        """Get list of available (filtered) tools."""
        return self._tools

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """Call a tool on the connected server."""
        if not self._client or not self._client.is_connected:
            return ToolCallResult(success=False, error="Not connected")

        # Check if tool is allowed
        if not self.plugin.is_tool_allowed(tool_name):
            return ToolCallResult(success=False, error=f"Tool '{tool_name}' is not allowed")

        return self._client.call_tool(tool_name, arguments)

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected
