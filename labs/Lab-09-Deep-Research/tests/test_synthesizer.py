"""Unit tests for EvidenceSynthesizer in Lab 9."""

import re
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


class TestEvidenceSynthesizer(unittest.TestCase):
    """Verifies executive summary generation, inline citations, and next question synthesis."""

    def setUp(self) -> None:
        self.retriever = SearchRetriever()
        self.extractor = EvidenceExtractor()
        self.comparator = EvidenceComparator()
        self.synthesizer = EvidenceSynthesizer()
        self.docs = self.retriever.get_all_sources()
        self.rows = self.extractor.extract_table(self.docs)
        self.agreements, self.conflicts, self.gaps = self.comparator.compare(self.rows)
        self.metrics = self.synthesizer.compute_metrics(self.rows, self.conflicts)

    def test_executive_summary_contains_bracketed_source_citations(self) -> None:
        question = "Does RAG reduce factual hallucinations?"
        summary = self.synthesizer.generate_executive_summary(
            question, self.rows, self.agreements, self.conflicts, self.gaps, self.metrics
        )

        # Asserts presence of [S1], [S2], [S3], [S4]
        for sid in ["S1", "S2", "S3", "S4"]:
            pattern = rf"\[{sid}\]"
            self.assertTrue(
                bool(re.search(pattern, summary)),
                f"Missing citation [{sid}] in executive summary",
            )

    def test_summary_highlights_assignment_1_and_2(self) -> None:
        question = "Does RAG reduce factual hallucinations?"
        summary = self.synthesizer.generate_executive_summary(
            question, self.rows, self.agreements, self.conflicts, self.gaps, self.metrics
        )

        # Assignment 1 contradiction
        self.assertIn("contradiction", summary.lower())
        self.assertIn("multi-hop", summary.lower())

        # Assignment 2 tiering and disclosure
        self.assertIn("tier 3", summary.lower())
        self.assertIn("disclosed", summary.lower())

        # Latency mention
        self.assertIn("200–400 ms", summary)

    def test_recommended_next_questions_generated(self) -> None:
        questions = self.synthesizer.generate_recommended_next_questions(
            self.rows, self.conflicts
        )
        self.assertGreaterEqual(len(questions), 3)
        for q in questions:
            self.assertTrue(q.endswith("?"))

    def test_human_review_flag_enforced_under_conflict(self) -> None:
        self.assertTrue(self.metrics.human_review_required)
        self.assertIn("CONTESTED_TIER_1_CONFLICT", self.metrics.status)


if __name__ == "__main__":
    unittest.main()
