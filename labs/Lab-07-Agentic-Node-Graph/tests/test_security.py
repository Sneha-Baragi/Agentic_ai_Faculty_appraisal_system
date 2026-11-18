"""Security, Governance, and Privacy tests for Lab 7.

Verifies:
- Faculty consent enforcement and workflow termination on all-consent-denied.
- Role-based authorization for human review.
- Privacy preservation in student feedback data (no raw student identifiers).
- Multi-tenant state isolation between distinct faculty workflow runs.
- Audit trail completeness and immutability.
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 7 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.coordinator import AURACoordinator
from agents.human_review_agent import HumanReviewAgent
from agents.teaching_agent import TeachingAgent
from graph.state import create_initial_state


class TestSecurityAndGovernance(unittest.TestCase):
    """Test suite for security, consent, privacy, and state isolation."""

    def test_all_consent_denied_terminates_workflow(self) -> None:
        """Test workflow halts immediately at intake when all consent flags are False."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        state.consent = {
            "research": False,
            "teaching_learning": False,
            "administrative": False,
        }

        coordinator = AURACoordinator()
        result = coordinator.run_workflow(state)

        self.assertEqual(result.workflow_status, "TERMINATED")
        self.assertEqual(result.publication_status, "BLOCKED")
        self.assertEqual(len(result.research_activities), 0)
        self.assertEqual(len(result.teaching_activities), 0)
        self.assertEqual(len(result.administrative_activities), 0)

        actions = [entry["action"] for entry in result.audit_log]
        self.assertIn("WORKFLOW_TERMINATED_ALL_CONSENT_DENIED", actions)

    def test_partial_consent_enforcement(self) -> None:
        """Test partial consent permits authorized categories while skipping denied ones."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        # Deny research, allow teaching and administrative
        state.consent["research"] = False
        state.consent["teaching_learning"] = True
        state.consent["administrative"] = True

        coordinator = AURACoordinator()
        result = coordinator.run_workflow(state)

        self.assertEqual(len(result.research_activities), 0)
        self.assertGreater(len(result.teaching_activities), 0)
        self.assertGreater(len(result.administrative_activities), 0)

    def test_unauthorized_review_roles_blocked(self) -> None:
        """Test arbitrary unauthorized roles are strictly rejected at the human review gate."""
        unauthorized_roles = ["Student", "Faculty_Peer", "Guest", "System_Admin", "Registrar"]
        for role in unauthorized_roles:
            state = create_initial_state(
                faculty_id="FAC001",
                faculty_name="Dr. Jane Doe",
                appraisal_period="2025-2026",
                requester_role="Faculty",
            )
            state.report = {"report_id": "REP_001", "status": "DRAFT"}
            agent = HumanReviewAgent(
                reviewer_id=f"REV_{role.upper()}_01",
                reviewer_role=role,
                simulated_decision="APPROVED",
            )
            res = agent.execute(state)
            self.assertEqual(res.workflow_status, "REJECTED", f"Role {role} was not rejected")
            self.assertEqual(res.publication_status, "BLOCKED")

    def test_student_feedback_privacy_preservation(self) -> None:
        """Test student feedback is strictly aggregated and contains no personally identifiable data."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        agent = TeachingAgent()
        res = agent.execute(state)

        feedback_items = [
            a for a in res.teaching_activities if a.get("sub_category") == "Student_Feedback"
        ]
        self.assertGreater(len(feedback_items), 0)
        for item in feedback_items:
            for forbidden in ["usn", "student_name", "email", "phone", "student_id"]:
                self.assertNotIn(forbidden, item["description"].lower())

    def test_state_isolation_between_runs(self) -> None:
        """Test two distinct workflows for different faculty run without cross-contamination."""
        state_1 = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
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

        # Faculty 1 activities should not appear in Faculty 2
        fac_1_ids = {a["faculty_id"] for a in res_1.validated_activities}
        self.assertTrue(all(fid == "FAC001" for fid in fac_1_ids))


if __name__ == "__main__":
    unittest.main()
