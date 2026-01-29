"""
MatrixShell MCP Server with SSE support.

This module provides an MCP (Model Context Protocol) server that can be registered
with Context Forge for integration with Claude and other AI assistants.

Usage:
    python -m matrixsh.mcp_server --host 127.0.0.1 --port 9000

Dependencies:
    pip install matrixsh[mcp]
    # or: pip install uvicorn starlette sse-starlette
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

try:
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route
    from sse_starlette.sse import EventSourceResponse
    import uvicorn
except ImportError:
    print("MCP server requires additional dependencies.")
    print("Install them with: pip install matrixsh[mcp]")
    print("Or: pip install uvicorn starlette sse-starlette")
    sys.exit(1)


# MCP Protocol version
MCP_VERSION = "2024-11-05"

# Server info
SERVER_NAME = "matrixsh"
SERVER_VERSION = "0.1.0"

# Active SSE connections
_connections: dict[str, asyncio.Queue] = {}


async def health(request):
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "mcp_version": MCP_VERSION,
    })


async def mcp_sse(request):
    """
    MCP SSE endpoint for Server-Sent Events communication.

    This implements the MCP transport layer using SSE for server->client
    and POST for client->server messages.
    """
    connection_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _connections[connection_id] = queue

    async def event_generator():
        try:
            # Send initial connection established message
            yield {
                "event": "endpoint",
                "data": f"/mcp/message?session_id={connection_id}"
            }

            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": "message",
                        "data": json.dumps(message)
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}
        except asyncio.CancelledError:
            pass
        finally:
            _connections.pop(connection_id, None)

    return EventSourceResponse(event_generator())


async def mcp_message(request):
    """
    Handle incoming MCP messages from clients.
    """
    session_id = request.query_params.get("session_id")
    if not session_id or session_id not in _connections:
        return JSONResponse(
            {"error": "Invalid or expired session"},
            status_code=400
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "Invalid JSON"},
            status_code=400
        )

    # Process MCP request
    response = await handle_mcp_request(body)

    # Send response via SSE
    queue = _connections.get(session_id)
    if queue:
        await queue.put(response)

    return JSONResponse({"status": "ok"})


async def handle_mcp_request(request: dict[str, Any]) -> dict[str, Any]:
    """
    Handle MCP protocol requests.
    """
    method = request.get("method", "")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": MCP_VERSION,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "shell_execute",
                        "description": "Execute a shell command via MatrixShell with AI assistance",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "string",
                                    "description": "The shell command to execute"
                                },
                                "cwd": {
                                    "type": "string",
                                    "description": "Working directory (optional)"
                                }
                            },
                            "required": ["command"]
                        }
                    },
                    {
                        "name": "shell_suggest",
                        "description": "Get AI-powered command suggestions for a task",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task": {
                                    "type": "string",
                                    "description": "Natural language description of what you want to do"
                                },
                                "cwd": {
                                    "type": "string",
                                    "description": "Working directory for context (optional)"
                                }
                            },
                            "required": ["task"]
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = request.get("params", {}).get("name")
        tool_args = request.get("params", {}).get("arguments", {})

        result = await execute_tool(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }

    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": []}
        }

    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"prompts": []}
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


async def execute_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """
    Execute an MCP tool.
    """
    if tool_name == "shell_execute":
        command = args.get("command", "")
        cwd = args.get("cwd")

        import subprocess
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=60
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Exit code: {result.returncode}\n\nStdout:\n{result.stdout}\n\nStderr:\n{result.stderr}"
                    }
                ]
            }
        except subprocess.TimeoutExpired:
            return {
                "content": [{"type": "text", "text": "Command timed out after 60 seconds"}],
                "isError": True
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Error executing command: {e}"}],
                "isError": True
            }

    elif tool_name == "shell_suggest":
        task = args.get("task", "")
        cwd = args.get("cwd")

        # Try to use MatrixLLM for suggestions
        try:
            from .config import Settings
            from .llm import MatrixLLM
            from .shell import detect_default_mode, list_files, os_name

            settings = Settings.load()
            llm = MatrixLLM(
                settings.base_url,
                settings.api_key,
                token=settings.token,
                timeout_s=settings.timeout_s
            )

            mode = detect_default_mode()
            files = list_files(cwd) if cwd else []

            suggestion = llm.suggest(
                model=settings.model,
                os_name=os_name(),
                shell_mode=mode,
                cwd=cwd or ".",
                files=files,
                user_input=task,
            )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Suggested command: {suggestion.command}\n\nExplanation: {suggestion.explanation}\n\nRisk level: {suggestion.risk}"
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Could not get suggestion from MatrixLLM: {e}"}],
                "isError": True
            }

    return {
        "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
        "isError": True
    }


# Create Starlette app
app = Starlette(
    debug=False,
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/mcp/sse", mcp_sse, methods=["GET"]),
        Route("/mcp/message", mcp_message, methods=["POST"]),
    ],
)


def main():
    parser = argparse.ArgumentParser(
        prog="matrixsh.mcp_server",
        description="MatrixShell MCP Server with SSE support"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9000, help="Port to bind to (default: 9000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    print(f"Starting MatrixShell MCP Server...")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  SSE URL: http://{args.host}:{args.port}/mcp/sse")
    print(f"  Health: http://{args.host}:{args.port}/health")
    print()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
