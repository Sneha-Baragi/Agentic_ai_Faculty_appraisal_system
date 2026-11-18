"""Unit tests for Lab 7 API Calculation Agent (Group E).

Verifies weighted score calculation according to weightages.json,
exclusion of unverified points from verified score, and provisional score flag.
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

from agents.api_calculation_agent import APICalculationAgent
from graph.state import create_initial_state
from models.schemas import WorkflowState


class TestAPICalculation(unittest.TestCase):
    """Test suite for APICalculationAgent."""

    def setUp(self) -> None:
        """Create test state and mock weightages."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
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

    def test_clean_verified_calculation(self) -> None:
        """Test API calculation when all activities are verified with zero exceptions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            weight_file = Path(tmp_dir) / "weightages.json"
            weight_file.write_text(json.dumps(self.mock_weightages), encoding="utf-8")

            # Research: 50 pts (weighted 40% = 20.0)
            # Teaching: 40 pts (weighted 40% = 16.0)
            # Admin: 30 pts (weighted 20% = 6.0)
            # Total verified = 20.0 + 16.0 + 6.0 = 42.0
            self.state.validated_activities = [
                {
                    "activity_id": "RES_1",
                    "category": "Research",
                    "claimed_points": 50.0,
                    "evidence_status": "VERIFIED",
                },
                {
                    "activity_id": "TEA_1",
                    "category": "Teaching_Learning",
                    "claimed_points": 40.0,
                    "evidence_status": "VERIFIED",
                },
                {
                    "activity_id": "ADM_1",
                    "category": "Administrative",
                    "claimed_points": 30.0,
                    "evidence_status": "VERIFIED",
                },
            ]
            self.state.evidence_exceptions = []

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
        """Test unverified claims add to raw claimed score, but NOT to verified score."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            weight_file = Path(tmp_dir) / "weightages.json"
            weight_file.write_text(json.dumps(self.mock_weightages), encoding="utf-8")

            # Research has 1 verified (50 pts) and 1 missing evidence (30 pts)
            self.state.validated_activities = [
                {
                    "activity_id": "RES_1",
                    "category": "Research",
                    "claimed_points": 50.0,
                    "evidence_status": "VERIFIED",
                },
                {
                    "activity_id": "RES_2",
                    "category": "Research",
                    "claimed_points": 30.0,
                    "evidence_status": "MISSING_EVIDENCE",
                },
            ]
            self.state.evidence_exceptions = [
                {
                    "activity_id": "RES_2",
                    "evidence_status": "MISSING_EVIDENCE",
                }
            ]

            agent = APICalculationAgent(weightages_path=weight_file)
            res_state = agent.execute(self.state)

            score = res_state.api_score
            self.assertTrue(score["is_provisional"])
            self.assertEqual(score["score_status"], "PROVISIONAL")

            # Raw claimed Research = 80 * 0.40 = 32.0
            # Verified Research = 50 * 0.40 = 20.0
            self.assertEqual(score["overall_claimed_score"], 32.0)
            self.assertEqual(score["overall_verified_score"], 20.0)

    def test_audit_log_on_calculation(self) -> None:
        """Test audit trail logs calculation completion with breakdown details."""
        agent = APICalculationAgent()
        res_state = agent.execute(self.state)

        actions = [entry["action"] for entry in res_state.audit_log]
        self.assertIn("API_CALCULATION_COMPLETE", actions)


if __name__ == "__main__":
    unittest.main()
