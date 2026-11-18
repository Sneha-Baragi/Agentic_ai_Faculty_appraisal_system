"""Unit tests for Lab 8 Human Review Agent and Governance Gate.

Verifies:
- Authorized governance roles (HoD, Dean, IQAC) can grant approvals.
- Unauthorized reviewers are strictly rejected and logged.
- Unresolved evidence exceptions block final approval.
- Incomplete swarm collection blocks approval.
- Human rejections set status to REJECTED and block publication.
- Unapproved reports are never published.
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.human_review_agent import HumanReviewAgent
from swarm.state import create_initial_state


class TestHumanReview(unittest.TestCase):
    """Test suite for HumanReviewAgent."""

    def setUp(self) -> None:
        """Create clean test state."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        self.state.report = {
            "report_id": "REP_TEST",
            "version": "v1",
            "status": "DRAFT_PENDING_APPROVAL",
        }
        self.state.evidence_exceptions = []
        self.state.merge_result = {"status": "SUCCESS"}

    def test_hod_approval_clean_report(self) -> None:
        """Test HoD can approve clean appraisal report."""
        agent = HumanReviewAgent(
            reviewer_id="REV_HOD_001",
            reviewer_role="HoD",
            simulated_decision="APPROVED",
            comments="Verified and approved all requirements.",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "APPROVED")
        self.assertEqual(res_state.review_decision["decision"], "APPROVED")
        self.assertEqual(res_state.review_decision["reviewer_role"], "HoD")

    def test_dean_approval_clean_report(self) -> None:
        """Test Dean can approve clean appraisal report."""
        agent = HumanReviewAgent(
            reviewer_id="REV_DEAN_001",
            reviewer_role="Dean",
            simulated_decision="APPROVED",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "APPROVED")
        self.assertEqual(res_state.review_decision["reviewer_role"], "Dean")

    def test_iqac_approval_clean_report(self) -> None:
        """Test IQAC coordinator can approve clean appraisal report."""
        agent = HumanReviewAgent(
            reviewer_id="REV_IQAC_001",
            reviewer_role="IQAC",
            simulated_decision="APPROVED",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "APPROVED")
        self.assertEqual(res_state.review_decision["reviewer_role"], "IQAC")

    def test_unauthorized_role_rejected(self) -> None:
        """Test attempt by unauthorized role (Student) is rejected and audited."""
        agent = HumanReviewAgent(
            reviewer_id="STU_999",
            reviewer_role="Student_Representative",
            simulated_decision="APPROVED",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "REJECTED")
        self.assertEqual(res_state.publication_status, "BLOCKED")

        actions = [e["action"] for e in res_state.audit_log]
        self.assertIn("UNAUTHORIZED_REVIEW_ATTEMPT", actions)

    def test_approval_blocked_on_unresolved_exceptions(self) -> None:
        """Test approval is blocked with NEEDS_CORRECTION if unresolved exceptions exist."""
        self.state.evidence_exceptions = [
            {"activity_id": "RES_MISSING", "evidence_status": "MISSING_EVIDENCE"}
        ]
        agent = HumanReviewAgent(
            reviewer_id="REV_HOD_001",
            reviewer_role="HoD",
            simulated_decision="APPROVED",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "BLOCKED_ON_EXCEPTIONS")
        self.assertEqual(res_state.publication_status, "BLOCKED")
        self.assertEqual(res_state.review_decision["decision"], "NEEDS_CORRECTION")

        actions = [e["action"] for e in res_state.audit_log]
        self.assertIn("APPROVAL_BLOCKED_UNRESOLVED_EXCEPTIONS", actions)

    def test_approval_blocked_on_incomplete_collection(self) -> None:
        """Test approval is blocked if swarm collection was incomplete."""
        self.state.merge_result = {"status": "PARTIAL"}
        agent = HumanReviewAgent(
            reviewer_id="REV_HOD_001",
            reviewer_role="HoD",
            simulated_decision="APPROVED",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "BLOCKED_ON_EXCEPTIONS")
        self.assertEqual(res_state.publication_status, "BLOCKED")
        self.assertEqual(res_state.review_decision["decision"], "NEEDS_CORRECTION")

    def test_dean_rejection(self) -> None:
        """Test Dean rejection transitions workflow to REJECTED and blocks publication."""
        agent = HumanReviewAgent(
            reviewer_id="REV_DEAN_001",
            reviewer_role="Dean",
            simulated_decision="REJECTED",
            comments="Instructional delivery documentation does not meet required syllabus targets.",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "REJECTED")
        self.assertEqual(res_state.publication_status, "BLOCKED")
        self.assertEqual(res_state.review_decision["decision"], "REJECTED")

        actions = [e["action"] for e in res_state.audit_log]
        self.assertIn("APPRAISAL_REJECTED", actions)

    def test_approval_blocked_on_consent_limited_appraisal(self) -> None:
        """Test approval is blocked with NEEDS_CORRECTION if appraisal is consent-limited without override."""
        self.state.api_score = {
            "is_consent_limited": True,
            "skipped_categories": ["Research"],
        }
        agent = HumanReviewAgent(
            reviewer_id="REV_HOD_001",
            reviewer_role="HoD",
            simulated_decision="APPROVED",
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "BLOCKED_ON_CONSENT")
        self.assertEqual(res_state.publication_status, "BLOCKED")
        self.assertEqual(res_state.review_decision["decision"], "NEEDS_CORRECTION")
        self.assertIn("consent-limited", res_state.review_decision["comments"].lower())

        actions = [e["action"] for e in res_state.audit_log]
        self.assertIn("APPROVAL_BLOCKED_CONSENT_LIMITATION", actions)

    def test_approval_permitted_with_authorized_institutional_override(self) -> None:
        """Test approval succeeds for consent-limited appraisal when authorized institutional override is supplied."""
        self.state.api_score = {
            "is_consent_limited": True,
            "skipped_categories": ["Research"],
        }
        override = {
            "override_authorized": True,
            "authorized_by": "Academic_Council",
            "policy_ref": "STATUTE_POLICY_4.2_SABBATICAL_EXEMPTION",
            "reason": "Official sabbatical leave approved by Academic Council.",
        }
        agent = HumanReviewAgent(
            reviewer_id="REV_DEAN_001",
            reviewer_role="Dean",
            simulated_decision="APPROVED",
            institutional_override=override,
        )
        res_state = agent.execute(self.state)

        self.assertEqual(res_state.workflow_status, "APPROVED")
        self.assertEqual(res_state.review_decision["decision"], "APPROVED")

        actions = [e["action"] for e in res_state.audit_log]
        self.assertIn("APPRAISAL_APPROVED_WITH_OVERRIDE", actions)

    def test_invalid_or_unauthorized_override_rejected(self) -> None:
        """Test caller-supplied override is rejected if authority is unauthorized or policy is unrecognized."""
        self.state.api_score = {
            "is_consent_limited": True,
            "skipped_categories": ["Research"],
        }

        # Case 1: Caller supplies override_authorized=True but unauthorized authority (Student_Council)
        invalid_override_1 = {
            "override_authorized": True,
            "authorized_by": "Student_Council",
            "policy_ref": "STATUTE_POLICY_4.2_SABBATICAL_EXEMPTION",
            "reason": "Student body recommendation",
        }
        val_res_1 = HumanReviewAgent.validate_institutional_override(invalid_override_1)
        self.assertFalse(val_res_1["is_valid"])
        self.assertIn("Unrecognized or unauthorized", val_res_1["reason"])

        agent_1 = HumanReviewAgent(
            reviewer_id="REV_HOD_001",
            reviewer_role="HoD",
            simulated_decision="APPROVED",
            institutional_override=invalid_override_1,
        )
        res_1 = agent_1.execute(self.state)
        self.assertEqual(res_1.workflow_status, "BLOCKED_ON_CONSENT")
        self.assertEqual(res_1.publication_status, "BLOCKED")
        self.assertEqual(res_1.review_decision["decision"], "NEEDS_CORRECTION")
        actions_1 = [e["action"] for e in res_1.audit_log]
        self.assertIn("INVALID_OVERRIDE_REJECTED", actions_1)

        # Case 2: Caller supplies override_authorized=True without required authority and policy ref
        invalid_override_2 = {"override_authorized": True}
        val_res_2 = HumanReviewAgent.validate_institutional_override(invalid_override_2)
        self.assertFalse(val_res_2["is_valid"])


if __name__ == "__main__":
    unittest.main()
