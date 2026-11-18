"""End-to-End Integration tests for Lab 8 Scenarios A through G.

Validates:
- Scenario A: Full parallel swarm success with HoD approval (APPROVED_AND_PUBLISHED).
- Scenario B: Research evidence missing (Provisional score, publication blocked).
- Scenario C: Teaching evidence mismatched (Publication blocked).
- Scenario D: Collector failure (Teaching/Admin preserved, partial merge, publication blocked).
- Scenario E: Research consent denied (Research skipped, Teaching/Admin processed).
- Scenario F: Unauthorized reviewer (Student role -> UNAUTHORIZED_REVIEW_ATTEMPT, blocked).
- Scenario G: Human rejection by Dean (REJECTED, publication blocked).
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.coordinator import AURACoordinator
from swarm.state import create_initial_state


class TestEndToEndScenarios(unittest.TestCase):
    """Full workflow integration test suite across all official Lab 8 scenarios."""

    def test_scenario_a_success(self) -> None:
        """Scenario A: Full successful appraisal with 3 concurrent collectors and HoD approval."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            scenario_name="scenario_a_success",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
            human_review_comments="All activities verified against institutional records. Recommended for promotion.",
        )

        final_state = coordinator.run_workflow(state)

        self.assertEqual(final_state.workflow_status, "APPROVED_AND_PUBLISHED")
        self.assertEqual(final_state.publication_status, "APPROVED_AND_PUBLISHED")
        self.assertEqual(len(final_state.evidence_exceptions), 0)
        self.assertFalse(final_state.api_score["is_provisional"])
        self.assertEqual(final_state.api_score["score_status"], "FINALIZED_PENDING_APPROVAL")
        self.assertEqual(final_state.api_score["overall_verified_score"], 54.0)
        self.assertEqual(final_state.report["version"], "v1")
        self.assertEqual(final_state.report["publication_status"], "APPROVED_AND_PUBLISHED")

    def test_scenario_b_missing_evidence(self) -> None:
        """Scenario B: Claim with missing evidence forces provisional score and blocks publication."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            test_injection="MISSING_EVIDENCE",
            scenario_name="scenario_b_missing_evidence",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
        )

        final_state = coordinator.run_workflow(state)

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
        """Scenario C: Claim with mismatched evidence category blocks publication."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            test_injection="MISMATCHED_EVIDENCE",
            scenario_name="scenario_c_mismatched_evidence",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
        )

        final_state = coordinator.run_workflow(state)

        self.assertEqual(final_state.workflow_status, "BLOCKED_ON_EXCEPTIONS")
        self.assertEqual(final_state.publication_status, "BLOCKED")
        self.assertGreater(len(final_state.evidence_exceptions), 0)

        mismatched_exc = [
            e for e in final_state.evidence_exceptions if e.get("evidence_status") == "MISMATCHED_EVIDENCE"
        ]
        self.assertGreater(len(mismatched_exc), 0)

    def test_scenario_d_collector_failure(self) -> None:
        """Scenario D: Research collector fails; Teaching and Admin outputs preserved, merge is PARTIAL."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            test_injection="FAIL_RESEARCH",
            scenario_name="scenario_d_collector_failure",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
        )

        final_state = coordinator.run_workflow(state)

        # Merge must be PARTIAL
        self.assertIsNotNone(final_state.merge_result)
        self.assertEqual(final_state.merge_result["status"], "PARTIAL")
        self.assertIn("ResearchDataCollectionAgent", final_state.merge_result["failed_collectors"])

        # Teaching and Admin must still be collected and merged
        teaching_acts = [a for a in final_state.merged_activities if a.get("category") == "Teaching_Learning"]
        admin_acts = [a for a in final_state.merged_activities if a.get("category") == "Administrative"]
        self.assertGreater(len(teaching_acts), 0)
        self.assertGreater(len(admin_acts), 0)

        # Incomplete collection blocks approval and publication
        self.assertEqual(final_state.workflow_status, "BLOCKED_ON_EXCEPTIONS")
        self.assertEqual(final_state.publication_status, "BLOCKED")
        self.assertTrue(final_state.api_score["is_provisional"])

    def test_scenario_e_consent_denied(self) -> None:
        """Scenario E: Faculty withholds consent for Research; category is marked NOT_COLLECTED_CONSENT_DENIED, not verified zero, and approval is blocked."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            consent={"research": False, "teaching_learning": True, "administrative": True},
            scenario_name="scenario_e_consent_denied",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
        )

        final_state = coordinator.run_workflow(state)

        # 1. Research must not have any collected activities
        research_acts = [a for a in final_state.merged_activities if a.get("category") == "Research"]
        teaching_acts = [a for a in final_state.merged_activities if a.get("category") == "Teaching_Learning"]
        admin_acts = [a for a in final_state.merged_activities if a.get("category") == "Administrative"]

        self.assertEqual(len(research_acts), 0)
        self.assertGreater(len(teaching_acts), 0)
        self.assertGreater(len(admin_acts), 0)

        # 2. Research category must NOT be represented as a verified zero
        api_score = final_state.api_score
        res_cat = api_score["category_scores"]["Research"]
        self.assertFalse(res_cat["is_verified_zero"])
        self.assertIsNone(res_cat["raw_claimed_points"])
        self.assertIsNone(res_cat["verified_points"])
        self.assertIsNone(res_cat["raw_weighted_score"])
        self.assertIsNone(res_cat["verified_weighted_score"])
        self.assertEqual(res_cat["status"], "NOT_COLLECTED_CONSENT_DENIED")
        self.assertEqual(res_cat["collection_status"], "SKIPPED_CONSENT_DENIED")

        # 3. Overall appraisal must be provisional and marked CONSENT_LIMITED
        self.assertTrue(api_score["is_provisional"])
        self.assertTrue(api_score["is_consent_limited"])
        self.assertEqual(api_score["score_status"], "CONSENT_LIMITED")

        # 4. Normal approval and publication must be blocked without explicit override
        self.assertEqual(final_state.workflow_status, "BLOCKED_ON_CONSENT")
        self.assertEqual(final_state.publication_status, "BLOCKED")
        self.assertEqual(final_state.review_decision["decision"], "NEEDS_CORRECTION")
        self.assertIn("consent-limited", final_state.review_decision["comments"].lower())

    def test_scenario_e_with_authorized_institutional_override(self) -> None:
        """Scenario E with explicit authorized override allows approval of consent-limited appraisal."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            consent={"research": False, "teaching_learning": True, "administrative": True},
            scenario_name="scenario_e_override",
        )
        override = {
            "override_authorized": True,
            "authorized_by": "Academic_Council",
            "policy_ref": "STATUTE_POLICY_4.2_SABBATICAL_EXEMPTION",
            "reason": "Faculty member on official sabbatical leave during appraisal cycle.",
        }
        coordinator = AURACoordinator(
            human_reviewer_id="REV_DEAN_001",
            human_reviewer_role="Dean",
            human_review_decision="APPROVED",
            institutional_override=override,
        )

        final_state = coordinator.run_workflow(state)

        # With explicit institutional override, publication succeeds
        self.assertEqual(final_state.workflow_status, "APPROVED_AND_PUBLISHED")
        self.assertEqual(final_state.publication_status, "APPROVED_AND_PUBLISHED")
        self.assertEqual(final_state.review_decision["decision"], "APPROVED")

    def test_scenario_e_with_unauthorized_override_blocked(self) -> None:
        """Scenario E with forged/unauthorized override is rejected and publication is blocked."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            consent={"research": False, "teaching_learning": True, "administrative": True},
            scenario_name="scenario_e_unauth_override",
        )
        fake_override = {
            "override_authorized": True,
            "authorized_by": "External_Vendor_Agent",
            "policy_ref": "INVALID_POLICY_REF_999",
            "reason": "Bypass attempt",
        }
        coordinator = AURACoordinator(
            human_reviewer_id="REV_HOD_001",
            human_reviewer_role="HoD",
            human_review_decision="APPROVED",
            institutional_override=fake_override,
        )

        final_state = coordinator.run_workflow(state)

        # Unrecognized override must be rejected and publication blocked
        self.assertEqual(final_state.workflow_status, "BLOCKED_ON_CONSENT")
        self.assertEqual(final_state.publication_status, "BLOCKED")
        self.assertEqual(final_state.review_decision["decision"], "NEEDS_CORRECTION")
        actions = [e["action"] for e in final_state.audit_log]
        self.assertIn("INVALID_OVERRIDE_REJECTED", actions)

    def test_scenario_f_unauthorized_reviewer(self) -> None:
        """Scenario F: Review attempted by unauthorized role (Student) is rejected and blocked."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            scenario_name="scenario_f_unauthorized_reviewer",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_STU_999",
            human_reviewer_role="Student_Representative",
            human_review_decision="APPROVED",
            human_review_comments="Student sign-off attempt.",
        )

        final_state = coordinator.run_workflow(state)

        self.assertEqual(final_state.workflow_status, "REJECTED")
        self.assertEqual(final_state.publication_status, "BLOCKED")

        actions = [e["action"] for e in final_state.audit_log]
        self.assertIn("UNAUTHORIZED_REVIEW_ATTEMPT", actions)

    def test_scenario_g_human_rejection(self) -> None:
        """Scenario G: Dean exercises governance oversight and rejects report; publication blocked."""
        state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            scenario_name="scenario_g_human_rejection",
        )
        coordinator = AURACoordinator(
            human_reviewer_id="REV_DEAN_001",
            human_reviewer_role="Dean",
            human_review_decision="REJECTED",
            human_review_comments="Instructional delivery hours documentation does not meet minimum 120 contact hour requirement.",
        )

        final_state = coordinator.run_workflow(state)

        self.assertEqual(final_state.workflow_status, "REJECTED")
        self.assertEqual(final_state.publication_status, "BLOCKED")
        self.assertEqual(final_state.review_decision["decision"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
