"""Unit Tests for Assignment 1: Per-User Session Rate Limiting.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Assignment: 1 - Add Per-User Rate Limiting
"""

import unittest

from runtime.agent_runtime import (
    RateLimitExceededError,
    RateLimiter,
    receive_task,
)
from runtime.audit import Audit
from runtime.memory import Memory
from skills import reset_skill_registry


class TestRateLimiting(unittest.TestCase):
    """Test suite verifying per-user task quotas (max 3 per session) and rejection behavior."""

    def setUp(self) -> None:
        reset_skill_registry()
        self.memory = Memory()
        self.audit = Audit()
        self.limiter = RateLimiter(max_tasks=3)

    def test_first_three_tasks_accepted(self) -> None:
        """Verify user can successfully execute up to 3 tasks in a session."""
        for i in range(1, 4):
            task = {
                "skill": "summarize_notes",
                "text": f"Note content for attempt {i}",
            }
            res = receive_task(
                task=task,
                user="uday",
                memory=self.memory,
                audit=self.audit,
                rate_limiter=self.limiter,
                enable_rate_limiting=True,
            )
            self.assertEqual(res["status"], "success")

        self.assertEqual(self.limiter.get_count("uday"), 3)

    def test_fourth_task_from_same_user_rejected(self) -> None:
        """Verify the 4th task submitted by the same user is rejected with a clear error."""
        # Execute 3 tasks
        for i in range(3):
            receive_task(
                task={"skill": "summarize_notes", "text": "Valid note"},
                user="uday",
                memory=self.memory,
                audit=self.audit,
                rate_limiter=self.limiter,
            )

        # 4th task attempt
        fourth_task = {
            "skill": "summarize_notes",
            "text": "This fourth task must be blocked",
        }
        res = receive_task(
            task=fourth_task,
            user="uday",
            memory=self.memory,
            audit=self.audit,
            rate_limiter=self.limiter,
            enable_rate_limiting=True,
            raise_on_rate_limit=False,
        )

        self.assertEqual(res["status"], "rejected")
        self.assertIn("Rate limit exceeded", res["error"])
        self.assertEqual(res["task_count"], 3)
        self.assertEqual(res["limit"], 3)

    def test_rejected_task_does_not_execute_skill(self) -> None:
        """Verify rejected 4th task does not invoke the skill or modify user memory."""
        # Execute 3 tasks with note lengths 2, 4, 6
        lengths = [2, 4, 6]
        for l in lengths:
            receive_task(
                task={"skill": "summarize_notes", "text": "word " * l},
                user="uday",
                memory=self.memory,
                audit=self.audit,
                rate_limiter=self.limiter,
            )

        self.assertEqual(self.memory.get("uday", "last_note_length"), 6)

        # 4th task with 10 words
        receive_task(
            task={"skill": "summarize_notes", "text": "word " * 10},
            user="uday",
            memory=self.memory,
            audit=self.audit,
            rate_limiter=self.limiter,
            raise_on_rate_limit=False,
        )

        # Memory must STILL reflect length 6 from 3rd task, not 10
        self.assertEqual(self.memory.get("uday", "last_note_length"), 6)

    def test_rejection_is_recorded_in_audit_log(self) -> None:
        """Verify rate limit rejection is recorded in the audit trail."""
        for _ in range(3):
            receive_task(
                task={"skill": "summarize_notes", "text": "Allowed note"},
                user="uday",
                memory=self.memory,
                audit=self.audit,
                rate_limiter=self.limiter,
            )

        entries_before = len(self.audit.get_entries())

        # 4th task rejected
        receive_task(
            task={"skill": "summarize_notes", "text": "Rejected note"},
            user="uday",
            memory=self.memory,
            audit=self.audit,
            rate_limiter=self.limiter,
            raise_on_rate_limit=False,
        )

        entries_after = self.audit.get_entries()
        self.assertEqual(len(entries_after), entries_before + 1)
        last_entry = entries_after[-1]
        self.assertEqual(last_entry["user"], "uday")
        self.assertIsNotNone(last_entry["error"])
        self.assertIn("Rate limit exceeded", last_entry["error"])

    def test_different_users_have_independent_rate_limits(self) -> None:
        """Verify exhausting one user's quota does not impact another user."""
        # Exhaust uday's 3 tasks
        for _ in range(3):
            receive_task(
                task={"skill": "summarize_notes", "text": "Uday's note"},
                user="uday",
                memory=self.memory,
                audit=self.audit,
                rate_limiter=self.limiter,
            )

        # uday is blocked
        res_uday = receive_task(
            task={"skill": "summarize_notes", "text": "Uday's 4th"},
            user="uday",
            memory=self.memory,
            audit=self.audit,
            rate_limiter=self.limiter,
            raise_on_rate_limit=False,
        )
        self.assertEqual(res_uday["status"], "rejected")

        # priya can still execute normally
        res_priya = receive_task(
            task={"skill": "summarize_notes", "text": "Priya's 1st note"},
            user="priya",
            memory=self.memory,
            audit=self.audit,
            rate_limiter=self.limiter,
        )
        self.assertEqual(res_priya["status"], "success")
        self.assertEqual(self.limiter.get_count("priya"), 1)

    def test_rate_limit_resets_for_new_session(self) -> None:
        """Verify limiter.reset() clears session state and allows tasks again."""
        for _ in range(3):
            self.limiter.record_attempt("uday")
        self.assertFalse(self.limiter.is_allowed("uday"))

        # Reset session
        self.limiter.reset()
        self.assertTrue(self.limiter.is_allowed("uday"))
        self.assertEqual(self.limiter.get_count("uday"), 0)

    def test_raise_on_rate_limit_flag(self) -> None:
        """Verify RateLimitExceededError is raised when raise_on_rate_limit is True."""
        for _ in range(3):
            self.limiter.record_attempt("uday")

        with self.assertRaises(RateLimitExceededError):
            receive_task(
                task={"skill": "summarize_notes", "text": "Will raise"},
                user="uday",
                memory=self.memory,
                audit=self.audit,
                rate_limiter=self.limiter,
                raise_on_rate_limit=True,
            )


if __name__ == "__main__":
    unittest.main()
