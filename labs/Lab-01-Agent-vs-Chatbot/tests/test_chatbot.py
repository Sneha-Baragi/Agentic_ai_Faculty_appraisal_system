"""Unit Tests for Conventional Study Planning Chatbot (Lab 1).

Validates that the chatbot exhibits conventional non-agentic behavior:
- Generates a static text response.
- Performs zero autonomous tool calls.
- Does not maintain structured goal state or planning loops.
- Overlooks external timetable conflicts and unverified assumptions.
"""

import os
import sys
import unittest

# Ensure the Lab 1 root is in python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LAB_ROOT = os.path.dirname(CURRENT_DIR)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from chatbot.chatbot import StudyChatbot


class TestStudyChatbot(unittest.TestCase):
    """Test suite verifying conventional chatbot characteristics."""

    def setUp(self) -> None:
        self.bot = StudyChatbot()

    def test_chatbot_generates_response(self) -> None:
        """Verify the chatbot returns a text string response."""
        prompt = "Create a study plan for Data Structures and Operating Systems."
        response = self.bot.respond(prompt)
        self.assertIsInstance(response, str)
        self.assertIn("ConventionalStudyBot Response", response)
        self.assertIn("Monday", response)

    def test_chatbot_does_not_call_tools(self) -> None:
        """Verify the conventional chatbot invokes zero external tools."""
        self.assertEqual(self.bot.tool_calls_count, 0)
        self.bot.respond("Plan my week for 3 subjects.")
        self.assertEqual(self.bot.tool_calls_count, 0)

        capabilities = self.bot.inspect_capabilities()
        self.assertFalse(capabilities["autonomous_loop"])
        self.assertFalse(capabilities["maintains_structured_state"])
        self.assertEqual(capabilities["tool_calls_count"], 0)

    def test_chatbot_no_state_preservation(self) -> None:
        """Verify the chatbot does not maintain persistent schedule structures."""
        self.bot.respond("Initial request for Data Structures.")
        self.assertFalse(self.bot.maintains_structured_state)

        # On feedback, it generates a fresh generic text response without state mutation
        feedback_response = self.bot.respond("Move Tuesday's session to the evening.")
        self.assertIn("generated this fresh response from scratch", feedback_response)
        self.assertFalse(self.bot.inspect_capabilities()["can_mutate_plan_in_place"])

    def test_chatbot_unverified_assumptions(self) -> None:
        """Verify chatbot schedules across all 7 days regardless of hidden calendar conflicts."""
        response = self.bot.respond("Need a study plan.")
        # Chatbot naively allocates Wednesday and Sunday without calendar verification
        self.assertIn("Wednesday", response)
        self.assertIn("Sunday", response)
        self.assertIn("Assumptions made by chatbot", response)


if __name__ == "__main__":
    unittest.main()

