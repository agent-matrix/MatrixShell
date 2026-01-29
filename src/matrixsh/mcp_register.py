"""
Register MatrixShell MCP Server with Context Forge.

This module handles the registration of the MCP server endpoint
with a Context Forge instance.

Usage:
    python -m matrixsh.mcp_register --url http://127.0.0.1:9000/mcp/sse
"""
from __future__ import annotations

import argparse
import sys

import requests
from rich.console import Console

from .config import Settings

console = Console()


def register_mcp_server(mcp_url: str, context_forge_url: str | None = None, token: str | None = None) -> bool:
    """
    Register the MCP server URL with Context Forge.

    Args:
        mcp_url: The MCP SSE endpoint URL (e.g., http://127.0.0.1:9000/mcp/sse)
        context_forge_url: Context Forge URL (uses settings if not provided)
        token: Context Forge token (uses settings if not provided)

    Returns:
        True if registration succeeded, False otherwise
    """
    settings = Settings.load()

    cf_url = context_forge_url or settings.context_forge_url
    cf_token = token or settings.context_forge_token

    if not cf_url:
        console.print("[red]Error: Context Forge URL not configured.[/red]")
        console.print("")
        console.print("Configure it with one of:")
        console.print("  1. matrixsh login --url http://localhost:4444 --token YOUR_TOKEN")
        console.print("  2. Set CONTEXT_FORGE_URL environment variable")
        console.print("  3. Add context_forge_url to your config file")
        return False

    if not cf_token:
        console.print("[red]Error: Context Forge token not configured.[/red]")
        console.print("")
        console.print("Configure it with one of:")
        console.print("  1. matrixsh login --url http://localhost:4444 --token YOUR_TOKEN")
        console.print("  2. Set CONTEXT_FORGE_TOKEN environment variable")
        console.print("  3. Add context_forge_token to your config file")
        return False

    # Prepare registration payload
    payload = {
        "name": "matrixsh",
        "url": mcp_url,
        "description": "MatrixShell: AI-augmented shell wrapper powered by MatrixLLM",
        "transport": "sse",
    }

    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json",
    }

    # Try to register
    register_endpoint = f"{cf_url.rstrip('/')}/api/mcp/servers"

    try:
        console.print(f"Registering with Context Forge at {cf_url}...")
        console.print(f"MCP Server URL: {mcp_url}")
        console.print("")

        response = requests.post(
            register_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code in (200, 201):
            console.print("[green]Successfully registered MCP server with Context Forge![/green]")
            try:
                result = response.json()
                if result.get("id"):
                    console.print(f"Server ID: {result['id']}")
            except Exception:
                pass
            return True

        elif response.status_code == 409:
            console.print("[yellow]MCP server already registered. Updating...[/yellow]")
            # Try to update instead
            update_endpoint = f"{cf_url.rstrip('/')}/api/mcp/servers/matrixsh"
            response = requests.put(
                update_endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )
            if response.status_code in (200, 201):
                console.print("[green]Successfully updated MCP server registration![/green]")
                return True
            else:
                console.print(f"[red]Failed to update: {response.status_code}[/red]")
                try:
                    console.print(response.json())
                except Exception:
                    console.print(response.text)
                return False

        elif response.status_code == 401:
            console.print("[red]Error: Authentication failed. Check your Context Forge token.[/red]")
            return False

        elif response.status_code == 403:
            console.print("[red]Error: Permission denied. Your token may not have registration permissions.[/red]")
            return False

        else:
            console.print(f"[red]Error: Registration failed with status {response.status_code}[/red]")
            try:
                error_detail = response.json()
                console.print(f"Details: {error_detail}")
            except Exception:
                console.print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        console.print(f"[red]Error: Could not connect to Context Forge at {cf_url}[/red]")
        console.print("Make sure Context Forge is running and the URL is correct.")
        return False

    except requests.exceptions.Timeout:
        console.print("[red]Error: Request to Context Forge timed out.[/red]")
        return False

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return False


def main():
    parser = argparse.ArgumentParser(
        prog="matrixsh.mcp_register",
        description="Register MatrixShell MCP Server with Context Forge"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="MCP Server SSE URL (e.g., http://127.0.0.1:9000/mcp/sse)"
    )
    parser.add_argument(
        "--context-forge-url",
        help="Context Forge URL (overrides settings)"
    )
    parser.add_argument(
        "--token",
        help="Context Forge token (overrides settings)"
    )

    args = parser.parse_args()

    success = register_mcp_server(
        mcp_url=args.url,
        context_forge_url=args.context_forge_url,
        token=args.token
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
