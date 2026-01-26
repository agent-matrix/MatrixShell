"""MatrixShell Plugin System.

Allows MatrixShell to act as an MCP aggregator/orchestrator that can:
- Run built-in tools (shell/safety/history/llm)
- Mount external MCP servers as plugins
- Provide unified tool catalog with namespacing
- Enforce central policy across all tools

Admin commands:
- matrixsh plugin list      - List all plugins
- matrixsh plugin add       - Add a new plugin
- matrixsh plugin remove    - Remove a plugin
- matrixsh plugin enable    - Enable a plugin
- matrixsh plugin disable   - Disable a plugin
- matrixsh plugin tools     - List tools from a plugin
- matrixsh plugin doctor    - Check health of all plugins
"""

from .models import Plugin, PluginPermissions, PluginConfig, AgentProfile
from .manager import PluginManager, create_stdio_plugin, create_http_plugin
from .broker import ToolBroker, UnifiedTool

__all__ = [
    "Plugin",
    "PluginPermissions",
    "PluginConfig",
    "AgentProfile",
    "PluginManager",
    "ToolBroker",
    "UnifiedTool",
    "create_stdio_plugin",
    "create_http_plugin",
]
