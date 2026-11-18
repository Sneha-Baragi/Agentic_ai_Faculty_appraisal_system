"""MCP-Style Client Interface.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Scenario: Capability Discovery and Dispatch Layer

Implements the MCPClient class that dynamically queries capability manifests
from the MCPServer, validates input arguments against schemas, and dispatches
execution requests.

NOTE: This client is fully dynamic and contains NO hardcoded references to
individual capabilities (such as 'read_file', 'query_db', 'call_api', or 'list_files').
Any new capability registered on the server is discovered and invokable without code edits.
"""

from typing import Any, Dict, List, Optional
from server.mcp_server import MCPServer


class MCPClient:
    """Client for interacting with an MCP-style integration server."""

    def __init__(self, server: MCPServer) -> None:
        """Initialize MCP client connected to target server instance.

        Args:
            server: MCPServer instance to query and execute through.
        """
        self._server = server
        self._manifest: Dict[str, Dict[str, Any]] = {}
        self._last_discovery_count: int = 0
        # Automatically perform initial discovery
        self.discover()

    # -------------------------------------------------------------------------
    # DISCOVERY INTERFACE
    # -------------------------------------------------------------------------

    def discover(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Query server for the list of available capabilities and cache manifest.

        Args:
            force_refresh: Whether to force querying the server manifest.

        Returns:
            List of capability contract dictionaries.
        """
        capabilities_list = self._server.list_capabilities()
        self._manifest = {cap["name"]: cap for cap in capabilities_list}
        self._last_discovery_count = len(self._manifest)
        return capabilities_list

    def list_capabilities(self) -> List[Dict[str, Any]]:
        """Return the currently cached capability specifications."""
        if not self._manifest:
            return self.discover()
        return list(self._manifest.values())

    def get_capability(self, capability_name: str) -> Optional[Dict[str, Any]]:
        """Get specification for a specific capability by name."""
        # Always check cached manifest first, refresh if not found in case server registered new ones
        if capability_name not in self._manifest:
            self.discover(force_refresh=True)
        return self._manifest.get(capability_name)

    def has_capability(self, capability_name: str) -> bool:
        """Check if capability is available on the server."""
        return self.get_capability(capability_name) is not None

    # -------------------------------------------------------------------------
    # CAPABILITY INVOCATION WITH SCHEMA VALIDATION
    # -------------------------------------------------------------------------

    def call(self, capability_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Invoke a capability through the structured connector interface.

        Validates that:
        1. The capability exists in the discovered manifest.
        2. All required parameters defined in input_schema are supplied.

        Then dispatches execution to the server.

        Args:
            capability_name: The name of the capability to invoke.
            **kwargs: Arguments to pass to the capability.

        Returns:
            Structured dictionary response from the server handler.
        """
        # Ensure discovery is up-to-date
        cap_spec = self.get_capability(capability_name)
        if not cap_spec:
            return {
                "status": "error",
                "error_code": "UNKNOWN_CAPABILITY",
                "message": (
                    f"Client error: Capability '{capability_name}' is not recognized "
                    f"in the discovered manifest. Available: {sorted(list(self._manifest.keys()))}."
                ),
            }

        # Validate required parameters from input schema
        input_schema = cap_spec.get("input_schema", {})
        required_fields: List[str] = input_schema.get("required", [])
        properties: Dict[str, Any] = input_schema.get("properties", {})

        missing_fields = [field for field in required_fields if field not in kwargs]
        if missing_fields:
            return {
                "status": "error",
                "error_code": "MISSING_REQUIRED_PARAMETER",
                "message": (
                    f"Client error: Missing required parameter(s) {missing_fields} "
                    f"for capability '{capability_name}'."
                ),
            }

        # Apply schema defaults for optional parameters if not provided in kwargs
        call_kwargs = dict(kwargs)
        for prop_name, prop_meta in properties.items():
            if prop_name not in call_kwargs and "default" in prop_meta:
                call_kwargs[prop_name] = prop_meta["default"]

        # Dispatch execution to the server
        return self._server.execute(capability_name, **call_kwargs)
