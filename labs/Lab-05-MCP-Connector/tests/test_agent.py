"""Unit Tests for DataAssistant Agent.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
"""

import json
from pathlib import Path
import unittest

from agent.data_assistant import DataAssistant
from client.mcp_client import MCPClient
from server.mcp_server import MCPServer


class TestDataAssistant(unittest.TestCase):
    """Test suite for DataAssistant capability selection, execution, and tracing."""

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
        self.assistant = DataAssistant(self.client, caller_id="data_assistant")

    def test_base_request_1_read_file(self) -> None:
        """Verify Request 1 routes to read_file resource and produces grounded output."""
        res = self.assistant.process_request("Read the README file.")
        self.assertTrue(res["success"])
        self.assertEqual(res["capability"], "read_file")
        self.assertEqual(res["kind"], "resource")
        self.assertEqual(res["input"]["file_path"], "README.md")
        self.assertIn("Successfully read 'README.md'", res["output_summary"])
        self.assertIn("Campus Activities", res["final_answer"])

    def test_base_request_2_query_db(self) -> None:
        """Verify Request 2 routes to query_db tool and calculates accurate totals."""
        res = self.assistant.process_request("Show me the campus event signup counts.")
        self.assertTrue(res["success"])
        self.assertEqual(res["capability"], "query_db")
        self.assertEqual(res["kind"], "tool")
        self.assertIn("SELECT event, count FROM signups", res["input"]["sql"])

        # Verify factual accuracy without fabrication
        final = res["final_answer"]
        self.assertIn("AI Club Talk: 12", final)
        self.assertIn("Hackathon Kickoff: 9", final)
        self.assertIn("Robotics Demo: 15", final)
        self.assertIn("Total participants across all events: 36", final)

    def test_base_request_3_call_api(self) -> None:
        """Verify Request 3 routes to call_api tool with events_today endpoint."""
        res = self.assistant.process_request("Which events are happening today?")
        self.assertTrue(res["success"])
        self.assertEqual(res["capability"], "call_api")
        self.assertEqual(res["kind"], "tool")
        self.assertEqual(res["input"]["endpoint"], "events_today")

        final = res["final_answer"]
        self.assertIn("AI Club Talk", final)
        self.assertIn("Robotics Demo", final)
        self.assertIn("Auditorium Hall B", final)

    def test_assignment_1_list_files(self) -> None:
        """Verify Assignment 1 routes dynamically to list_files resource."""
        res = self.assistant.process_request("List the available files.")
        self.assertTrue(res["success"])
        self.assertEqual(res["capability"], "list_files")
        self.assertEqual(res["kind"], "resource")

        final = res["final_answer"]
        self.assertIn("README.md", final)
        self.assertIn("announcements.txt", final)

    def test_trace_generation_and_export(self) -> None:
        """Verify full execution traces are captured with all required audit fields."""
        self.assistant.process_request("Read the README file.")
        self.assistant.process_request("Show me the campus event signup counts.")

        traces = self.assistant.get_traces()
        self.assertEqual(len(traces), 2)

        for trace in traces:
            self.assertIn("step", trace)
            self.assertIn("timestamp", trace)
            self.assertIn("user_request", trace)
            self.assertIn("discovered_capabilities", trace)
            self.assertIn("selected_capability", trace)
            self.assertIn("selected_kind", trace)
            self.assertIn("selection_reason", trace)
            self.assertIn("tool_input", trace)
            self.assertIn("tool_output", trace)
            self.assertIn("success", trace)
            self.assertIn("output_summary", trace)
            self.assertIn("final_answer", trace)

        # Test JSON serialization
        exported = self.assistant.export_trace_json()
        parsed = json.loads(exported)
        self.assertEqual(len(parsed), 2)

    def test_unmatched_intent_graceful_handling(self) -> None:
        """Verify graceful error reporting when user request matches no capability."""
        res = self.assistant.process_request("Fly an autonomous drone across the campus soccer pitch.")
        self.assertFalse(res["success"])
        self.assertIsNone(res["capability"])
        self.assertIn("could not find an appropriate capability", res["final_answer"])


if __name__ == "__main__":
    unittest.main()
