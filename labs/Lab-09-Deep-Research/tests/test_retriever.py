"""Unit tests for SearchRetriever in Lab 9."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.search_retriever import SearchRetriever
from models.schemas import QualityTier


class TestSearchRetriever(unittest.TestCase):
    """Verifies source retrieval, query filtering, and synthetic metadata preservation."""

    def setUp(self) -> None:
        self.retriever = SearchRetriever()

    def test_retrieve_all_four_official_sources(self) -> None:
        docs = self.retriever.get_all_sources()
        self.assertEqual(len(docs), 4)
        doc_ids = {d.source_id for d in docs}
        self.assertEqual(doc_ids, {"S1", "S2", "S3", "S4"})

    def test_retrieve_by_ids(self) -> None:
        subset = self.retriever.get_by_ids(["S1", "S4"])
        self.assertEqual(len(subset), 2)
        self.assertEqual([d.source_id for d in subset], ["S1", "S4"])

    def test_official_dates_and_source_types(self) -> None:
        doc_map = {d.source_id: d for d in self.retriever.get_all_sources()}
        self.assertEqual(doc_map["S1"].date, "2026-02")
        self.assertEqual(doc_map["S1"].source_type, "peer-reviewed paper")
        self.assertEqual(doc_map["S2"].date, "2026-04")
        self.assertEqual(doc_map["S2"].source_type, "vendor engineering blog")
        self.assertEqual(doc_map["S3"].date, "2026-05")
        self.assertEqual(doc_map["S3"].source_type, "independent benchmark report")
        self.assertEqual(doc_map["S4"].date, "2026-06")
        self.assertEqual(doc_map["S4"].source_type, "peer-reviewed paper")

    def test_mock_and_synthetic_flags_preservation(self) -> None:
        docs = self.retriever.get_all_sources()
        for doc in docs:
            self.assertTrue(doc.is_synthetic)
            self.assertEqual(doc.source_origin, "local_fixture")

        s4 = [d for d in docs if d.source_id == "S4"][0]
        self.assertEqual(
            s4.verification_status,
            "synthetic_demonstration_fixture_not_independently_verified",
        )

    def test_search_query_filtering(self) -> None:
        latency_results = self.retriever.search("latency overhead")
        self.assertTrue(any(d.source_id == "S3" for d in latency_results))

        hallucination_results = self.retriever.search("hallucination reduction")
        self.assertTrue(any(d.source_id in {"S1", "S4"} for d in hallucination_results))


if __name__ == "__main__":
    unittest.main()
