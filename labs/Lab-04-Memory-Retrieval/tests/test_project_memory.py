"""
test_project_memory.py
======================
Unit and integration tests for Lab 4 – Memory and Retrieval: Project Memory.

Covers:
  - MemoryRecord initialization, validation, and serialization
  - ProjectMemory storage, topic-scoped retrieval, and permission controls
  - ProjectAssistant source tagging and short-term vs long-term memory separation
  - Conflict detection, resolution, and non-automatic overwrite enforcement
  - Assignment 1: Topic isolation (preventing cross-topic memory leakage)
  - Assignment 2: Configurable retention and staleness warnings
  - Input validation and malformed data handling
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

# Ensure Lab-04 root is on sys.path for direct test execution
_LAB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LAB_ROOT not in sys.path:
    sys.path.insert(0, _LAB_ROOT)

from agent.project_assistant import ProjectAssistant
from memory.memory_record import MemoryRecord
from memory.project_memory import ProjectMemory


class TestMemoryRecord(unittest.TestCase):
    """Tests for the MemoryRecord dataclass."""

    def test_record_creation_valid(self):
        """MemoryRecord properly initializes with valid fields."""
        rec = MemoryRecord(
            topic="database",
            fact="we chose PostgreSQL",
            date="2026-07-03",
            source="memory",
        )
        self.assertEqual(rec.topic, "database")
        self.assertEqual(rec.fact, "we chose PostgreSQL")
        self.assertEqual(rec.date, "2026-07-03")
        self.assertEqual(rec.source, "memory")

    def test_default_source_is_memory(self):
        """Default source value is 'memory'."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL")
        self.assertEqual(rec.source, "memory")

    def test_topic_normalization(self):
        """Topic is normalized to lowercase and stripped."""
        rec = MemoryRecord(topic="  DATABASE  ", fact="we chose PostgreSQL")
        self.assertEqual(rec.topic, "database")

    def test_serialization_to_dict(self):
        """to_dict produces expected dictionary."""
        rec = MemoryRecord(
            topic="hosting",
            fact="we chose AWS",
            date="2026-07-04",
            source="memory",
        )
        data = rec.to_dict()
        self.assertEqual(
            data,
            {
                "topic": "hosting",
                "fact": "we chose AWS",
                "date": "2026-07-04",
                "source": "memory",
            },
        )

    def test_deserialization_from_dict(self):
        """from_dict reconstructs an identical MemoryRecord."""
        raw = {
            "topic": "frontend",
            "fact": "we chose Next.js",
            "date": "2026-07-05",
            "source": "memory",
        }
        rec = MemoryRecord.from_dict(raw)
        self.assertEqual(rec.topic, "frontend")
        self.assertEqual(rec.fact, "we chose Next.js")
        self.assertEqual(rec.date, "2026-07-05")
        self.assertEqual(rec.source, "memory")

    def test_empty_topic_raises_error(self):
        """Empty or whitespace topic raises ValueError."""
        with self.assertRaises(ValueError):
            MemoryRecord(topic="", fact="some fact")
        with self.assertRaises(ValueError):
            MemoryRecord(topic="   ", fact="some fact")

    def test_empty_fact_raises_error(self):
        """Empty or whitespace fact raises ValueError."""
        with self.assertRaises(ValueError):
            MemoryRecord(topic="database", fact="")
        with self.assertRaises(ValueError):
            MemoryRecord(topic="database", fact="   ")


