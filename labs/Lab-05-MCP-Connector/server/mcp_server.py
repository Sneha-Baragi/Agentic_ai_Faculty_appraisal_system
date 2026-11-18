"""MCP-Style Mini Integration Server.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Scenario: Multi-Source Data Integration Server

Implements the MCPServer class which manages the unified CAPABILITIES manifest,
exposes data sources as resources and tools, and executes capability handlers
with permission boundary checks.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from server.api_tool import LocalApiTool
from server.capabilities import (
    Capability,
    get_default_capabilities,
    LIST_FILES_CAPABILITY,
)
from server.database_tool import DatabaseTool
from server.file_resource import FileResource


class MCPServer:
    """MCP Server exposing local files, SQLite, and mock API through unified contracts."""

    def __init__(
        self,
        safe_dir: Optional[Union[str, Path]] = None,
        db_path: Optional[Union[str, Path]] = None,
        include_assignment_1: bool = True,
    ) -> None:
        # Initialize backend adapters
        self.file_resource = FileResource(safe_dir=safe_dir)
        self.database_tool = DatabaseTool(db_path=db_path)
        self.api_tool = LocalApiTool()

        # Initialize capability registry
        self._capabilities: Dict[str, Capability] = get_default_capabilities(
            include_assignment_1=include_assignment_1
        )

        # Mapping of handler names to bound adapter methods
        self._handlers: Dict[str, Callable[..., Dict[str, Any]]] = {
            "read_file": self.file_resource.read_file,
            "query_db": self.database_tool.query,
            "call_api": self.api_tool.call_api,
            "list_files": self.file_resource.list_files,
        }

    # -------------------------------------------------------------------------
    # CAPABILITY DISCOVERY & MANIFEST INTERFACE
    # -------------------------------------------------------------------------

    def list_capabilities(self) -> List[Dict[str, Any]]:
        """Return the manifest describing every currently available capability.

        The manifest is the single source of truth for dynamic discovery.
        """
        return [cap.to_dict() for cap in self._capabilities.values()]

    def get_capability_manifest(self) -> Dict[str, Dict[str, Any]]:
        """Return capabilities manifest as a mapping keyed by capability name."""
        return {name: cap.to_dict() for name, cap in self._capabilities.items()}

    def get_capability(self, capability_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve the specification for a single designated capability."""
        cap = self._capabilities.get(capability_name)
        return cap.to_dict() if cap else None

    def register_capability(
        self,
        capability: Capability,
        handler: Optional[Callable[..., Dict[str, Any]]] = None,
    ) -> None:
        """Dynamically add or enable a capability on the server."""
        self._capabilities[capability.name] = capability
        if handler:
            self._handlers[capability.name] = handler
        elif capability.handler_name in self._handlers:
            self._handlers[capability.name] = self._handlers[capability.handler_name]

    def unregister_capability(self, capability_name: str) -> bool:
        """Dynamically remove a capability from the server manifest."""
        if capability_name in self._capabilities:
            del self._capabilities[capability_name]
            return True
        return False

    # -------------------------------------------------------------------------
    # CAPABILITY EXECUTION DISPATCH
    # -------------------------------------------------------------------------

    def execute(self, capability_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Dispatch execution to the appropriate capability handler on the server.

        Args:
            capability_name: The name of the registered capability (e.g. 'read_file').
            **kwargs: Arguments required by the capability handler.

        Returns:
            Structured dictionary response from the handler.
        """
        if capability_name not in self._capabilities:
            return {
                "status": "error",
                "error_code": "UNKNOWN_CAPABILITY",
                "message": (
                    f"Server error: Capability '{capability_name}' is not registered "
                    f"in the server manifest. Available: {sorted(list(self._capabilities.keys()))}."
                ),
            }

        cap = self._capabilities[capability_name]
        handler = self._handlers.get(cap.handler_name)

        if not handler:
            return {
                "status": "error",
                "error_code": "HANDLER_NOT_FOUND",
                "message": f"Server error: No handler bound for capability '{capability_name}'.",
            }

        try:
            return handler(**kwargs)
        except TypeError as err:
            return {
                "status": "error",
                "error_code": "INVALID_ARGUMENTS",
                "message": f"Parameter error invoking '{capability_name}': {str(err)}",
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "EXECUTION_EXCEPTION",
                "message": f"Exception raised executing '{capability_name}': {str(exc)}",
            }
