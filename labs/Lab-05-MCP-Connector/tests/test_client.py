"""Unit Tests for MCPClient Interface.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
"""

import inspect
from pathlib import Path
import unittest

from client.mcp_client import MCPClient
from server.mcp_server import MCPServer


class TestMCPClient(unittest.TestCase):
    """Test suite for MCPClient dynamic discovery, validation, and invocation."""

    def setUp(self) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.safe_dir = self.base_dir / "safe_data"
        self.db_path = self.base_dir / "data" / "campus.db"
        self.server = MCPServer(
            safe_dir=self.safe_dir,
            db_path=self.db_path,
            include_assignment_1=True,
        )
        self.client = MCPClient(self.server)

    def test_dynamic_discovery_populates_manifest(self) -> None:
        """Verify client dynamically queries and caches capabilities from server."""
        caps = self.client.discover()
        self.assertGreaterEqual(len(caps), 4)

        names = {c["name"] for c in caps}
        self.assertIn("read_file", names)
        self.assertIn("query_db", names)
        self.assertIn("call_api", names)
        self.assertIn("list_files", names)

    def test_get_capability_from_manifest(self) -> None:
        """Verify retrieving capability contract details through client."""
        cap = self.client.get_capability("read_file")
        self.assertIsNotNone(cap)
        self.assertEqual(cap["name"], "read_file")
        self.assertEqual(cap["kind"], "resource")

    def test_missing_required_parameter_validation(self) -> None:
        """Verify client validates input schema and blocks calls missing required arguments."""
        # read_file requires 'file_path'
        res = self.client.call("read_file")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "MISSING_REQUIRED_PARAMETER")
        self.assertIn("file_path", res["message"])

        # query_db requires 'sql'
        res = self.client.call("query_db")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "MISSING_REQUIRED_PARAMETER")
        self.assertIn("sql", res["message"])

        # call_api requires 'endpoint'
        res = self.client.call("call_api")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "MISSING_REQUIRED_PARAMETER")
        self.assertIn("endpoint", res["message"])

    def test_call_known_capabilities(self) -> None:
        """Verify successful dispatch across resources and tools via client."""
        # 1. Resource: read_file
        res_file = self.client.call("read_file", file_path="README.md")
        self.assertEqual(res_file["status"], "success")
        self.assertIn("Campus Activities", res_file["content"])

        # 2. Tool: query_db (caller_id gets schema default applied if omitted)
        res_db = self.client.call("query_db", sql="SELECT COUNT(*) AS total FROM signups;")
        self.assertEqual(res_db["status"], "success")
        self.assertEqual(res_db["rows"][0]["total"], 3)

        # 3. Tool: call_api
        res_api = self.client.call("call_api", endpoint="events_today")
        self.assertEqual(res_api["status"], "success")
        self.assertEqual(res_api["data"]["total_events"], 2)

        # 4. Resource: list_files
        res_list = self.client.call("list_files")
        self.assertEqual(res_list["status"], "success")
        self.assertGreaterEqual(res_list["file_count"], 2)

    def test_unknown_capability_handling(self) -> None:
        """Verify client returns structured error when calling unregistered capability."""
        res = self.client.call("unregistered_capability", test_arg="value")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "UNKNOWN_CAPABILITY")

    def test_no_hardcoded_list_files_in_client(self) -> None:
        """Verify client contains zero hardcoded references to 'list_files'.

        Assignment 1 constraint: The client must discover and invoke list_files dynamically
        without any special-cased code or hardcoded names in MCPClient.
        """
        source = inspect.getsource(MCPClient)
        # Search for any string literal or identifier 'list_files' in the client source
        self.assertNotIn(
            "'list_files'",
            source,
            "MCPClient must not contain hardcoded string literal 'list_files'.",
        )
        self.assertNotIn(
            '"list_files"',
            source,
            'MCPClient must not contain hardcoded string literal "list_files".',
        )
        self.assertNotIn(
            "def list_files",
            source,
            "MCPClient must not have hardcoded list_files method.",
        )


if __name__ == "__main__":
    unittest.main()
