"""Unit tests for Lab 7 data collection agents (Group A, B, and C).

Tests ResearchAgent, TeachingAgent, and AdministrativeAgent collection behavior,
schema normalization, privacy preservation, incomplete record handling, and consent guardrails.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

# Ensure Lab 7 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.administrative_agent import AdministrativeAgent
from agents.research_agent import ResearchAgent
from agents.teaching_agent import TeachingAgent
from graph.state import create_initial_state
from models.schemas import WorkflowState


class TestCollectionAgents(unittest.TestCase):
    """Test suite for specialized collection agents."""

    def setUp(self) -> None:
        """Set up test initial state."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )

    def test_research_agent_collection(self) -> None:
        """Test ResearchAgent collects valid publications, grants, and guidance records."""
        agent = ResearchAgent()
        updated_state = agent.execute(self.state)

        self.assertGreater(len(updated_state.research_activities), 0)
        for act in updated_state.research_activities:
            self.assertEqual(act["faculty_id"], "FAC001")
            self.assertEqual(act["category"], "Research")
            self.assertIn("claimed_points", act)
            self.assertIn("source_system", act)
            self.assertIn("evidence_ref", act)

        # Check audit entry
        actions = [entry["action"] for entry in updated_state.audit_log]
        self.assertIn("COLLECTION_COMPLETE", actions)

    def test_research_agent_consent_denied(self) -> None:
        """Test ResearchAgent aborts collection and records audit when consent is False."""
        self.state.consent["research"] = False
        agent = ResearchAgent()
        updated_state = agent.execute(self.state)

        self.assertEqual(len(updated_state.research_activities), 0)
        actions = [entry["action"] for entry in updated_state.audit_log]
        self.assertIn("CONSENT_DENIED_SKIPPED", actions)

    def test_research_agent_incomplete_record(self) -> None:
        """Test ResearchAgent flags incomplete research claims."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = Path(tmp_dir) / "test_res.json"
            mock_data = [
                {
                    "activity_id": "RES_BAD",
                    "faculty_id": "FAC001",
                    "title": "",  # Missing title
                    "category": "Research",
                    "claimed_points": 0.0,
                    "evidence_ref": "EVID_001",
                }
            ]
            tmp_file.write_text(json.dumps(mock_data), encoding="utf-8")

            agent = ResearchAgent(data_path=tmp_file)
            updated_state = agent.execute(self.state)

            self.assertEqual(len(updated_state.research_activities), 1)
            bad_act = updated_state.research_activities[0]
            self.assertEqual(bad_act["evidence_status"], "INCOMPLETE")

    def test_teaching_agent_collection(self) -> None:
        """Test TeachingAgent collects instruction hours, feedback, CO attainment, and FDP."""
        agent = TeachingAgent()
        updated_state = agent.execute(self.state)

        self.assertGreater(len(updated_state.teaching_activities), 0)
        categories = {a["sub_category"] for a in updated_state.teaching_activities}
        self.assertIn("Instructional_Delivery", categories)
        self.assertIn("Student_Feedback", categories)
        self.assertIn("Learning_Outcomes", categories)
        self.assertIn("FDP_Training", categories)

    def test_teaching_agent_privacy_guardrail(self) -> None:
        """Test TeachingAgent preserves student privacy: aggregate metrics only, no student IDs."""
        agent = TeachingAgent()
        updated_state = agent.execute(self.state)

        for act in updated_state.teaching_activities:
            if act["sub_category"] == "Student_Feedback":
                # Ensure no raw student identifier keys exist in description or fields
                desc = act["description"].lower()
                self.assertNotIn("usn", desc)
                self.assertNotIn("student_id", desc)
                self.assertNotIn("roll_number", desc)
                self.assertIn("aggregate", desc)

    def test_teaching_agent_consent_denied(self) -> None:
        """Test TeachingAgent aborts collection when teaching consent is False."""
        self.state.consent["teaching_learning"] = False
        agent = TeachingAgent()
        updated_state = agent.execute(self.state)

        self.assertEqual(len(updated_state.teaching_activities), 0)
        actions = [entry["action"] for entry in updated_state.audit_log]
        self.assertIn("CONSENT_DENIED_SKIPPED", actions)

    def test_administrative_agent_collection(self) -> None:
        """Test AdministrativeAgent collects institutional roles and source citations."""
        agent = AdministrativeAgent()
        updated_state = agent.execute(self.state)

        self.assertGreater(len(updated_state.administrative_activities), 0)
        for act in updated_state.administrative_activities:
            self.assertEqual(act["category"], "Administrative")
            self.assertTrue(len(act["source_system"]) > 0)
            self.assertTrue(any(kw in act["source_system"] for kw in ["HoD", "Dean", "Academic", "Office"]))
            self.assertTrue(len(act["evidence_ref"]) > 0)

    def test_administrative_agent_consent_denied(self) -> None:
        """Test AdministrativeAgent aborts collection when administrative consent is False."""
        self.state.consent["administrative"] = False
        agent = AdministrativeAgent()
        updated_state = agent.execute(self.state)

        self.assertEqual(len(updated_state.administrative_activities), 0)
        actions = [entry["action"] for entry in updated_state.audit_log]
        self.assertIn("CONSENT_DENIED_SKIPPED", actions)


if __name__ == "__main__":
    unittest.main()
