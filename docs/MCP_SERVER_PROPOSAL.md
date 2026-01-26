# MCP Server Unification Proposal for MatrixShell

## Executive Summary

This document proposes unifying all MatrixShell tools into a single MCP (Model Context Protocol) server. This architectural change would:

- **Centralize tool management** for easier maintenance
- **Enable tool reuse** across different agents and interfaces
- **Standardize communication** via MCP protocol
- **Preserve all existing functionality** through careful mapping

**Feasibility Assessment: HIGHLY FEASIBLE**

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        cli.py                                │
│                    (Orchestrator)                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
    ┌─────────┬───────────┼───────────┬─────────┬─────────┐
    │         │           │           │         │         │
    ▼         ▼           ▼           ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌─────────┐ ┌────────┐ ┌───────┐ ┌──────┐
│shell  │ │safety │ │  llm    │ │history │ │config │ │gateway│
│.py    │ │.py    │ │  .py    │ │.py     │ │.py    │ │.py   │
└───────┘ └───────┘ └─────────┘ └────────┘ └───────┘ └──────┘
```

**Problem**: Direct function calls tightly couple the CLI to all modules.

---

## Proposed MCP Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Clients                               │
│         (CLI, Web UI, IDE Extensions, Other Agents)          │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP Protocol (JSON-RPC)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│                   MatrixShell MCP Server                     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Tool Registry                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │    │
│  │  │  Shell   │ │  Safety  │ │   LLM    │ │ History│  │    │
│  │  │  Tools   │ │  Tools   │ │  Tools   │ │ Tools  │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐             │    │
│  │  │  Config  │ │ Gateway  │ │  Pairing │             │    │
│  │  │  Tools   │ │  Tools   │ │  Tools   │             │    │
│  │  └──────────┘ └──────────┘ └──────────┘             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Tool Mapping to MCP

### Tool Group 1: Shell Execution

```python
# MCP Tool Definition
@mcp_tool(name="shell_execute")
async def shell_execute(
    command: str,
    mode: Literal["bash", "powershell", "cmd"] = "bash",
    cwd: str = "."
) -> dict:
    """Execute a shell command and return results."""
    return {
        "exit_code": int,
        "stdout": str,
        "stderr": str
    }

@mcp_tool(name="shell_change_directory")
async def shell_change_directory(
    path: str,
    current_cwd: str,
    mode: str = "bash"
) -> dict:
    """Change working directory with validation."""
    return {
        "success": bool,
        "new_cwd": str,
        "error": str | None
    }

@mcp_tool(name="shell_list_files")
async def shell_list_files(cwd: str, limit: int = 200) -> dict:
    """List files in directory for context."""
    return {
        "files": list[str],
        "truncated": bool
    }

@mcp_tool(name="shell_get_system_info")
async def shell_get_system_info() -> dict:
    """Get OS and shell information."""
    return {
        "os": str,
        "default_shell": str,
        "home_dir": str
    }
```

### Tool Group 2: Safety & Validation

```python
@mcp_tool(name="safety_validate_command")
async def safety_validate_command(command: str) -> dict:
    """Check if command is safe to execute."""
    return {
        "allowed": bool,
        "reason": str | None,
        "risk_level": Literal["low", "medium", "high", "blocked"]
    }

@mcp_tool(name="safety_classify_input")
async def safety_classify_input(text: str) -> dict:
    """Determine if input is natural language or shell command."""
    return {
        "is_natural_language": bool,
        "confidence": float,
        "detected_language": str | None
    }

@mcp_tool(name="safety_parse_shell_error")
async def safety_parse_shell_error(
    stderr: str,
    mode: str
) -> dict:
    """Parse shell error to determine type."""
    return {
        "is_command_not_found": bool,
        "error_type": str,
        "suggestion": str | None
    }
```

### Tool Group 3: LLM Communication

```python
@mcp_tool(name="llm_suggest_command")
async def llm_suggest_command(
    user_input: str,
    os_name: str,
    shell_mode: str,
    cwd: str,
    files: list[str],
    history: list[dict] = []
) -> dict:
    """Get AI suggestion for shell command."""
    return {
        "explanation": str,
        "command": str,
        "risk": Literal["low", "medium", "high"]
    }

