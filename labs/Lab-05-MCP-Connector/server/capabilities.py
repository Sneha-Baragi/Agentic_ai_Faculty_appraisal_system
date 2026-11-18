"""MCP Capabilities Manifest and Capability Contract Definitions.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Scenario: Capability Manifest & Contract Definition

Defines the structured capability manifest entries exposing resources and tools
through standardized MCP schemas, descriptions, and input/output contracts.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Capability:
    """Represents a single MCP capability exposed by the server."""

    name: str
    kind: str  # 'resource' or 'tool'
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    handler_name: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize capability contract into standard dictionary format."""
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


# -----------------------------------------------------------------------------
# BASE CAPABILITIES MANIFEST (Original 3 Capabilities)
# -----------------------------------------------------------------------------

READ_FILE_CAPABILITY = Capability(
    name="read_file",
    kind="resource",
    description=(
        "Read the text content of a designated file located within the declared "
        "safe data directory boundary. Prevents directory traversals."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative file path within safe_data/ (e.g. 'README.md', 'announcements.txt')",
            },
        },
        "required": ["file_path"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "error"]},
            "file_name": {"type": "string"},
            "content": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "relative_path": {"type": "string"},
        },
        "required": ["status"],
    },
    handler_name="read_file",
)

QUERY_DB_CAPABILITY = Capability(
    name="query_db",
    kind="tool",
    description=(
        "Execute a read-only SELECT SQL statement on the campus SQLite database (signups table). "
        "Strictly rejects modifications (INSERT, UPDATE, DELETE, DROP, etc.) and unauthorized callers."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "Read-only SELECT query (e.g. 'SELECT event, count FROM signups;')",
            },
            "caller_id": {
                "type": "string",
                "description": "Authorized caller identifier token",
                "default": "data_assistant",
            },
        },
        "required": ["sql"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "error"]},
            "columns": {"type": "array", "items": {"type": "string"}},
            "rows": {"type": "array", "items": {"type": "object"}},
            "row_count": {"type": "integer"},
            "query": {"type": "string"},
        },
        "required": ["status"],
    },
    handler_name="query_db",
)

CALL_API_CAPABILITY = Capability(
    name="call_api",
    kind="tool",
    description=(
        "Invoke a deterministic local mock campus API endpoint. Supported endpoints include "
        "'events_today', 'event_details', and 'system_status'. Rejects unknown endpoints."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "description": "Target mock API endpoint name (e.g. 'events_today')",
            },
            "params": {
                "type": "object",
                "description": "Optional parameters dictionary",
            },
        },
        "required": ["endpoint"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "error"]},
            "endpoint": {"type": "string"},
            "data": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "total_events": {"type": "integer"},
                    "events": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
            },
        },
        "required": ["status"],
    },
    handler_name="call_api",
)


# -----------------------------------------------------------------------------
# ASSIGNMENT 1 CAPABILITY: list_files (Resource)
# -----------------------------------------------------------------------------

LIST_FILES_CAPABILITY = Capability(
    name="list_files",
    kind="resource",
    description=(
        "List all accessible files and directory metadata located within the declared "
        "safe data directory boundary."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "subdir": {
                "type": "string",
                "description": "Optional relative subdirectory within safe_data/ to inspect",
                "default": "",
            },
        },
        "required": [],
    },
    output_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "error"]},
            "directory": {"type": "string"},
            "file_count": {"type": "integer"},
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "size_bytes": {"type": "integer"},
                        "extension": {"type": "string"},
                    },
                },
            },
        },
        "required": ["status"],
    },
    handler_name="list_files",
)


def get_default_capabilities(include_assignment_1: bool = True) -> Dict[str, Capability]:
    """Return dictionary of registered capabilities.

    Args:
        include_assignment_1: If True, includes the 4th capability ('list_files').

    Returns:
        Dictionary mapping capability name to Capability object.
    """
    caps: Dict[str, Capability] = {
        "read_file": READ_FILE_CAPABILITY,
        "query_db": QUERY_DB_CAPABILITY,
        "call_api": CALL_API_CAPABILITY,
    }
    if include_assignment_1:
        caps["list_files"] = LIST_FILES_CAPABILITY
    return caps
