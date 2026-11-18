"""Unit Tests for Audit Layer (Operational and Compliance Logging).

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from datetime import datetime
import unittest

from runtime.audit import Audit


class TestAudit(unittest.TestCase):
    """Test suite verifying audit logging compliance, formatting, and failure queries."""

    def setUp(self) -> None:
        self.audit = Audit()

    def test_log_successful_execution_entry(self) -> None:
        """Verify successful task execution is logged with complete fields and ISO timestamp."""
        task = {"skill": "summarize_notes", "text": "Testing audit log"}
        tool_calls = [{"tool": "word_count", "args": {"text": "Testing audit log"}, "output": {"count": 3}}]
        result = {"status": "success", "word_count": 3}

        entry = self.audit.log(
            task=task,
            skill_name="summarize_notes",
            tool_calls=tool_calls,
            result=result,
            error=None,
            user="uday",
        )

        self.assertEqual(len(self.audit.get_entries()), 1)
        self.assertEqual(entry["user"], "uday")
        self.assertEqual(entry["skill_name"], "summarize_notes")
        self.assertEqual(entry["task"], task)
        self.assertEqual(entry["tool_calls"], tool_calls)
        self.assertEqual(entry["result"], result)
        self.assertIsNone(entry["error"])

        # Timestamp must be valid ISO format
        parsed_dt = datetime.fromisoformat(entry["timestamp"])
        self.assertIsNotNone(parsed_dt)

    def test_log_failed_execution_entry(self) -> None:
        """Verify failed task execution is logged with error string and result=None."""
        task = {"skill": "draft_email", "recipient": "Unknown Person"}
        error_msg = "Contact lookup failed: Contact 'Unknown Person' not found."

        entry = self.audit.log(
            task=task,
            skill_name="draft_email",
            tool_calls=[],
            result=None,
            error=error_msg,
            user="uday",
        )

        self.assertEqual(len(self.audit.get_entries()), 1)
        self.assertEqual(entry["user"], "uday")
        self.assertEqual(entry["skill_name"], "draft_email")
        self.assertIsNone(entry["result"])
        self.assertEqual(entry["error"], error_msg)

    def test_count_failures_isolates_by_user_and_skill(self) -> None:
        """Verify count_failures accurately counts errors per user/skill without cross-pollution."""
        # 2 failures for uday on draft_email
        self.audit.log({"t": 1}, "draft_email", [], error="Err 1", user="uday")
        self.audit.log({"t": 2}, "draft_email", [], error="Err 2", user="uday")

        # 1 success for uday on draft_email (must NOT be counted)
        self.audit.log({"t": 3}, "draft_email", [], result={"status": "ok"}, error=None, user="uday")

        # 1 failure for uday on summarize_notes (different skill - must NOT be counted)
        self.audit.log({"t": 4}, "summarize_notes", [], error="Word count error", user="uday")

        # 1 failure for priya on draft_email (different user - must NOT be counted)
        self.audit.log({"t": 5}, "draft_email", [], error="Priya err", user="priya")

        # Verify isolation
        self.assertEqual(self.audit.count_failures("uday", "draft_email"), 2)
        self.assertEqual(self.audit.count_failures("uday", "summarize_notes"), 1)
        self.assertEqual(self.audit.count_failures("priya", "draft_email"), 1)
        self.assertEqual(self.audit.count_failures("priya", "summarize_notes"), 0)

    def test_clear_audit_trail(self) -> None:
        """Verify clear() empties all logs."""
        self.audit.log({"t": 1}, "summarize_notes", [], result={"ok": True}, user="uday")
        self.assertEqual(len(self.audit.get_entries()), 1)
        self.audit.clear()
        self.assertEqual(len(self.audit.get_entries()), 0)


if __name__ == "__main__":
    unittest.main()
