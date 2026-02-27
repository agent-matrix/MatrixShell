"""Provider modules for external MCP server catalogs.

Providers are special plugin sources that can automatically
discover and sync MCP servers into MatrixShell's plugin registry.
"""

from .contextforge import ContextForgeProvider, ContextForgeConfig

__all__ = ["ContextForgeProvider", "ContextForgeConfig"]
