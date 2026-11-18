"""Security, Consent, and State Isolation tests for Lab 8 - Parallel Swarm.

Verifies:
- Faculty consent enforcement and termination when all consent flags are False.
- Partial consent enforcement per data source category.
- Student privacy preservation in teaching feedback.
- State isolation between independent workflow runs.
- Completeness of append-only audit trail.
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.coordinator import AURACoordinator
from agents.teaching_agent import TeachingDataCollectionAgent
from swarm.state import create_initial_state


class TestSecurityAndGovernance(unittest.TestCase):
    """Test suite for security, consent, privacy, and state isolation."""

    def test_all_consent_denied_terminates_workflow(self) -> None:
        """Test workflow halts immediately at intake when all consent flags are False."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            consent={"research": False, "teaching_learning": False, "administrative": False},
        )
        coordinator = AURACoordinator()
        result = coordinator.run_workflow(state)

        self.assertEqual(result.workflow_status, "TERMINATED")
        self.assertEqual(result.publication_status, "BLOCKED")
        self.assertEqual(len(result.merged_activities), 0)

        actions = [e["action"] for e in result.audit_log]
        self.assertIn("WORKFLOW_TERMINATED_ALL_CONSENT_DENIED", actions)

    def test_partial_consent_enforcement(self) -> None:
        """Test partial consent permits authorized categories, marks skipped as consent-limited, and blocks normal publication."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            consent={"research": False, "teaching_learning": True, "administrative": True},
        )
        coordinator = AURACoordinator()
        result = coordinator.run_workflow(state)

        # Research must be skipped
        research_activities = [
            a for a in result.merged_activities if a.get("category") == "Research"
        ]
        teaching_activities = [
            a for a in result.merged_activities if a.get("category") == "Teaching_Learning"
        ]
        admin_activities = [
            a for a in result.merged_activities if a.get("category") == "Administrative"
        ]

        self.assertEqual(len(research_activities), 0)
        self.assertGreater(len(teaching_activities), 0)
        self.assertGreater(len(admin_activities), 0)

        # Skipped Research category must NOT be a verified zero
        res_cat = result.api_score["category_scores"]["Research"]
        self.assertFalse(res_cat["is_verified_zero"])
        self.assertIsNone(res_cat["raw_claimed_points"])
        self.assertIsNone(res_cat["verified_points"])
        self.assertEqual(res_cat["status"], "NOT_COLLECTED_CONSENT_DENIED")

        # Score marked consent-limited and provisional
        self.assertTrue(result.api_score["is_provisional"])
        self.assertTrue(result.api_score["is_consent_limited"])
        self.assertEqual(result.api_score["score_status"], "CONSENT_LIMITED")

        # Normal publication must be blocked
        self.assertEqual(result.publication_status, "BLOCKED")
        self.assertEqual(result.workflow_status, "BLOCKED_ON_CONSENT")

    def test_student_privacy_redaction(self) -> None:
        """Test teaching feedback contains only aggregate ratings; personal student IDs are redacted."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        agent = TeachingDataCollectionAgent()
        res = agent.execute(state)

        feedback_items = [
            a for a in res.activities if a.get("sub_category") == "Student_Feedback"
        ]
        self.assertGreater(len(feedback_items), 0)
        for item in feedback_items:
            for forbidden in ["usn", "student_name", "email", "phone", "student_id", "roll_number"]:
                self.assertNotIn(forbidden, item["description"].lower())

    def test_state_isolation_between_runs(self) -> None:
        """Test two distinct workflows for different faculty run without cross-contamination."""
        state_1 = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        state_2 = create_initial_state(
            faculty_id="FAC002",
            faculty_name="Dr. Alan Smith",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )

        coord_1 = AURACoordinator()
        coord_2 = AURACoordinator()

        res_1 = coord_1.run_workflow(state_1)
        res_2 = coord_2.run_workflow(state_2)

        self.assertEqual(res_1.faculty_id, "FAC001")
        self.assertEqual(res_2.faculty_id, "FAC002")
        self.assertNotEqual(res_1.run_id, res_2.run_id)

        # Faculty 1 activities must all belong to FAC001
        fac_1_ids = {a["faculty_id"] for a in res_1.merged_activities}
        self.assertTrue(all(fid == "FAC001" for fid in fac_1_ids))


if __name__ == "__main__":
    unittest.main()
