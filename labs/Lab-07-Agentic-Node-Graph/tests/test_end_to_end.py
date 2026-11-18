"""End-to-End integration tests for Lab 7 Scenarios A through F.

Validates:
- Scenario A: Clean successful appraisal workflow (HoD approval -> APPROVED_AND_PUBLISHED).
- Scenario B: Claim with missing evidence (Provisional score, publication blocked).
- Scenario C: Claim with mismatched evidence (Certificate belongs to FAC002 -> blocked).
- Scenario D: Human rejection (Dean rejects report -> REJECTED, publication blocked).
- Scenario E: Consent denied for research (Skipped research collection, teaching/admin processed).
- Scenario F: Unauthorized reviewer (Student role -> UNAUTHORIZED_REVIEW_ATTEMPT, blocked).
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 7 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.coordinator import AURACoordinator
from graph.state import create_initial_state


class TestEndToEndScenarios(unittest.TestCase):
    """Full workflow integration test suite across all official scenarios."""

    def test_scenario_a_success(self) -> None:
        """Scenario A: Full successful appraisal workflow with HoD approval and publication."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
            human_review_comments="All activities verified against institutional records. Recommended for promotion.",
        )

        final_state = coordinator.run_workflow(state)

        # Assertions for successful completion
        self.assertEqual(final_state.workflow_status, "APPROVED_AND_PUBLISHED")
        self.assertEqual(final_state.publication_status, "APPROVED_AND_PUBLISHED")
        self.assertEqual(len(final_state.evidence_exceptions), 0)
        self.assertFalse(final_state.api_score["is_provisional"])
        self.assertEqual(final_state.api_score["score_status"], "FINALIZED_PENDING_APPROVAL")
        self.assertGreater(final_state.api_score["overall_verified_score"], 0)
        self.assertEqual(final_state.report["version"], "v1")
        self.assertEqual(final_state.report["publication_status"], "APPROVED_AND_PUBLISHED")

    def test_scenario_b_missing_evidence(self) -> None:
        """Scenario B: Claim with missing evidence forces provisional score and blocks publication."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            include_missing_evidence=True,
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
        )

        final_state = coordinator.run_workflow(state)

        # Must be blocked on exceptions
        self.assertEqual(final_state.workflow_status, "BLOCKED_ON_EXCEPTIONS")
        self.assertEqual(final_state.publication_status, "BLOCKED")
        self.assertGreater(len(final_state.evidence_exceptions), 0)
        self.assertTrue(final_state.api_score["is_provisional"])
        self.assertEqual(final_state.api_score["score_status"], "PROVISIONAL")

        missing_exc = [
            e for e in final_state.evidence_exceptions if e.get("evidence_status") == "MISSING_EVIDENCE"
        ]
        self.assertGreater(len(missing_exc), 0)

    def test_scenario_c_mismatched_evidence(self) -> None:
        """Scenario C: Claim referencing another faculty member's evidence is blocked."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            include_mismatched_evidence=True,
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
        )

        final_state = coordinator.run_workflow(state)

        self.assertEqual(final_state.workflow_status, "BLOCKED_ON_EXCEPTIONS")
        self.assertEqual(final_state.publication_status, "BLOCKED")

        mismatch_exc = [
            e for e in final_state.evidence_exceptions if e.get("evidence_status") == "MISMATCHED_EVIDENCE"
        ]
        self.assertGreater(len(mismatch_exc), 0)
        self.assertIn("FAC002", mismatch_exc[0]["validation_notes"])

    def test_scenario_d_human_rejection(self) -> None:
        """Scenario D: Dean rejects appraisal report, publication is blocked."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_DEAN_001",
            human_reviewer_role="Dean",
            human_review_decision="REJECTED",
            human_review_comments="Teaching hours documentation does not meet minimum 120 contact hour requirement.",
        )

        final_state = coordinator.run_workflow(state)

        self.assertEqual(final_state.workflow_status, "REJECTED")
        self.assertEqual(final_state.publication_status, "BLOCKED")
        self.assertEqual(final_state.review_decision["decision"], "REJECTED")

    def test_scenario_e_consent_denied(self) -> None:
        """Scenario E: Faculty denies research consent; research skipped, others processed."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            consent={"research": False, "teaching_learning": True, "administrative": True},
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
        )

        final_state = coordinator.run_workflow(state)

        # Research must be empty
        self.assertEqual(len(final_state.research_activities), 0)
        # Teaching and administrative must be collected
        self.assertGreater(len(final_state.teaching_activities), 0)
        self.assertGreater(len(final_state.administrative_activities), 0)

        # Check audit log contains consent denied
        actions = [e["action"] for e in final_state.audit_log]
        self.assertIn("CONSENT_DENIED_SKIPPED", actions)

    def test_scenario_f_unauthorized_reviewer(self) -> None:
        """Scenario F: Review attempted by unauthorized role (Student) is rejected and blocked."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="STU_999",
            human_reviewer_role="Student_Representative",
            human_review_decision="APPROVED",
            human_review_comments="Student representative sign-off attempt.",
        )

        final_state = coordinator.run_workflow(state)

        self.assertEqual(final_state.workflow_status, "REJECTED")
        self.assertEqual(final_state.publication_status, "BLOCKED")

        actions = [e["action"] for e in final_state.audit_log]
        self.assertIn("UNAUTHORIZED_REVIEW_ATTEMPT", actions)


if __name__ == "__main__":
    unittest.main()
