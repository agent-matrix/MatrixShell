"""Internal MCP organization for MatrixShell.

Normal usage is embedded (single process): CLI calls tools via ToolRegistry.
Power users can expose the same tools over MCP with `matrixsh --serve`.
"""

from .registry import ToolRegistry

__all__ = ["ToolRegistry"]
