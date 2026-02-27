# MCP Server Catalog Guide

Simple guide to connect MatrixShell to external MCP servers.

## Quick Start

### 1. Login to a Catalog

```bash
matrixsh login --url http://localhost:4444 --token YOUR_JWT_TOKEN
```

### 2. List Available Servers

```bash
matrixsh servers
```

Output:
```
ID        Name          Status
github    GitHub MCP    active
slack     Slack MCP     inactive
```

### 3. Enable a Server

```bash
matrixsh enable github
```

### 4. Sync to Local Plugins

```bash
matrixsh sync
```

### 5. Check Status

```bash
matrixsh status
```

That's it! Your external tools are now available.

---

## All Commands

| Command | What it does |
|---------|--------------|
| `matrixsh login --url URL --token TOKEN` | Connect to catalog |
| `matrixsh logout` | Disconnect |
| `matrixsh status` | Show everything |
| `matrixsh servers` | List servers |
| `matrixsh enable ID` | Turn on a server |
| `matrixsh disable ID` | Turn off a server |
| `matrixsh tools` | List all tools |
| `matrixsh sync` | Save servers locally |
| `matrixsh unsync` | Remove synced servers |
| `matrixsh plugins` | Show local plugins |

---

## Example: Using ContextForge

[ContextForge](https://github.com/IBM/mcp-context-forge) is an MCP gateway that manages multiple MCP servers.

### Step 1: Start ContextForge

```bash
# Install
pip install mcp-context-forge

# Start
mcpgateway --port 4444
```

### Step 2: Get Your Token

Open http://localhost:4444 and copy your JWT token.

### Step 3: Connect MatrixShell

```bash
matrixsh login --url http://localhost:4444 --token eyJhbG...
matrixsh servers
matrixsh enable github
matrixsh sync
```

Done! GitHub tools are now available in MatrixShell.

---

## Manual Plugin Setup

Don't have a catalog? Add plugins manually:

```bash
# Add a plugin
matrixsh plugin add \
  --id my-server \
  --name "My MCP Server" \
  --transport stdio \
  --command "python -m my_mcp_server"

# Or HTTP plugin
matrixsh plugin add \
  --id remote-server \
  --name "Remote Server" \
  --transport streamable-http \
  --url http://example.com/mcp
```

### Plugin Commands

| Command | What it does |
|---------|--------------|
| `matrixsh plugin list` | Show all plugins |
| `matrixsh plugin add ...` | Add new plugin |
| `matrixsh plugin enable ID` | Enable plugin |
| `matrixsh plugin disable ID` | Disable plugin |
| `matrixsh plugin remove ID` | Delete plugin |

---

## Troubleshooting

### "Catalog not configured"

Run `matrixsh login` first.

### "Authentication failed"

Your token expired. Get a new one and login again.

### "Cannot connect"

Check if the catalog server is running.

### Plugins not working after sync?

```bash
matrixsh unsync
matrixsh sync
```

---

## Config File Locations

| OS | Path |
|----|------|
| Linux/macOS | `~/.config/matrixsh/catalog.json` |
| Windows | `%APPDATA%\matrixsh\catalog.json` |

Plugins are stored in `plugins.json` in the same folder.
