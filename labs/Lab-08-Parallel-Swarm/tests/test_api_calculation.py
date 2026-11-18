"""Unit tests for Lab 8 API Calculation Agent.

Verifies:
- Only VERIFIED activities contribute to verified score.
- Unverified activities contribute 0.0 to verified total.
- Weightage enforcement matches weightages.json.
- Provisional score flag set when exceptions exist.
- Transparent mathematical category-wise breakdown.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.api_calculation_agent import APICalculationAgent
from swarm.state import create_initial_state


class TestAPICalculation(unittest.TestCase):
    """Test suite for APICalculationAgent."""

    def setUp(self) -> None:
        """Create clean test state."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        self.mock_weightages = {
            "version": "1.0.0-test",
            "category_weights": {
                "Research": 0.40,
                "Teaching_Learning": 0.40,
                "Administrative": 0.20,
            },
        }

    def test_clean_verified_scoring(self) -> None:
        """Test API score calculation when all activities are verified with zero exceptions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            weight_file = Path(tmp_dir) / "weightages.json"
            weight_file.write_text(json.dumps(self.mock_weightages), encoding="utf-8")

            # Research: 50 pts * 0.40 = 20.0
            # Teaching: 40 pts * 0.40 = 16.0
            # Admin: 30 pts * 0.20 = 6.0
            # Verified total = 42.0
            self.state.validated_activities = [
                {"activity_id": "RES_1", "category": "Research", "claimed_points": 50.0, "evidence_status": "VERIFIED"},
                {"activity_id": "TEA_1", "category": "Teaching_Learning", "claimed_points": 40.0, "evidence_status": "VERIFIED"},
                {"activity_id": "ADM_1", "category": "Administrative", "claimed_points": 30.0, "evidence_status": "VERIFIED"},
            ]
            self.state.evidence_exceptions = []
            self.state.merge_result = {"status": "SUCCESS"}

            agent = APICalculationAgent(weightages_path=weight_file)
            res_state = agent.execute(self.state)

            score = res_state.api_score
            self.assertFalse(score["is_provisional"])
            self.assertEqual(score["score_status"], "FINALIZED_PENDING_APPROVAL")
            self.assertEqual(score["overall_verified_score"], 42.0)
            self.assertEqual(score["overall_claimed_score"], 42.0)

            cat_scores = score["category_scores"]
            self.assertEqual(cat_scores["Research"]["verified_weighted_score"], 20.0)
            self.assertEqual(cat_scores["Teaching_Learning"]["verified_weighted_score"], 16.0)
            self.assertEqual(cat_scores["Administrative"]["verified_weighted_score"], 6.0)

    def test_unverified_claims_excluded_from_verified_score(self) -> None:
        """Test unverified claims do not contribute to verified score and flag score provisional."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            weight_file = Path(tmp_dir) / "weightages.json"
            weight_file.write_text(json.dumps(self.mock_weightages), encoding="utf-8")

            # Research has 1 verified (50 pts) and 1 missing evidence (30 pts)
            self.state.validated_activities = [
                {"activity_id": "RES_1", "category": "Research", "claimed_points": 50.0, "evidence_status": "VERIFIED"},
                {"activity_id": "RES_2", "category": "Research", "claimed_points": 30.0, "evidence_status": "MISSING_EVIDENCE"},
            ]
            self.state.evidence_exceptions = [{"activity_id": "RES_2", "evidence_status": "MISSING_EVIDENCE"}]
            self.state.merge_result = {"status": "SUCCESS"}

            agent = APICalculationAgent(weightages_path=weight_file)
            res_state = agent.execute(self.state)

            score = res_state.api_score
            self.assertTrue(score["is_provisional"])
            self.assertEqual(score["score_status"], "PROVISIONAL")
            # Claimed = 80 * 0.40 = 32.0; Verified = 50 * 0.40 = 20.0
            self.assertEqual(score["overall_claimed_score"], 32.0)
            self.assertEqual(score["overall_verified_score"], 20.0)

    def test_partial_merge_forces_provisional_score(self) -> None:
        """Test that a partial merge status flags the score as provisional even if no exceptions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            weight_file = Path(tmp_dir) / "weightages.json"
            weight_file.write_text(json.dumps(self.mock_weightages), encoding="utf-8")

            self.state.validated_activities = [
                {"activity_id": "TCH_1", "category": "Teaching_Learning", "claimed_points": 40.0, "evidence_status": "VERIFIED"}
            ]
            self.state.evidence_exceptions = []
            # Merge was PARTIAL due to a failed collector
            self.state.merge_result = {"status": "PARTIAL"}

            agent = APICalculationAgent(weightages_path=weight_file)
            res_state = agent.execute(self.state)

            score = res_state.api_score
            self.assertTrue(score["is_provisional"])
            self.assertEqual(score["score_status"], "PROVISIONAL")

    def test_consent_denied_category_not_represented_as_verified_zero(self) -> None:
        """Test skipped category due to withheld consent is NOT represented as verified zero."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            weight_file = Path(tmp_dir) / "weightages.json"
            weight_file.write_text(json.dumps(self.mock_weightages), encoding="utf-8")

            self.state.consent = {"research": False, "teaching_learning": True, "administrative": True}
            self.state.validated_activities = [
                {"activity_id": "TCH_1", "category": "Teaching_Learning", "claimed_points": 40.0, "evidence_status": "VERIFIED"},
                {"activity_id": "ADM_1", "category": "Administrative", "claimed_points": 20.0, "evidence_status": "VERIFIED"},
            ]
            self.state.evidence_exceptions = []
            self.state.merge_result = {"status": "CONSENT_LIMITED", "skipped_collectors": ["ResearchDataCollectionAgent"]}

            agent = APICalculationAgent(weightages_path=weight_file)
            res_state = agent.execute(self.state)

            score = res_state.api_score
            self.assertTrue(score["is_provisional"])
            self.assertTrue(score["is_consent_limited"])
            self.assertEqual(score["score_status"], "CONSENT_LIMITED")

            res_cat = score["category_scores"]["Research"]
            self.assertFalse(res_cat["is_verified_zero"])
            self.assertEqual(res_cat["status"], "NOT_COLLECTED_CONSENT_DENIED")
            self.assertIsNone(res_cat["raw_claimed_points"])
            self.assertIsNone(res_cat["verified_points"])
            self.assertIsNone(res_cat["raw_weighted_score"])
            self.assertIsNone(res_cat["verified_weighted_score"])
            self.assertNotEqual(res_cat["verified_weighted_score"], 0.0)
            self.assertEqual(score["score_type"], "PARTIAL_CONSENT_LIMITED")
            self.assertIn("NOT a verified zero", res_cat["notes"])

    def test_genuinely_verified_zero_distinguished_from_consent_denied(self) -> None:
        """Test genuinely verified zero category is distinguished with is_verified_zero=True."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            weight_file = Path(tmp_dir) / "weightages.json"
            weight_file.write_text(json.dumps(self.mock_weightages), encoding="utf-8")

            # All consent granted, but faculty has 0 research activities
            self.state.consent = {"research": True, "teaching_learning": True, "administrative": True}
            self.state.validated_activities = [
                {"activity_id": "TCH_1", "category": "Teaching_Learning", "claimed_points": 50.0, "evidence_status": "VERIFIED"}
            ]
            self.state.evidence_exceptions = []
            self.state.merge_result = {"status": "SUCCESS", "skipped_collectors": []}

            agent = APICalculationAgent(weightages_path=weight_file)
            res_state = agent.execute(self.state)

            score = res_state.api_score
            res_cat = score["category_scores"]["Research"]
            self.assertTrue(res_cat["is_verified_zero"])
            self.assertEqual(res_cat["status"], "VERIFIED_ZERO")
            self.assertEqual(res_cat["raw_claimed_points"], 0.0)
            self.assertEqual(res_cat["verified_points"], 0.0)


if __name__ == "__main__":
    unittest.main()