class TestProjectMemoryStorage(unittest.TestCase):
    """Tests for ProjectMemory storage, retrieval, and permission enforcement."""

    def setUp(self):
        self.mem = ProjectMemory()

    def test_authorized_write_by_team_lead(self):
        """team_lead can write to long-term memory."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL", date="2026-07-03")
        self.mem.write(rec, user_role="team_lead")
        stored = self.mem.retrieve("database")
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].fact, "we chose PostgreSQL")

    def test_unauthorized_write_by_member_raises_error(self):
        """member role raises PermissionError when writing to long-term memory."""
        rec = MemoryRecord(topic="database", fact="we're switching to SQLite")
        with self.assertRaises(PermissionError) as ctx:
            self.mem.write(rec, user_role="member")
        self.assertIn("Permission denied", str(ctx.exception))
        self.assertIn("member", str(ctx.exception))

    def test_unauthorized_write_by_lead_raises_error(self):
        """lead role is not authorized and raises PermissionError."""
        rec = MemoryRecord(topic="database", fact="we're switching to SQLite")
        with self.assertRaises(PermissionError) as ctx:
            self.mem.write(rec, user_role="lead")
        self.assertIn("Permission denied", str(ctx.exception))
        self.assertIn("lead", str(ctx.exception))

    def test_unauthorized_write_by_architect_raises_error(self):
        """architect role is not authorized and raises PermissionError."""
        rec = MemoryRecord(topic="database", fact="we're switching to SQLite")
        with self.assertRaises(PermissionError) as ctx:
            self.mem.write(rec, user_role="architect")
        self.assertIn("Permission denied", str(ctx.exception))
        self.assertIn("architect", str(ctx.exception))

    def test_unauthorized_write_by_arbitrary_role_raises_error(self):
        """Arbitrary unrecognized roles raise PermissionError."""
        rec = MemoryRecord(topic="database", fact="we're switching to SQLite")
        for bad_role in ("guest", "developer", "viewer", "qa_lead", ""):
            with self.assertRaises(PermissionError):
                self.mem.write(rec, user_role=bad_role)

    def test_unauthorized_write_does_not_mutate_store(self):
        """Failed write leaves memory completely untouched."""
        valid_rec = MemoryRecord(topic="database", fact="we chose PostgreSQL")
        self.mem.write(valid_rec, user_role="team_lead")

        bad_rec = MemoryRecord(topic="database", fact="we're switching to SQLite")
        with self.assertRaises(PermissionError):
            self.mem.write(bad_rec, user_role="member")

        stored = self.mem.retrieve("database")
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].fact, "we chose PostgreSQL")

    def test_empty_retrieval_for_unknown_topic(self):
        """Querying an unknown topic returns an empty list."""
        results = self.mem.retrieve("nonexistent_topic")
        self.assertEqual(results, [])

    def test_case_insensitive_retrieval(self):
        """Topic lookup is case-insensitive."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL")
        self.mem.write(rec, user_role="team_lead")
        self.assertEqual(len(self.mem.retrieve("DATABASE")), 1)
        self.assertEqual(len(self.mem.retrieve("Database")), 1)
        self.assertEqual(len(self.mem.retrieve("  database  ")), 1)

    def test_get_latest_record(self):
        """get_latest returns the most recent record among multiple entries."""
        rec1 = MemoryRecord(topic="database", fact="PostgreSQL v1", date="2026-07-01")
        rec2 = MemoryRecord(topic="database", fact="PostgreSQL v2", date="2026-07-03")
        self.mem.write(rec1, user_role="team_lead")
        self.mem.write(rec2, user_role="team_lead")
        latest = self.mem.get_latest("database")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.fact, "PostgreSQL v2")

    def test_get_latest_for_unknown_topic_is_none(self):
        """get_latest returns None if topic has no stored records."""
        self.assertIsNone(self.mem.get_latest("unknown"))

    def test_invalid_record_type_raises_type_error(self):
        """Passing non-MemoryRecord object to write raises TypeError."""
        with self.assertRaises(TypeError):
            self.mem.write("not a record", user_role="team_lead")  # type: ignore[arg-type]


