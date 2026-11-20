"""Unit tests for EvidenceExtractor in Lab 9."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.extractor import EvidenceExtractor
from agent.search_retriever import SearchRetriever


class TestEvidenceExtractor(unittest.TestCase):
    """Verifies six-field extraction completeness and anti-fabrication constraints."""

    def setUp(self) -> None:
        self.retriever = SearchRetriever()
        self.extractor = EvidenceExtractor()
        self.docs = self.retriever.get_all_sources()

    def test_extract_all_six_required_fields(self) -> None:
        table = self.extractor.extract_table(self.docs)
        self.assertEqual(len(table), 4)

        for row in table:
            self.assertTrue(row.source_id in {"S1", "S2", "S3", "S4"})
            self.assertTrue(row.source_date != "")
            self.assertTrue(row.author_organization != "")
            self.assertTrue(row.key_claim != "")
            self.assertTrue(row.evidence != "")
            self.assertTrue(row.limitation != "")
            self.assertTrue(row.relevance != "")
            self.assertTrue(row.tier != "")
            self.assertIn(row.tier_weight, {1.0, 0.7, 0.4})

    def test_official_claims_extracted_verbatim(self) -> None:
        row_map = {r.source_id: r for r in self.extractor.extract_table(self.docs)}
        # S1: RAG reduces hallucination by 41%
        self.assertIn("41%", row_map["S1"].key_claim)
        self.assertIn("200 held-out questions", row_map["S1"].evidence)

        # S2: RAG improves accuracy by 35% over 10,000 support tickets
        self.assertIn("35%", row_map["S2"].key_claim)
        self.assertIn("10,000 support tickets", row_map["S2"].evidence)

        # S3: RAG adds 200–400 ms latency across five open-source pipelines
        self.assertIn("200–400 ms", row_map["S3"].key_claim)
        self.assertIn("five open-source RAG pipelines", row_map["S3"].evidence)

        # S4: RAG does not reduce hallucination by 41%; increases by 12% to 15%
        self.assertIn("12% to 15%", row_map["S4"].key_claim)
        self.assertIn("8,000 multi-hop reasoning questions", row_map["S4"].evidence)

    def test_anti_fabrication_unspecified_authors(self) -> None:
        row_map = {r.source_id: r for r in self.extractor.extract_table(self.docs)}
        # For S2 and S3, author was not stated in source
        self.assertIn("Enterprise AI Platform Engineering Blog", row_map["S2"].author_organization)
        self.assertIn("Open Benchmark Consortium", row_map["S3"].author_organization)


if __name__ == "__main__":
    unittest.main()
