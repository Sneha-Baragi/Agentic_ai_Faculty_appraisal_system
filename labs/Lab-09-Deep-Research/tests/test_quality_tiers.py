"""Unit tests for Evidence-Quality Tiers and Mathematical Formulas (Assignment 2)."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.comparator import EvidenceComparator
from agent.extractor import EvidenceExtractor
from agent.search_retriever import SearchRetriever
from agent.synthesizer import EvidenceSynthesizer
from models.schemas import QualityTier, TIER_WEIGHTS


class TestQualityTiers(unittest.TestCase):
    """Verifies quality tier weights, formula calculations, and lower-tier disclosure."""

    def setUp(self) -> None:
        self.retriever = SearchRetriever()
        self.extractor = EvidenceExtractor()
        self.comparator = EvidenceComparator()
        self.synthesizer = EvidenceSynthesizer()
        self.docs = self.retriever.get_all_sources()
        self.rows = self.extractor.extract_table(self.docs)
        _, self.conflicts, _ = self.comparator.compare(self.rows)

    def test_tier_weight_mappings(self) -> None:
        self.assertEqual(TIER_WEIGHTS[QualityTier.TIER_1], 1.0)
        self.assertEqual(TIER_WEIGHTS[QualityTier.TIER_2], 0.7)
        self.assertEqual(TIER_WEIGHTS[QualityTier.TIER_3], 0.4)

    def test_sources_assigned_correct_tiers(self) -> None:
        row_map = {r.source_id: r for r in self.rows}
        self.assertEqual(row_map["S1"].tier, QualityTier.TIER_1.value)
        self.assertEqual(row_map["S1"].tier_weight, 1.0)

        self.assertEqual(row_map["S2"].tier, QualityTier.TIER_3.value)
        self.assertEqual(row_map["S2"].tier_weight, 0.4)

        self.assertEqual(row_map["S3"].tier, QualityTier.TIER_2.value)
        self.assertEqual(row_map["S3"].tier_weight, 0.7)

        self.assertEqual(row_map["S4"].tier, QualityTier.TIER_1.value)
        self.assertEqual(row_map["S4"].tier_weight, 1.0)

    def test_four_source_eqi_and_reliability_formula(self) -> None:
        metrics = self.synthesizer.compute_metrics(self.rows, self.conflicts)

        # Expected EQI = (1.0 + 0.4 + 0.7 + 1.0) / 4 = 3.1 / 4 = 0.775
        self.assertEqual(metrics.eqi, 0.775)

        # Severity max = 1.0 (Tier 1 vs Tier 1)
        self.assertEqual(metrics.severity_max, 1.0)

        # Reliability = 0.775 * (1.0 - 0.5 * 1.0) = 0.775 * 0.5 = 0.3875
        self.assertEqual(metrics.reliability_score, 0.3875)
        self.assertEqual(metrics.status, "CONTESTED_TIER_1_CONFLICT")
        self.assertTrue(metrics.human_review_required)

    def test_baseline_three_source_metrics_without_conflict(self) -> None:
        baseline_docs = self.retriever.get_by_ids(["S1", "S2", "S3"])
        baseline_rows = self.extractor.extract_table(baseline_docs)
        _, baseline_conflicts, _ = self.comparator.compare(baseline_rows)

        metrics = self.synthesizer.compute_metrics(baseline_rows, baseline_conflicts)

        # Expected EQI = (1.0 + 0.4 + 0.7) / 3 = 2.1 / 3 = 0.70
        self.assertEqual(metrics.eqi, 0.7)
        self.assertEqual(metrics.severity_max, 0.0)
        self.assertEqual(metrics.reliability_score, 0.7)
        self.assertEqual(metrics.status, "CONVERGENT_WITH_CAVEATS")
        self.assertFalse(metrics.human_review_required)

    def test_lower_tier_evidence_disclosed_not_suppressed(self) -> None:
        # S2 is Tier 3 (vendor blog), verify it is present in the extracted rows
        row_ids = [r.source_id for r in self.rows]
        self.assertIn("S2", row_ids)

        s2_row = [r for r in self.rows if r.source_id == "S2"][0]
        self.assertEqual(s2_row.tier_weight, 0.4)
        self.assertIn("35%", s2_row.key_claim)

    def test_policy_disclaimer_present(self) -> None:
        metrics = self.synthesizer.compute_metrics(self.rows, self.conflicts)
        self.assertIn("Demonstration Policy Disclaimer", metrics.policy_disclaimer)


if __name__ == "__main__":
    unittest.main()
