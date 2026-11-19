"""Unit tests for EvidenceComparator in Lab 9."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.comparator import EvidenceComparator
from agent.extractor import EvidenceExtractor
from agent.search_retriever import SearchRetriever


class TestEvidenceComparator(unittest.TestCase):
    """Verifies agreement detection, Assignment 1 contradiction analysis, and gap extraction."""

    def setUp(self) -> None:
        self.retriever = SearchRetriever()
        self.extractor = EvidenceExtractor()
        self.comparator = EvidenceComparator()
        self.docs = self.retriever.get_all_sources()
        self.rows = self.extractor.extract_table(self.docs)

    def test_detect_s1_vs_s4_genuine_contradiction(self) -> None:
        agreements, conflicts, gaps = self.comparator.compare(self.rows)
        self.assertEqual(len(conflicts), 1)

        c = conflicts[0]
        self.assertEqual(c.source_a, "S1")
        self.assertEqual(c.source_b, "S4")
        self.assertEqual(c.conflict_type, "GENUINE_CONTRADICTION")
        self.assertEqual(c.severity, 1.0)
        self.assertIn("Factual Hallucination Rate Impact", c.metric)

    def test_contradiction_explains_root_causes(self) -> None:
        _, conflicts, _ = self.comparator.compare(self.rows)
        c = conflicts[0]
        reasons = c.contradiction_reasons

        self.assertIn("methodology", reasons)
        self.assertIn("domain", reasons)
        self.assertIn("dataset_size", reasons)
        self.assertIn("retrieval_noise_sensitivity", reasons)

        self.assertIn("single-hop", reasons["methodology"])
        self.assertIn("multi-hop", reasons["methodology"])
        self.assertIn("medical", reasons["domain"])
        self.assertIn("200 questions", reasons["dataset_size"])
        self.assertIn("8,000 questions", reasons["dataset_size"])

    def test_distinguishes_conflict_from_evidence_gap(self) -> None:
        _, conflicts, gaps = self.comparator.compare(self.rows)
        # S1 vs S4 is a genuine conflict
        self.assertEqual(conflicts[0].conflict_type, "GENUINE_CONTRADICTION")

        # Gaps are kept separate
        gap_sources = {g.source_id for g in gaps}
        self.assertIn("S1", gap_sources)
        self.assertIn("S2", gap_sources)
        self.assertIn("S3", gap_sources)
        self.assertIn("S4", gap_sources)

    def test_detect_agreements_between_s1_and_s2(self) -> None:
        agreements, _, _ = self.comparator.compare(self.rows)
        topics = [a.topic for a in agreements]
        self.assertTrue(any("Factual Grounding" in t for t in topics))


if __name__ == "__main__":
    unittest.main()
