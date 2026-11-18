"""Unit Tests for Core Runtime Loop, Extensibility, and Skills.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

import inspect
import unittest

from runtime.agent_runtime import receive_task, run_task, select_skill
from runtime.audit import Audit
from runtime.memory import Memory
from skills import (
    SKILL_REGISTRY,
    SummarizeNotesSkill,
    DraftEmailSkill,
    TranslateTextSkill,
    register_skill,
    reset_skill_registry,
)


class TestAgentRuntime(unittest.TestCase):
    """Test suite verifying generic runtime loop, dynamic registry, and skill execution."""

    def setUp(self) -> None:
        reset_skill_registry()
        self.memory = Memory()
        self.audit = Audit()

    def tearDown(self) -> None:
        reset_skill_registry()

    def test_select_skill_from_dict_and_string(self) -> None:
        """Verify select_skill identifies registered skills from diverse task formats."""
        # Dict with explicit skill key
        self.assertEqual(
            select_skill({"skill": "summarize_notes", "text": "Sample text"}),
            "summarize_notes",
        )
        self.assertEqual(
            select_skill({"action": "draft_email", "recipient": "Dr. Meena"}),
            "draft_email",
        )

        # String matching
        self.assertEqual(select_skill("summarize_notes"), "summarize_notes")
        self.assertEqual(select_skill("Please execute draft_email now"), "draft_email")

        # Unknown skill returns None
        self.assertIsNone(select_skill({"skill": "fly_drone"}))
        self.assertIsNone(select_skill("unrecognized request"))

    def test_run_task_summarize_notes_success(self) -> None:
        """Verify Run 1: summarize_notes calculates word count and stores length in memory."""
        task = {
            "skill": "summarize_notes",
            "text": "Agentic AI systems combine goals tools skills memory",
        }
        result = run_task(task=task, user="uday", memory=self.memory, audit=self.audit)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["word_count"], 8)
        self.assertIn("Summary stub: note has 8 words.", result["summary"])

        # Verify user scoped memory was populated
        uday_mem = self.memory.scope("uday")
        self.assertEqual(uday_mem["last_note_length"], 8)

        # Verify audit log recorded execution
        entries = self.audit.get_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["skill_name"], "summarize_notes")
        self.assertEqual(entries[0]["user"], "uday")
        self.assertIsNone(entries[0]["error"])
        self.assertEqual(entries[0]["tool_calls"][0]["tool"], "word_count")

    def test_run_task_draft_email_success(self) -> None:
        """Verify Run 2: draft_email retrieves Dr. Meena contact and returns draft."""
        task = {
            "skill": "draft_email",
            "recipient": "Dr. Meena",
            "subject": "Lab guide review",
        }
        result = run_task(task=task, user="uday", memory=self.memory, audit=self.audit)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["email"], "meena@example.edu")
        self.assertIn("To: meena@example.edu", result["draft"])
        self.assertIn("Subject: Lab guide review", result["draft"])

        # Check memory
        uday_mem = self.memory.scope("uday")
        self.assertEqual(uday_mem["last_drafted_email"], "meena@example.edu")

        # Check audit
        entries = self.audit.get_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["skill_name"], "draft_email")
        self.assertEqual(entries[0]["tool_calls"][0]["tool"], "contact_lookup")

    def test_run_task_draft_email_failure_raises_and_logs(self) -> None:
        """Verify Run 3: unknown contact raises ValueError and records error in audit log."""
        task = {
            "skill": "draft_email",
            "recipient": "Unknown Person",
            "subject": "Hello",
        }
        with self.assertRaises(ValueError) as ctx:
            run_task(task=task, user="uday", memory=self.memory, audit=self.audit)

        self.assertIn("not found", str(ctx.exception).lower())

        # Audit log must contain the failed execution
        entries = self.audit.get_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["skill_name"], "draft_email")
        self.assertEqual(entries[0]["user"], "uday")
        self.assertIsNotNone(entries[0]["error"])
        self.assertIn("Unknown Person", entries[0]["error"])

    def test_run_task_unknown_skill_raises_and_logs(self) -> None:
        """Verify submitting an unmapped skill raises ValueError and logs error."""
        task = {"skill": "unsupported_magic_skill", "data": 123}
        with self.assertRaises(ValueError) as ctx:
            run_task(task=task, user="uday", memory=self.memory, audit=self.audit)

        self.assertIn("unregistered skill", str(ctx.exception).lower())
        self.assertEqual(len(self.audit.get_entries()), 1)
        self.assertIsNotNone(self.audit.get_entries()[0]["error"])

    def test_extensibility_add_third_skill_without_runtime_rewrite(self) -> None:
        """Verify Run 4: TranslateTextSkill can be registered and run without modifying runtime code.

        Critical grading requirement:
        Adding TranslateTextSkill requires ONLY registering the class in SKILL_REGISTRY;
        neither run_task() nor select_skill() can be modified.
        """
        # Confirm translate_text is initially absent
        self.assertNotIn("translate_text", SKILL_REGISTRY)

        # Register dynamically
        register_skill("translate_text", TranslateTextSkill)
        self.assertIn("translate_text", SKILL_REGISTRY)

        # Task definition
        task = {
            "skill": "translate_text",
            "text": "Hello, team",
            "target_language": "Kannada",
        }

        # Verify select_skill picks it up dynamically
        matched_skill = select_skill(task)
        self.assertEqual(matched_skill, "translate_text")

        # Verify run_task executes it cleanly
        result = run_task(task=task, user="uday", memory=self.memory, audit=self.audit)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["target_language"], "Kannada")
        self.assertEqual(result["translated_text"], "[translated to Kannada] Hello, team")

        # Verify no hardcoded strings exist in run_task or select_skill source
        run_source = inspect.getsource(run_task)
        select_source = inspect.getsource(select_skill)
        self.assertNotIn("translate_text", run_source)
        self.assertNotIn("TranslateTextSkill", run_source)
        self.assertNotIn("translate_text", select_source)
        self.assertNotIn("TranslateTextSkill", select_source)

    def test_receive_task_delegates_to_run_task(self) -> None:
        """Verify public interface receive_task delegates execution properly."""
        task = {
            "skill": "summarize_notes",
            "text": "Testing receive_task entry point",
        }
        res = receive_task(
            task=task,
            user="uday",
            memory=self.memory,
            audit=self.audit,
            enable_rate_limiting=False,
            enable_escalation=False,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["word_count"], 4)


if __name__ == "__main__":
    unittest.main()
