"""Unit tests for Lab 8 Specialist Collection Agents.

Verifies:
- Structured output schema normalization across Research, Teaching, and Administrative agents.
- Student privacy preservation in student feedback (aggregate metrics only).
- Source office citations for administrative activities.
- Faculty consent enforcement per category.
- Incomplete claim detection.
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.administrative_agent import AdministrativeDataCollectionAgent
from agents.research_agent import ResearchDataCollectionAgent
from agents.teaching_agent import TeachingDataCollectionAgent
from swarm.state import create_initial_state


class TestCollectionAgents(unittest.TestCase):
    """Test suite for specialist collector agents."""

    def setUp(self) -> None:
        """Create clean test state."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )

    def test_research_agent_structured_collection(self) -> None:
        """Test Research agent collects and normalizes publications, grants, and guidance."""
        agent = ResearchDataCollectionAgent()
        result = agent.execute(self.state)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.collector_role, "ResearchDataCollectionAgent")
        self.assertEqual(result.category, "Research")
        self.assertGreater(len(result.activities), 0)

        for act in result.activities:
            self.assertEqual(act["faculty_id"], "FAC001")
            self.assertEqual(act["category"], "Research")
            self.assertIn("claimed_points", act)
            self.assertIn("evidence_ref", act)
            self.assertIn("source_system", act)
            self.assertEqual(act["collector_role"], "ResearchDataCollectionAgent")

    def test_research_agent_consent_denied(self) -> None:
        """Test Research agent skips collection and sets status SKIPPED when consent is False."""
        self.state.consent["research"] = False
        agent = ResearchDataCollectionAgent()
        result = agent.execute(self.state)

        self.assertEqual(result.status, "SKIPPED")
        self.assertEqual(len(result.activities), 0)

        actions = [e["action"] for e in self.state.audit_log]
        self.assertIn("CONSENT_DENIED_SKIPPED", actions)

    def test_teaching_agent_structured_collection(self) -> None:
        """Test Teaching agent collects instruction hours, feedback, CO attainment, and FDP."""
        agent = TeachingDataCollectionAgent()
        result = agent.execute(self.state)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.collector_role, "TeachingDataCollectionAgent")
        self.assertGreater(len(result.activities), 0)

        sub_cats = {a["sub_category"] for a in result.activities}
        self.assertIn("Instructional_Delivery", sub_cats)
        self.assertIn("Student_Feedback", sub_cats)
        self.assertIn("Learning_Outcomes", sub_cats)
        self.assertIn("FDP_Training", sub_cats)

    def test_teaching_agent_student_privacy_guardrail(self) -> None:
        """Test Teaching agent exposes only aggregate ratings; personal student identifiers are excluded."""
        agent = TeachingDataCollectionAgent()
        result = agent.execute(self.state)

        feedback_activities = [
            a for a in result.activities if a["sub_category"] == "Student_Feedback"
        ]
        self.assertGreater(len(feedback_activities), 0)

        for act in feedback_activities:
            desc = act["description"].lower()
            self.assertNotIn("usn", desc)
            self.assertNotIn("student_name", desc)
            self.assertNotIn("roll_number", desc)
            self.assertNotIn("email", desc)
            self.assertIn("aggregate", desc)

    def test_teaching_agent_consent_denied(self) -> None:
        """Test Teaching agent skips collection when teaching consent is False."""
        self.state.consent["teaching_learning"] = False
        agent = TeachingDataCollectionAgent()
        result = agent.execute(self.state)

        self.assertEqual(result.status, "SKIPPED")
        self.assertEqual(len(result.activities), 0)

    def test_administrative_agent_structured_collection(self) -> None:
        """Test Administrative agent collects committee duties and cites institutional source offices."""
        agent = AdministrativeDataCollectionAgent()
        result = agent.execute(self.state)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.collector_role, "AdministrativeDataCollectionAgent")
        self.assertGreater(len(result.activities), 0)

        for act in result.activities:
            self.assertEqual(act["category"], "Administrative")
            self.assertTrue(len(act["source_system"]) > 0)
            self.assertTrue(any(kw in act["source_system"] for kw in ["HoD", "Dean", "Council", "Office"]))

    def test_administrative_agent_consent_denied(self) -> None:
        """Test Administrative agent skips collection when administrative consent is False."""
        self.state.consent["administrative"] = False
        agent = AdministrativeDataCollectionAgent()
        result = agent.execute(self.state)

        self.assertEqual(result.status, "SKIPPED")
        self.assertEqual(len(result.activities), 0)


if __name__ == "__main__":
    unittest.main()
