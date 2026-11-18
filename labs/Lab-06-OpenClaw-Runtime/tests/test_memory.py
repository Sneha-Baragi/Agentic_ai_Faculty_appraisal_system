"""Unit Tests for Memory Layer (Per-User Scoped Memory).

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

import unittest

from runtime.memory import Memory


class TestMemory(unittest.TestCase):
    """Test suite verifying per-user scoped memory isolation and persistence."""

    def setUp(self) -> None:
        self.memory = Memory()

    def test_scope_creates_empty_dict_for_new_user(self) -> None:
        """Verify scope() creates a new empty dictionary for an uninitialized user."""
        scope_uday = self.memory.scope("uday")
        self.assertIsInstance(scope_uday, dict)
        self.assertEqual(len(scope_uday), 0)

    def test_scope_persistence_for_same_user(self) -> None:
        """Verify scope() returns the same mutable dict for repeated calls."""
        scope_1 = self.memory.scope("uday")
        scope_1["last_note_length"] = 8

        scope_2 = self.memory.scope("uday")
        self.assertEqual(scope_2["last_note_length"], 8)
        self.assertIs(scope_1, scope_2)

    def test_strict_isolation_between_different_users(self) -> None:
        """Verify data stored in one user's scope does not leak into another's."""
        uday_scope = self.memory.scope("uday")
        priya_scope = self.memory.scope("priya")

        uday_scope["secret_key"] = "uday_val_123"
        uday_scope["last_note_length"] = 12

        self.assertNotIn("secret_key", priya_scope)
        self.assertNotIn("last_note_length", priya_scope)

        priya_scope["secret_key"] = "priya_val_456"
        self.assertEqual(uday_scope["secret_key"], "uday_val_123")
        self.assertEqual(priya_scope["secret_key"], "priya_val_456")

    def test_get_and_set_convenience_methods(self) -> None:
        """Verify get, set, and has helpers operate on the correct user scope."""
        self.memory.set("uday", "draft_count", 3)
        self.assertTrue(self.memory.has("uday", "draft_count"))
        self.assertEqual(self.memory.get("uday", "draft_count"), 3)

        # Non-existent key with default
        self.assertFalse(self.memory.has("uday", "non_existent"))
        self.assertEqual(self.memory.get("uday", "non_existent", "default_val"), "default_val")

        # Other user has no key
        self.assertFalse(self.memory.has("priya", "draft_count"))
        self.assertIsNone(self.memory.get("priya", "draft_count"))

    def test_clear_single_user_and_all_users(self) -> None:
        """Verify clear() clears target user without affecting others, and clears all when None."""
        self.memory.set("uday", "k1", "v1")
        self.memory.set("priya", "k2", "v2")

        # Clear uday only
        self.memory.clear("uday")
        self.assertFalse(self.memory.has("uday", "k1"))
        self.assertTrue(self.memory.has("priya", "k2"))

        # Clear all
        self.memory.clear()
        self.assertFalse(self.memory.has("priya", "k2"))
        self.assertEqual(len(self.memory.all_users()), 0)

    def test_invalid_user_identifiers_raise_error(self) -> None:
        """Verify empty or non-string user identifiers raise ValueError."""
        with self.assertRaises(ValueError):
            self.memory.scope("")

        with self.assertRaises(ValueError):
            self.memory.scope("   ")


if __name__ == "__main__":
    unittest.main()
