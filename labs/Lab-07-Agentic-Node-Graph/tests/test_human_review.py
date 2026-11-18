"""Unit tests for Lab 7 Human Review Agent (Group H).

Verifies role-based authorization gates (HoD, Dean, IQAC), blocking approval
when unresolved exceptions exist, human rejections, and unauthorized access attempts.
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 7 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.human_review_agent import HumanReviewAgent
from graph.state import create_initial_state
from models.schemas import WorkflowState


class TestHumanReview(unittest.TestCase):
    """Test suite for HumanReviewAgent."""

    def setUp(self) -> None:
        """Create clean test state with mock generated report."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        self.state.report = {
            "report_id": "REP_FAC001_V1",
            "version": "v1",
            "status": "DRAFT_PENDING_APPROVAL",
        }
        self.state.evidence_exceptions = []

    def test_hod_approval_success(self) -> None:
        """Test HoD can approve clean appraisal report with zero exceptions."""
        agent = HumanReviewAgent(
            reviewer_id="REV_HOD_001",
            reviewer_role="HoD",
            simulated_decision="APPROVED",
            comments="Verified and approved all requirements.",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "APPROVED")
        self.assertIsNotNone(res_state.review_decision)
        self.assertEqual(res_state.review_decision["decision"], "APPROVED")
        self.assertEqual(res_state.review_decision["reviewer_role"], "HoD")

    def test_dean_approval_success(self) -> None:
        """Test Dean can approve clean appraisal report."""
        agent = HumanReviewAgent(
            reviewer_id="REV_DEAN_001",
            reviewer_role="Dean",
            simulated_decision="APPROVED",
            comments="Dean approval granted.",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "APPROVED")
        self.assertEqual(res_state.review_decision["reviewer_role"], "Dean")

    def test_iqac_approval_success(self) -> None:
        """Test IQAC coordinator can approve clean appraisal report."""
        agent = HumanReviewAgent(
            reviewer_id="REV_IQAC_001",
            reviewer_role="IQAC",
            simulated_decision="APPROVED",
            comments="IQAC audit verified.",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "APPROVED")
        self.assertEqual(res_state.review_decision["reviewer_role"], "IQAC")

    def test_rejection_by_dean(self) -> None:
        """Test Dean rejection transitions workflow to REJECTED and blocks publication."""
        agent = HumanReviewAgent(
            reviewer_id="REV_DEAN_001",
            reviewer_role="Dean",
            simulated_decision="REJECTED",
            comments="Inadequate national journal publications.",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "REJECTED")
        self.assertEqual(res_state.publication_status, "BLOCKED")
        self.assertEqual(res_state.review_decision["decision"], "REJECTED")

    def test_approval_blocked_on_unresolved_exceptions(self) -> None:
        """Test approval is strictly blocked when unresolved evidence exceptions exist."""
        self.state.evidence_exceptions = [
            {"activity_id": "RES_MISSING", "evidence_status": "MISSING_EVIDENCE"}
        ]
        agent = HumanReviewAgent(
            reviewer_id="REV_HOD_001",
            reviewer_role="HoD",
            simulated_decision="APPROVED",
            comments="Premature approval attempt.",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "BLOCKED_ON_EXCEPTIONS")
        self.assertEqual(res_state.publication_status, "BLOCKED")
        self.assertEqual(res_state.review_decision["decision"], "NEEDS_CORRECTION")

        actions = [entry["action"] for entry in res_state.audit_log]
        self.assertIn("APPROVAL_BLOCKED_UNRESOLVED_EXCEPTIONS", actions)

    def test_unauthorized_reviewer_role(self) -> None:
        """Test attempt by unauthorized role (e.g. Student) is rejected and audited."""
        agent = HumanReviewAgent(
            reviewer_id="STU_999",
            reviewer_role="Student",
            simulated_decision="APPROVED",
            comments="Student cannot approve faculty appraisal.",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "REJECTED")
        self.assertEqual(res_state.publication_status, "BLOCKED")

        actions = [entry["action"] for entry in res_state.audit_log]
        self.assertIn("UNAUTHORIZED_REVIEW_ATTEMPT", actions)


if __name__ == "__main__":
    unittest.main()
