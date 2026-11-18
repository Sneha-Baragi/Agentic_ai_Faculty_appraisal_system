"""Unit Tests for Assignment 2: Escalate After Two Failures.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Assignment: 2 - Escalate After Two Failures
"""

import unittest

from runtime.agent_runtime import receive_task
from runtime.audit import Audit
from runtime.memory import Memory
from skills import reset_skill_registry


class TestFailureEscalation(unittest.TestCase):
    """Test suite verifying failure escalation to human supervisor after 2 failures."""

    def setUp(self) -> None:
        reset_skill_registry()
        self.memory = Memory()
        self.audit = Audit()
        self.failing_task = {
            "skill": "draft_email",
            "recipient": "Unknown Ghost Contact",
            "subject": "Important Notice",
        }

    def test_first_and_second_failures_execute_and_are_logged(self) -> None:
        """Verify first 2 attempts execute the skill, fail, and log error in audit trail."""
        # 1st failure
        with self.assertRaises(ValueError):
            receive_task(
                task=self.failing_task,
                user="uday",
                memory=self.memory,
                audit=self.audit,
                enable_rate_limiting=False,
                enable_escalation=True,
            )

        self.assertEqual(self.audit.count_failures("uday", "draft_email"), 1)

        # 2nd failure
        with self.assertRaises(ValueError):
            receive_task(
                task=self.failing_task,
                user="uday",
                memory=self.memory,
                audit=self.audit,
                enable_rate_limiting=False,
                enable_escalation=True,
            )

        self.assertEqual(self.audit.count_failures("uday", "draft_email"), 2)

    def test_third_attempt_escalates_without_executing_skill(self) -> None:
        """Verify 3rd attempt returns structured escalation response and does not run skill."""
        # Cause 2 failures
        for _ in range(2):
            try:
                receive_task(
                    task=self.failing_task,
                    user="uday",
                    memory=self.memory,
                    audit=self.audit,
                    enable_rate_limiting=False,
                )
            except ValueError:
                pass

        self.assertEqual(self.audit.count_failures("uday", "draft_email"), 2)

        # 3rd attempt - must NOT raise ValueError, must return structured escalation response
        res = receive_task(
            task=self.failing_task,
            user="uday",
            memory=self.memory,
            audit=self.audit,
            enable_rate_limiting=False,
            enable_escalation=True,
        )

        self.assertEqual(res["status"], "escalated")
        self.assertEqual(res["skill"], "draft_email")
        self.assertEqual(res["user"], "uday")
        self.assertIn("failed twice", res["reason"])

        # Tool calls for the 3rd attempt must be empty (skill was NOT executed)
        entries = self.audit.get_entries()
        self.assertEqual(len(entries), 3)
        third_entry = entries[-1]
        self.assertEqual(third_entry["tool_calls"], [])
        self.assertEqual(third_entry["result"]["status"], "escalated")

    def test_different_user_is_not_affected_by_failures(self) -> None:
        """Verify failures accumulated by user A do not escalate user B."""
        # 2 failures for uday
        for _ in range(2):
            try:
                receive_task(
                    task=self.failing_task,
                    user="uday",
                    memory=self.memory,
                    audit=self.audit,
                    enable_rate_limiting=False,
                )
            except ValueError:
                pass

        # priya attempts valid draft_email for Dr. Meena - must succeed
        valid_task = {
            "skill": "draft_email",
            "recipient": "Dr. Meena",
            "subject": "Collaboration",
        }
        res_priya = receive_task(
            task=valid_task,
            user="priya",
            memory=self.memory,
            audit=self.audit,
            enable_rate_limiting=False,
            enable_escalation=True,
        )
        self.assertEqual(res_priya["status"], "success")
        self.assertEqual(res_priya["email"], "meena@example.edu")

    def test_different_skill_has_independent_failure_count(self) -> None:
        """Verify failures in draft_email do not escalate summarize_notes."""
        # 2 failures for uday on draft_email
        for _ in range(2):
            try:
                receive_task(
                    task=self.failing_task,
                    user="uday",
                    memory=self.memory,
                    audit=self.audit,
                    enable_rate_limiting=False,
                )
            except ValueError:
                pass

        # uday runs summarize_notes - must succeed, NOT escalate
        summary_task = {
            "skill": "summarize_notes",
            "text": "Summarize this note without escalation",
        }
        res = receive_task(
            task=summary_task,
            user="uday",
            memory=self.memory,
            audit=self.audit,
            enable_rate_limiting=False,
            enable_escalation=True,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["word_count"], 5)

    def test_successful_runs_do_not_increase_failure_count(self) -> None:
        """Verify successful runs do not count towards the 2-failure threshold."""
        # 1 failure
        try:
            receive_task(
                task=self.failing_task,
                user="uday",
                memory=self.memory,
                audit=self.audit,
                enable_rate_limiting=False,
            )
        except ValueError:
            pass

        self.assertEqual(self.audit.count_failures("uday", "draft_email"), 1)

        # 1 success on valid contact
        valid_task = {
            "skill": "draft_email",
            "recipient": "Dr. Meena",
            "subject": "Greetings",
        }
        receive_task(
            task=valid_task,
            user="uday",
            memory=self.memory,
            audit=self.audit,
            enable_rate_limiting=False,
        )

        # Failure count must STILL be exactly 1
        self.assertEqual(self.audit.count_failures("uday", "draft_email"), 1)


if __name__ == "__main__":
    unittest.main()