class TestProjectAssistant(unittest.TestCase):
    """Tests for ProjectAssistant functionality, conflict detection, and answer logic."""

    def setUp(self):
        self.mem = ProjectMemory()
        self.assistant = ProjectAssistant(memory=self.mem)

    def test_source_tagged_answer_memory(self):
        """Answer for stored memory includes date and source tag [memory, dated YYYY-MM-DD]."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL", date="2026-07-03")
        self.mem.write(rec, user_role="team_lead")

        ans = self.assistant.answer("database", "What did we decide about the database?")
        self.assertEqual(ans["source"], "memory")
        self.assertIn("[memory, dated 2026-07-03]", ans["answer"])
        self.assertIn("we chose PostgreSQL", ans["answer"])
        self.assertIn("2026-07-03", ans["answer"])

    def test_session_state_separate_from_long_term_memory(self):
        """Short-term session facts do not mutate long-term memory."""
        self.assistant.set_session_fact("database", "benchmarking connection pool")
        # Long-term store must remain empty
        self.assertEqual(self.mem.retrieve("database"), [])

        ans = self.assistant.answer("database")
        self.assertEqual(ans["source"], "current_session")
        self.assertIn("[current_session]", ans["answer"])
        self.assertIn("benchmarking connection pool", ans["answer"])

    def test_combined_session_and_memory_answer(self):
        """When both exist, both sources are tagged and distinguished."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL", date="2026-07-03")
        self.mem.write(rec, user_role="team_lead")
        self.assistant.set_session_fact("database", "session note: testing read replicas")

        ans = self.assistant.answer("database")
        self.assertIn("[current_session]", ans["answer"])
        self.assertIn("[memory, dated 2026-07-03]", ans["answer"])

    def test_honest_answer_when_no_decision_exists(self):
        """Assistant explicitly states absence of stored decision (no fabrication)."""
        ans = self.assistant.answer("security")
        self.assertEqual(ans["source"], "none")
        self.assertIn("no stored decision", ans["answer"].lower())

    def test_conflict_detection_when_statement_differs(self):
        """Proposing a contradictory fact flags a conflict and asks for confirmation."""
        # Initial stored decision
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL", date="2026-07-03")
        self.mem.write(rec, user_role="team_lead")

        # Member proposes conflicting fact
        resp = self.assistant.receive_statement(
            topic="database",
            new_fact="we're switching to SQLite",
            user_role="member",
        )

        self.assertTrue(resp["conflict"])
        self.assertEqual(resp["stored"], "we chose PostgreSQL")
        self.assertEqual(resp["stored_date"], "2026-07-03")
        self.assertEqual(resp["new"], "we're switching to SQLite")
        self.assertIn("Conflict detected", resp["message"])
        self.assertFalse(resp["updated"])

    def test_no_automatic_overwrite_on_conflict(self):
        """A flagged conflict must NOT automatically overwrite the existing decision."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL", date="2026-07-03")
        self.mem.write(rec, user_role="team_lead")

        # Propose conflicting fact
        self.assistant.receive_statement(
            topic="database",
            new_fact="we're switching to SQLite",
            user_role="member",
        )

        # Original decision must remain intact
        latest = self.mem.get_latest("database")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.fact, "we chose PostgreSQL")

    def test_confirmed_update_by_team_lead_succeeds(self):
        """Authorized team_lead confirms and writes the updated decision."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL", date="2026-07-03")
        self.mem.write(rec, user_role="team_lead")

        # Confirm update
        confirm_resp = self.assistant.confirm_and_update(
            topic="database",
            new_fact="we're switching to SQLite",
            user_role="team_lead",
            date="2026-07-10",
        )
        self.assertTrue(confirm_resp["updated"])
        self.assertFalse(confirm_resp["conflict"])

        # Latest decision must now be the new one
        latest = self.mem.get_latest("database")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.fact, "we're switching to SQLite")
        self.assertEqual(latest.date, "2026-07-10")

    def test_confirmed_update_by_member_fails_permission(self):
        """Unauthorized member cannot confirm an update."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL", date="2026-07-03")
        self.mem.write(rec, user_role="team_lead")

        with self.assertRaises(PermissionError):
            self.assistant.confirm_and_update(
                topic="database",
                new_fact="we're switching to SQLite",
                user_role="member",
            )

    def test_unauthorized_conflict_confirmation_cannot_update_memory(self):
        """Unauthorized roles (lead, architect, guest) cannot update memory via confirmation."""
        rec = MemoryRecord(topic="database", fact="we chose PostgreSQL", date="2026-07-03")
        self.mem.write(rec, user_role="team_lead")

        # Flag a conflict first
        conflict_res = self.assistant.receive_statement(
            topic="database",
            new_fact="we're switching to SQLite",
            user_role="member",
        )
        self.assertTrue(conflict_res["conflict"])

        # Multiple unauthorized roles attempt to confirm update
        for unauthorized_role in ("lead", "architect", "member", "guest"):
            with self.assertRaises(PermissionError):
                self.assistant.confirm_and_update(
                    topic="database",
                    new_fact="we're switching to SQLite",
                    user_role=unauthorized_role,
                )

        # Verify original memory record remains completely unchanged
        stored_latest = self.mem.get_latest("database")
        self.assertIsNotNone(stored_latest)
        self.assertEqual(stored_latest.fact, "we chose PostgreSQL")
        self.assertEqual(stored_latest.date, "2026-07-03")


class TestAssignment1TopicIsolation(unittest.TestCase):
    """
    Assignment 1 tests:
    Verify that multiple stored topics remain strictly isolated
    and never leak into each other's retrieval results.
    """

    def setUp(self):
        self.mem = ProjectMemory()
        self.assistant = ProjectAssistant(memory=self.mem)

        # Store database decision
        self.mem.write(
            MemoryRecord(
                topic="database",
                fact="we chose PostgreSQL",
                date="2026-07-03",
            ),
            user_role="team_lead",
        )

        # Store hosting decision
        self.mem.write(
            MemoryRecord(
                topic="hosting",
                fact="we chose AWS ECS for container hosting",
                date="2026-07-04",
            ),
            user_role="team_lead",
        )

    def test_database_retrieval_contains_only_database(self):
        """Retrieving database records returns only database decisions."""
        db_records = self.mem.retrieve("database")
        self.assertEqual(len(db_records), 1)
        self.assertEqual(db_records[0].fact, "we chose PostgreSQL")
        # Ensure no hosting content
        self.assertNotIn("hosting", db_records[0].fact.lower())
        self.assertNotIn("aws", db_records[0].fact.lower())

    def test_hosting_retrieval_contains_only_hosting(self):
        """Retrieving hosting records returns only hosting decisions."""
        hosting_records = self.mem.retrieve("hosting")
        self.assertEqual(len(hosting_records), 1)
        self.assertEqual(hosting_records[0].fact, "we chose AWS ECS for container hosting")
        # Ensure no database content
        self.assertNotIn("postgresql", hosting_records[0].fact.lower())
        self.assertNotIn("database", hosting_records[0].fact.lower())

    def test_assistant_answer_isolation(self):
        """Assistant answer for database never leaks hosting information."""
        db_ans = self.assistant.answer("database")
        self.assertIn("PostgreSQL", db_ans["answer"])
        self.assertNotIn("AWS", db_ans["answer"])
        self.assertNotIn("ECS", db_ans["answer"])

        hosting_ans = self.assistant.answer("hosting")
        self.assertIn("AWS ECS", hosting_ans["answer"])
        self.assertNotIn("PostgreSQL", hosting_ans["answer"])


class TestAssignment2StalenessPolicy(unittest.TestCase):
    """
    Assignment 2 tests:
    Configurable retention policy, age calculation, and staleness warnings.
    """

    def setUp(self):
        # 90-day retention threshold
        self.mem = ProjectMemory(retention_days=90)
        self.assistant = ProjectAssistant(memory=self.mem)
        self.today = date(2026, 7, 20)

    def test_fresh_record_no_warning(self):
        """A record within retention_days (e.g. 15 days old) produces no warning."""
        fresh_date = (self.today - timedelta(days=15)).strftime("%Y-%m-%d")
        rec = MemoryRecord(
            topic="frontend",
            fact="we chose Next.js with TypeScript",
            date=fresh_date,
        )
        self.mem.write(rec, user_role="team_lead")

        is_stale, age = self.mem.check_staleness(rec, reference_date=self.today)
        self.assertFalse(is_stale)
        self.assertEqual(age, 15)

        ans = self.assistant.answer("frontend", reference_date=self.today)
        self.assertIsNone(ans["warning"])
        self.assertNotIn("Warning", ans["answer"])
        self.assertIn("Next.js", ans["answer"])

    def test_stale_record_triggers_warning(self):
        """A record older than retention_days (e.g. 180 days old) triggers warning."""
        stale_date = (self.today - timedelta(days=180)).strftime("%Y-%m-%d")
        rec = MemoryRecord(
            topic="architecture",
            fact="we chose monolithic architecture",
            date=stale_date,
        )
        self.mem.write(rec, user_role="team_lead")

        is_stale, age = self.mem.check_staleness(rec, reference_date=self.today)
        self.assertTrue(is_stale)
        self.assertEqual(age, 180)

        ans = self.assistant.answer("architecture", reference_date=self.today)
        self.assertIsNotNone(ans["warning"])
        self.assertIn("Warning: This decision is from 180 days ago", ans["warning"])
        self.assertIn("Warning", ans["answer"])
        self.assertIn("monolithic architecture", ans["answer"])

    def test_configurable_retention_days(self):
        """Changing retention threshold alters staleness classification."""
        # 30-day threshold
        strict_mem = ProjectMemory(retention_days=30)
        rec = MemoryRecord(topic="cache", fact="we chose Redis", date="2026-06-01")
        # On 2026-07-20, record is 49 days old -> stale under 30 days, fresh under 60 days
        is_stale_30, _ = strict_mem.check_staleness(rec, reference_date=self.today)
        self.assertTrue(is_stale_30)

        lenient_mem = ProjectMemory(retention_days=60)
        is_stale_60, _ = lenient_mem.check_staleness(rec, reference_date=self.today)
        self.assertFalse(is_stale_60)

    def test_disabled_retention_policy_never_stale(self):
        """If retention_days is None, staleness is never triggered."""
        unlimited_mem = ProjectMemory(retention_days=None)
        ancient_rec = MemoryRecord(topic="legacy", fact="old decision", date="2020-01-01")
        is_stale, _ = unlimited_mem.check_staleness(ancient_rec, reference_date=self.today)
        self.assertFalse(is_stale)


class TestInputValidation(unittest.TestCase):
    """Tests for edge cases and malformed inputs."""

    def setUp(self):
        self.assistant = ProjectAssistant()

    def test_empty_topic_answer(self):
        """Empty topic in answer query returns a safe guidance message."""
        res = self.assistant.answer("")
        self.assertEqual(res["source"], "none")

    def test_empty_topic_statement_raises(self):
        """receive_statement with empty topic raises ValueError."""
        with self.assertRaises(ValueError):
            self.assistant.receive_statement("", "some fact", "team_lead")

    def test_empty_fact_statement_raises(self):
        """receive_statement with empty fact raises ValueError."""
        with self.assertRaises(ValueError):
            self.assistant.receive_statement("database", "", "team_lead")

    def test_session_fact_empty_raises(self):
        """set_session_fact with empty strings raises ValueError."""
        with self.assertRaises(ValueError):
            self.assistant.set_session_fact("", "valid fact")
        with self.assertRaises(ValueError):
            self.assistant.set_session_fact("topic", "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

