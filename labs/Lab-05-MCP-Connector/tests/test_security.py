"""Security and Permission Boundary Unit Tests.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Assignment 2: Directory Traversal Protection & Read-Only Tool Enforcement
"""

from pathlib import Path
import unittest

from agent.data_assistant import DataAssistant
from client.mcp_client import MCPClient
from server.api_tool import LocalApiTool
from server.database_tool import DatabaseTool
from server.file_resource import FileResource
from server.mcp_server import MCPServer


class TestSecurityBoundaries(unittest.TestCase):
    """Test suite for permission boundaries, path traversal prevention, and read-only database locks."""

    def setUp(self) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.safe_dir = self.base_dir / "safe_data"
        self.db_path = self.base_dir / "data" / "campus.db"

        self.file_resource = FileResource(safe_dir=self.safe_dir)
        self.db_tool = DatabaseTool(db_path=self.db_path)
        self.api_tool = LocalApiTool()

        self.server = MCPServer(
            safe_dir=self.safe_dir,
            db_path=self.db_path,
            include_assignment_1=True,
        )
        self.client = MCPClient(self.server)
        self.assistant = DataAssistant(self.client, caller_id="data_assistant")

    # -------------------------------------------------------------------------
    # ASSIGNMENT 2: FILE RESOURCE PERMISSION BOUNDARY & PATH TRAVERSAL TESTS
    # -------------------------------------------------------------------------

    def test_parent_traversal_blocked(self) -> None:
        """Verify relative parent traversal (../../backend/.env) is blocked."""
        res = self.file_resource.read_file("../../backend/.env")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "PERMISSION_DENIED")
        self.assertIn("Access denied", res["message"])

    def test_relative_root_traversal_blocked(self) -> None:
        """Verify relative traversal to Lab README (../README.md) is blocked."""
        res = self.file_resource.read_file("../README.md")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "PERMISSION_DENIED")

    def test_windows_absolute_path_blocked(self) -> None:
        """Verify Windows absolute paths outside safe_data boundary are blocked."""
        res = self.file_resource.read_file("C:\\Windows\\win.ini")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "PERMISSION_DENIED")

    def test_unix_root_path_blocked(self) -> None:
        """Verify Unix-style absolute paths outside safe boundary are blocked."""
        res = self.file_resource.read_file("/some/unauthorized/file.txt")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "PERMISSION_DENIED")

    def test_nonexistent_file_inside_safe_boundary(self) -> None:
        """Verify non-existent file inside safe directory returns FILE_NOT_FOUND, not PERMISSION_DENIED."""
        res = self.file_resource.read_file("non_existent_file.txt")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "FILE_NOT_FOUND")

    def test_error_message_does_not_disclose_system_paths(self) -> None:
        """Verify error messages do not leak absolute server directory paths."""
        res = self.file_resource.read_file("../../backend/.env")
        # Ensure full project path is not leaked in the client-facing message
        self.assertNotIn(str(self.base_dir), res["message"])

    # -------------------------------------------------------------------------
    # DATABASE TOOL: READ-ONLY & AUTHORIZATION ENFORCEMENT
    # -------------------------------------------------------------------------

    def test_unauthorized_database_caller_rejected(self) -> None:
        """Verify callers without matching authorized token are rejected."""
        res = self.db_tool.query(
            "SELECT * FROM signups;",
            caller_id="unauthorized_rogue_agent",
        )
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "UNAUTHORIZED_CALLER")

    def test_sql_write_keywords_rejected(self) -> None:
        """Verify modification statements (INSERT, UPDATE, DELETE, DROP, ALTER) are rejected."""
        malicious_queries = [
            "INSERT INTO signups (event, count) VALUES ('Hacked', 999);",
            "UPDATE signups SET count = 0 WHERE event = 'AI Club Talk';",
            "DELETE FROM signups WHERE count > 0;",
            "DROP TABLE signups;",
            "ALTER TABLE signups ADD COLUMN backdoor TEXT;",
            "CREATE TABLE test (id INT);",
            "TRUNCATE TABLE signups;",
        ]
        for sql in malicious_queries:
            with self.subTest(sql=sql):
                res = self.db_tool.query(sql, caller_id="data_assistant")
                self.assertEqual(res["status"], "error")
                self.assertEqual(res["error_code"], "PERMISSION_DENIED")
                self.assertIn("Read-only access violation", res["message"])

    def test_stacked_sql_injection_rejected(self) -> None:
        """Verify stacked queries containing semicolon separators are rejected."""
        stacked_query = "SELECT * FROM signups; DROP TABLE signups;"
        res = self.db_tool.query(stacked_query, caller_id="data_assistant")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "PERMISSION_DENIED")

    # -------------------------------------------------------------------------
    # API TOOL: ENDPOINT WHITELIST ENFORCEMENT
    # -------------------------------------------------------------------------

    def test_unknown_api_endpoint_rejected(self) -> None:
        """Verify requesting undefined API endpoint returns ENDPOINT_NOT_FOUND."""
        res = self.api_tool.call_api("admin_delete_records")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "ENDPOINT_NOT_FOUND")

    # -------------------------------------------------------------------------
    # AGENT END-TO-END SECURITY HANDLING
    # -------------------------------------------------------------------------

    def test_agent_handles_path_traversal_gracefully(self) -> None:
        """Verify agent handles an adversarial path traversal request gracefully."""
        res = self.assistant.process_request("Read the file ../../backend/.env")
        self.assertFalse(res["success"])
        self.assertEqual(res["capability"], "read_file")
        self.assertEqual(res["output"]["error_code"], "PERMISSION_DENIED")
        self.assertIn("Access Denied", res["final_answer"])
        self.assertIn("PERMISSION_DENIED", res["final_answer"])


if __name__ == "__main__":
    unittest.main()