@mcp_tool(name="llm_chat")
async def llm_chat(
    messages: list[dict],
    model: str = "deepseek-r1",
    stream: bool = False
) -> dict:
    """Send chat messages to LLM."""
    return {
        "response": str,
        "model": str,
        "usage": dict | None
    }

@mcp_tool(name="llm_health_check")
async def llm_health_check() -> dict:
    """Check LLM gateway health."""
    return {
        "healthy": bool,
        "latency_ms": int,
        "model_available": bool
    }
```

### Tool Group 4: History & Persistence

```python
@mcp_tool(name="history_append")
async def history_append(
    cwd: str,
    kind: Literal["user", "assistant", "exec"],
    text: str
) -> dict:
    """Log an interaction to history."""
    return {
        "success": bool,
        "timestamp": str
    }

@mcp_tool(name="history_load")
async def history_load(
    cwd: str,
    limit: int = 50
) -> dict:
    """Load recent history for directory."""
    return {
        "items": list[dict],  # {ts, cwd, kind, text}
        "total_count": int
    }
```

### Tool Group 5: Configuration

```python
@mcp_tool(name="config_get")
async def config_get() -> dict:
    """Get current configuration."""
    return {
        "base_url": str,
        "model": str,
        "timeout_s": int,
        "has_api_key": bool,
        "has_token": bool
    }

@mcp_tool(name="config_set")
async def config_set(
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    token: str | None = None,
    timeout_s: int | None = None
) -> dict:
    """Update configuration."""
    return {
        "success": bool,
        "config_path": str
    }
```

### Tool Group 6: Gateway Management

```python
@mcp_tool(name="gateway_start")
async def gateway_start(
    model: str = "deepseek-r1",
    host: str = "127.0.0.1",
    port: int = 11435,
    auth_mode: Literal["pairing", "key"] = "pairing"
) -> dict:
    """Start local MatrixLLM gateway."""
    return {
        "success": bool,
        "pairing_code": str | None,
        "base_url": str
    }

@mcp_tool(name="gateway_stop")
async def gateway_stop() -> dict:
    """Stop local gateway process."""
    return {"success": bool}

@mcp_tool(name="gateway_pair")
async def gateway_pair(code: str) -> dict:
    """Complete pairing with gateway."""
    return {
        "success": bool,
        "token": str | None,
        "error": str | None
    }
```

---

## MCP Resources (Read-Only Data)

```python
# Resources provide read-only access to state

@mcp_resource(uri="matrixsh://system/info")
async def resource_system_info() -> dict:
    """Current system information."""
    return {
        "os": os_name(),
        "shell": detect_default_mode(),
        "cwd": os.getcwd()
    }

@mcp_resource(uri="matrixsh://config")
async def resource_config() -> dict:
    """Current configuration (sanitized)."""
    settings = Settings.load()
    return {
        "base_url": settings.base_url,
        "model": settings.model,
        "timeout_s": settings.timeout_s
    }

@mcp_resource(uri="matrixsh://history/{cwd_hash}")
async def resource_history(cwd_hash: str) -> dict:
    """History for a specific directory."""
    # Load and return history
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1-2)

1. **Create MCP server skeleton**
   ```
   src/matrixsh/
   ├── mcp/
   │   ├── __init__.py
   │   ├── server.py          # MCP server entry point
   │   ├── tools/
   │   │   ├── __init__.py
   │   │   ├── shell.py       # Shell tool implementations
   │   │   ├── safety.py      # Safety tool implementations
   │   │   ├── llm.py         # LLM tool implementations
   │   │   ├── history.py     # History tool implementations
   │   │   ├── config.py      # Config tool implementations
   │   │   └── gateway.py     # Gateway tool implementations
   │   └── resources/
   │       ├── __init__.py
   │       └── state.py       # Read-only resources
   ```

2. **Wrap existing functions as MCP tools**
   - Keep original modules unchanged initially
   - MCP tools call into existing functions
   - Enables parallel operation during migration

### Phase 2: Tool Migration (Week 3-4)

3. **Migrate shell tools**
   - `execute()` → `shell_execute`
   - `handle_cd()` → `shell_change_directory`
   - `list_files()` → `shell_list_files`

4. **Migrate safety tools**
   - `denylist_match()` → `safety_validate_command`
   - `looks_like_natural_language()` → `safety_classify_input`

