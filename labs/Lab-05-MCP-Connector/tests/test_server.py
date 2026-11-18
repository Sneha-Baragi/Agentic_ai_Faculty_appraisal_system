"""Unit Tests for MCPServer and Backend Adapters.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
"""

import os
from pathlib import Path
import unittest

from server.capabilities import Capability
from server.mcp_server import MCPServer


class TestMCPServer(unittest.TestCase):
    """Test suite for MCPServer capability discovery, registry, and execution."""

    def setUp(self) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.safe_dir = self.base_dir / "safe_data"
        self.db_path = self.base_dir / "data" / "campus.db"
        self.server = MCPServer(
            safe_dir=self.safe_dir,
            db_path=self.db_path,
            include_assignment_1=True,
        )

    def test_manifest_contains_expected_capabilities(self) -> None:
        """Verify the server exposes all expected capabilities in its manifest."""
        manifest = self.server.list_capabilities()
        cap_names = {cap["name"] for cap in manifest}

        self.assertIn("read_file", cap_names)
        self.assertIn("query_db", cap_names)
        self.assertIn("call_api", cap_names)
        self.assertIn("list_files", cap_names)

        # Check classification into resource vs tool
        by_name = {cap["name"]: cap for cap in manifest}
        self.assertEqual(by_name["read_file"]["kind"], "resource")
        self.assertEqual(by_name["list_files"]["kind"], "resource")
        self.assertEqual(by_name["query_db"]["kind"], "tool")
        self.assertEqual(by_name["call_api"]["kind"], "tool")

    def test_get_capability_specification(self) -> None:
        """Verify contract retrieval for a specific capability."""
        cap = self.server.get_capability("query_db")
        self.assertIsNotNone(cap)
        self.assertEqual(cap["name"], "query_db")
        self.assertEqual(cap["kind"], "tool")
        self.assertIn("input_schema", cap)
        self.assertIn("output_schema", cap)
        self.assertIn("sql", cap["input_schema"]["properties"])

    def test_execute_read_file(self) -> None:
        """Verify successful reading of safe_data/README.md."""
        res = self.server.execute("read_file", file_path="README.md")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["file_name"], "README.md")
        self.assertIn("Campus Activities", res["content"])
        self.assertGreater(res["size_bytes"], 0)

    def test_execute_query_db(self) -> None:
        """Verify querying signups from SQLite database."""
        res = self.server.execute(
            "query_db",
            sql="SELECT event, count FROM signups ORDER BY count DESC;",
            caller_id="data_assistant",
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["row_count"], 3)
        rows = res["rows"]
        # Top event should be Robotics Demo with 15
        self.assertEqual(rows[0]["event"], "Robotics Demo")
        self.assertEqual(rows[0]["count"], 15)

    def test_execute_call_api_events_today(self) -> None:
        """Verify deterministic API response for events_today endpoint."""
        res = self.server.execute("call_api", endpoint="events_today")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["endpoint"], "events_today")
        data = res["data"]
        self.assertEqual(data["total_events"], 2)
        event_names = [e["event"] for e in data["events"]]
        self.assertIn("AI Club Talk", event_names)
        self.assertIn("Robotics Demo", event_names)

    def test_execute_list_files(self) -> None:
        """Verify Assignment 1 list_files capability execution."""
        res = self.server.execute("list_files", subdir="")
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["file_count"], 2)
        file_names = {f["name"] for f in res["files"]}
        self.assertIn("README.md", file_names)
        self.assertIn("announcements.txt", file_names)

    def test_unknown_capability_rejection(self) -> None:
        """Verify server returns UNKNOWN_CAPABILITY for unregistered capability."""
        res = self.server.execute("non_existent_capability")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "UNKNOWN_CAPABILITY")

    def test_dynamic_register_and_unregister(self) -> None:
        """Verify dynamic capability registration and unregistration on the server."""
        dummy_cap = Capability(
            name="echo_test",
            kind="tool",
            description="Echoes input",
            input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
            output_schema={"type": "object"},
            handler_name="echo_test",
        )
        self.server.register_capability(
            dummy_cap, handler=lambda msg="": {"status": "success", "echo": msg}
        )

        # Confirm it appears in list_capabilities
        caps = {c["name"] for c in self.server.list_capabilities()}
        self.assertIn("echo_test", caps)

        # Test execution
        res = self.server.execute("echo_test", msg="Hello MCP")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["echo"], "Hello MCP")

        # Unregister
        removed = self.server.unregister_capability("echo_test")
        self.assertTrue(removed)
        self.assertNotIn("echo_test", {c["name"] for c in self.server.list_capabilities()})


if __name__ == "__main__":
    unittest.main()
