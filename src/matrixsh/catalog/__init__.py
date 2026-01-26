"""Catalog Module for MatrixShell.

Provides a unified interface to external MCP server catalogs (like ContextForge).
This module handles:
- Catalog authentication and configuration
- Server discovery and management
- Tool listing
- Sync operations to populate plugins.json
"""

from .client import CatalogClient, CatalogConfig, CatalogServer, CatalogTool, CatalogError
from .sync import sync_catalog, unsync_catalog, get_sync_status, get_all_plugins

__all__ = [
    "CatalogClient",
    "CatalogConfig",
    "CatalogServer",
    "CatalogTool",
    "CatalogError",
    "sync_catalog",
    "unsync_catalog",
    "get_sync_status",
    "get_all_plugins",
]
