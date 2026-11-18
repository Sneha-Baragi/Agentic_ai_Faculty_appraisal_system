"""MCP Server Package.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
"""

from server.api_tool import LocalApiTool
from server.capabilities import Capability, get_default_capabilities
from server.database_tool import DatabaseTool
from server.file_resource import FileResource
from server.mcp_server import MCPServer

__all__ = [
    "MCPServer",
    "Capability",
    "DatabaseTool",
    "FileResource",
    "LocalApiTool",
    "get_default_capabilities",
]