5. **Migrate LLM tools**
   - `MatrixLLM.suggest()` → `llm_suggest_command`
   - `MatrixLLM.chat_*()` → `llm_chat`

### Phase 3: Client Migration (Week 5-6)

6. **Create MCP client wrapper for CLI**
   ```python
   # cli.py now uses MCP client
   class MatrixShellClient:
       def __init__(self, server_uri: str):
           self.client = MCPClient(server_uri)

       async def execute_command(self, cmd: str):
           return await self.client.call_tool("shell_execute", {"command": cmd})
   ```

7. **Update CLI to use MCP client**
   - Replace direct function calls with MCP tool calls
   - Maintain identical user experience

### Phase 4: Testing & Documentation (Week 7-8)

8. **Comprehensive testing**
   - Unit tests for each MCP tool
   - Integration tests for tool chains
   - E2E tests for CLI via MCP

9. **Documentation**
   - MCP tool reference documentation
   - Migration guide for custom integrations

---

## Directory Structure (Final)

```
src/matrixsh/
├── __init__.py
├── cli.py                    # Thin CLI using MCP client
├── mcp/
│   ├── __init__.py
│   ├── server.py             # MCP server entry point
│   ├── registry.py           # Tool registration
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── shell.py          # execute, cd, list_files
│   │   ├── safety.py         # validate, classify
│   │   ├── llm.py            # suggest, chat, health
│   │   ├── history.py        # append, load
│   │   ├── config.py         # get, set
│   │   └── gateway.py        # start, stop, pair
│   ├── resources/
│   │   ├── __init__.py
│   │   └── state.py          # system_info, config
│   └── types.py              # Shared types/schemas
├── core/                     # Extracted core logic
│   ├── __init__.py
│   ├── shell.py              # Shell execution (moved from root)
│   ├── safety.py             # Safety logic
│   ├── llm.py                # LLM client
│   ├── history.py            # History persistence
│   ├── config.py             # Configuration
│   └── gateway.py            # Gateway management
└── legacy/                   # Deprecated direct imports
    └── __init__.py           # Re-exports for backwards compat
```

---

## Benefits of MCP Unification

### 1. **Maintainability**
- Single source of truth for tool definitions
- Clear interface contracts via MCP schemas
- Easier testing with standardized tool format

### 2. **Extensibility**
- New tools added without changing clients
- Third-party integrations via MCP protocol
- IDE extensions can use same tools

### 3. **Reusability**
- Same tools available to multiple agents
- Web UI, CLI, and extensions share tools
- Other AI assistants can use MatrixShell tools

### 4. **Observability**
- Centralized logging of all tool calls
- Metrics and monitoring in one place
- Audit trail for all operations

### 5. **Security**
- Centralized permission checking
- Tool-level access control
- Request validation in one layer

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance overhead | Medium | Use local socket for CLI, benchmark critical paths |
| Migration complexity | High | Phased approach with parallel operation |
| Breaking changes | High | Maintain backwards-compatible re-exports |
| MCP protocol changes | Low | Abstract protocol layer, version pinning |

---

## Success Criteria

1. **Functional Parity**: All existing CLI commands work identically
2. **Performance**: <10ms overhead for local MCP calls
3. **Test Coverage**: >90% coverage for MCP tools
4. **Documentation**: Complete API reference for all tools
5. **Multi-client**: CLI + at least one other client using MCP

---

## Conclusion

Unifying MatrixShell tools into an MCP server is **highly feasible** and **recommended** because:

1. **Clean existing boundaries** - Tools already have clear, single-purpose interfaces
2. **Stateless design** - Most tools are pure functions, ideal for server pattern
3. **Type contracts** - Dataclasses translate directly to MCP schemas
4. **Platform abstraction** - Already done, no additional work needed
5. **Minimal dependencies** - Few inter-module dependencies simplify migration

The proposed architecture preserves all functionality while enabling better maintenance, reusability, and extensibility.

---

## Next Steps

1. [ ] Review and approve this proposal
2. [ ] Set up MCP server skeleton with Python MCP SDK
3. [ ] Implement first tool group (Shell) as proof of concept
4. [ ] Validate performance with benchmarks
5. [ ] Proceed with full migration
