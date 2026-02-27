# MCP Server Mode Guide

Expose MatrixShell's tools to other AI agents via MCP.

## Quick Start

### Install MCP Support

```bash
pip install "matrixsh[mcp]"
```

### Start MCP Server

```bash
# stdio mode (for Claude Desktop, etc.)
matrixsh --serve

# HTTP mode (for web clients)
matrixsh --serve --serve-transport streamable-http
```

---

## Available Tools

When running as MCP server, MatrixShell exposes these tools:

| Tool | Description |
|------|-------------|
| `shell.execute` | Run shell commands |
| `shell.cd` | Change directory |
| `shell.pwd` | Get current directory |
| `shell.ls` | List files |
| `safety.check_command` | Check if command is safe |
| `safety.get_denylist` | Get blocked commands |
| `history.get` | Get command history |
| `history.search` | Search history |
| `llm.ask` | Ask MatrixLLM |
| `config.get` | Get configuration |

---

## Use with Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "matrixsh": {
      "command": "matrixsh",
      "args": ["--serve"]
    }
  }
}
```

Restart Claude Desktop. MatrixShell tools are now available!

---

## Use with Other Clients

### HTTP Mode

```bash
matrixsh --serve --serve-transport streamable-http
```

Server runs at `http://localhost:8000/mcp`

### Example: List Tools

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Example: Run Command

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"shell.execute",
      "arguments":{"command":"echo hello"}
    }
  }'
```

---

## Security Notes

- MCP server mode respects the same safety denylist as interactive mode
- Dangerous commands are blocked automatically
- Run only on trusted networks
- Consider using authentication in production

---

## Troubleshooting

### "MCP module not installed"

```bash
pip install "matrixsh[mcp]"
```

### Server won't start

Check if port 8000 is in use:
```bash
lsof -i :8000
```

### Tools not appearing in Claude Desktop

1. Check the config path is correct
2. Restart Claude Desktop completely
3. Check logs for errors
