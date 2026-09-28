"""MCP-style adapter package for read-only appraisal tools.

This package provides a thin compatibility layer over the existing approved tool
functions. It intentionally does not implement a networked or remote MCP server.
"""

from .connector import get_mcp_tool, get_mcp_tools

__all__ = ["get_mcp_tool", "get_mcp_tools"]
