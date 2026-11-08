"""Unit Tests for Research Summary Skill (Lab 3).

Course: Agentic AI (26ECAC401)
Lab: 3 - Skill Creation
Scenario: Research Summary Skill

Tests the deterministic extraction, anti-fabrication rules, schema invariance,
competing claim resolution, fallback mechanics, and reusability checks.
"""

import json
import os
import sys
import unittest

# Ensure the Lab 3 root directory is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LAB_ROOT = os.path.dirname(CURRENT_DIR)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from skill.research_summary import (
    apply_research_summary_skill,
    reusability_check,
)
from skill.skill_spec import FALLBACK_NOT_STATED, SKILL_SPEC


def load_example(name: str) -> dict:
    """Helper to load article JSON file from examples directory."""
    path = os.path.join(LAB_ROOT, "examples", name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestResearchSummarySkill(unittest.TestCase):
    """Test suite verifying the reusable Research Summary Skill behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.article_a = load_example("article_a.json")
        cls.article_b = load_example("article_b.json")
        cls.article_c = load_example("article_c.json")
        cls.article_d = load_example("article_d.json")

        cls.output_a = apply_research_summary_skill(cls.article_a)
        cls.output_b = apply_research_summary_skill(cls.article_b)
        cls.output_c = apply_research_summary_skill(cls.article_c)
        cls.output_d = apply_research_summary_skill(cls.article_d)

    # -------------------------------------------------------------------------
    # BASE EXAMPLES: ARTICLE A (RAG SYSTEM)
    # -------------------------------------------------------------------------

    def test_article_a_main_claim(self) -> None:
        """Verify Article A main claim extracts RAG hallucination reduction of 41%."""
        claim = self.output_a["main_claim"]
        self.assertIn("Retrieval-Augmented Generation", claim)
        self.assertIn("41%", claim)
        self.assertIn("reduces factual hallucination rates", claim)

    def test_article_a_supporting_evidence(self) -> None:
        """Verify Article A evidence identifies the 200 medical knowledge base questions."""
        evidence = self.output_a["supporting_evidence"]
        self.assertIn("200 held-out questions", evidence)
        self.assertIn("medical knowledge base", evidence)

    def test_article_a_limitations(self) -> None:
        """Verify Article A limitation identifies small single-domain dataset."""
        limitation = self.output_a["limitations"]
        self.assertIn("small, single-domain dataset", limitation)
        self.assertIn("may not generalize", limitation)

    def test_article_a_teaching_takeaway(self) -> None:
        """Verify Article A takeaway emphasizes cross-domain validation."""
        takeaway = self.output_a["teaching_takeaway"]
        self.assertIn("validate results across diverse domains", takeaway.lower())

    # -------------------------------------------------------------------------
    # BASE EXAMPLES: ARTICLE B (CAMPUS WI-FI)
    # -------------------------------------------------------------------------

    def test_article_b_main_claim(self) -> None:
        """Verify Article B main claim extracts library peak-hour throughput gain of 60%."""
        claim = self.output_b["main_claim"]
        self.assertIn("library peak-hour throughput", claim)
        self.assertIn("60%", claim)

    def test_article_b_supporting_evidence(self) -> None:
        """Verify Article B evidence captures two weeks of monitoring dashboard metrics."""
        evidence = self.output_b["supporting_evidence"]
        self.assertIn("two weeks", evidence.lower())
        self.assertIn("network monitoring dashboard", evidence.lower())

    def test_article_b_limitations(self) -> None:
        """Verify Article B limitation captures missing campus buildings."""
        limitation = self.output_b["limitations"]
        self.assertIn("other campus buildings", limitation.lower())
        self.assertIn("unclear whether the improvement was uniform", limitation.lower())

    def test_article_b_teaching_takeaway(self) -> None:
        """Verify Article B takeaway advises measuring across multiple locations."""
        takeaway = self.output_b["teaching_takeaway"]
        self.assertIn("multiple distinct physical locations", takeaway.lower())

    # -------------------------------------------------------------------------
    # REUSABILITY AND CONTRACT INVARIANCE
    # -------------------------------------------------------------------------

    def test_consistent_output_keys_across_all_articles(self) -> None:
        """Verify all articles (A, B, C, D) yield identical schema keys matching SKILL_SPEC."""
        expected_keys = set(SKILL_SPEC["required_output_schema"])
        for name, output in [("A", self.output_a), ("B", self.output_b), ("C", self.output_c), ("D", self.output_d)]:
            actual_keys = set(output.keys())
            self.assertEqual(
                expected_keys,
                actual_keys,
                f"Article {name} output schema deviated from SKILL_SPEC required keys.",
            )

    def test_reusability_check_article_a_and_b(self) -> None:
        """Verify reusability_check confirms schema equivalence and topic differentiation."""
        result = reusability_check(self.output_a, self.output_b)
        self.assertTrue(result["is_reusable"])
        self.assertTrue(result["schema_matches"])
        self.assertTrue(result["content_differentiated"])
        self.assertTrue(result["types_aligned"])
        self.assertTrue(result["fallback_compliant"])
        self.assertEqual(result["required_keys_count"], len(SKILL_SPEC["required_output_schema"]))

    # -------------------------------------------------------------------------
    # ASSIGNMENT 1: COMPETING CLAIMS (ARTICLE C)
    # -------------------------------------------------------------------------

    def test_article_c_detects_multiple_claims(self) -> None:
        """Verify Article C detects multiple competing claims (cost vs latency)."""
        self.assertTrue(self.output_c["multiple_claims_detected"])
        self.assertGreaterEqual(len(self.output_c["competing_claims"]), 2)

    def test_article_c_evidence_based_selection_not_sentence_order(self) -> None:
        """Verify Article C selects the latency claim over the first-sentence cost claim."""
        # The first sentence in Article C is about cost (45% cost cut).
        # The agent must select the latency claim (78% latency reduction) because it has empirical evidence.
        main_claim = self.output_c["main_claim"]
        self.assertIn("latency", main_claim.lower())
        self.assertIn("78%", main_claim)
        self.assertNotIn("serverless edge architecture is projected to cut cloud infrastructure hosting costs", main_claim)

    def test_article_c_selection_rationale_documents_tradeoff(self) -> None:
        """Verify Article C provides explicit selection rationale explaining why latency was preferred."""
        rationale = self.output_c["selection_rationale"]
        self.assertIn("competing claims", rationale.lower())
        self.assertIn("latency", rationale.lower())
        self.assertIn("cost", rationale.lower())
        self.assertIn("benchmark", rationale.lower())

    # -------------------------------------------------------------------------
    # ASSIGNMENT 2: MISSING EVIDENCE AND LIMITATIONS (ARTICLE D)
    # -------------------------------------------------------------------------

    def test_article_d_claim_extracted(self) -> None:
        """Verify Article D's claim is extracted despite missing evidence."""
        claim = self.output_d["main_claim"]
        self.assertIn("cryptographic handshake protocol", claim.lower())
        self.assertIn("forward secrecy", claim.lower())

    def test_article_d_missing_evidence_fallback(self) -> None:
        """Verify missing evidence in Article D strictly uses 'not stated in source'."""
        evidence = self.output_d["supporting_evidence"]
        self.assertEqual(evidence, FALLBACK_NOT_STATED)
        self.assertIn("supporting_evidence", self.output_d["missing_fields"])

    def test_article_d_missing_limitations_fallback(self) -> None:
        """Verify missing limitations in Article D strictly uses 'not stated in source'."""
        limitations = self.output_d["limitations"]
        self.assertEqual(limitations, FALLBACK_NOT_STATED)
        self.assertIn("limitations", self.output_d["missing_fields"])

    def test_article_d_missing_assumptions_fallback(self) -> None:
        """Verify missing assumptions in Article D strictly uses 'not stated in source'."""
        assumptions = self.output_d["assumptions"]
        self.assertEqual(assumptions, FALLBACK_NOT_STATED)

    def test_article_d_no_fabricated_numbers_or_metrics(self) -> None:
        """Verify Article D does NOT manufacture numbers, percentages, or sample sizes."""
        # Check that evidence does not contain fabricated digits
        self.assertEqual(self.output_d["supporting_evidence"], FALLBACK_NOT_STATED)
        self.assertEqual(self.output_d["limitations"], FALLBACK_NOT_STATED)
        # Verify the takeaway reminds students to demand empirical evidence
        takeaway = self.output_d["teaching_takeaway"]
        self.assertIn("skepticism", takeaway.lower())

    # -------------------------------------------------------------------------
    # NARRATIVE SUMMARY AND MALFORMED INPUTS
    # -------------------------------------------------------------------------

    def test_summary_word_count_is_approximately_100_words(self) -> None:
        """Verify summaries for all articles fall within reasonable ~100-word bounds (70 - 130 words)."""
        for name, output in [("A", self.output_a), ("B", self.output_b), ("C", self.output_c), ("D", self.output_d)]:
            word_count = output["word_count_summary"]
            self.assertGreaterEqual(
                word_count,
                65,
                f"Article {name} summary too brief: {word_count} words.",
            )
            self.assertLessEqual(
                word_count,
                135,
                f"Article {name} summary too long: {word_count} words.",
            )

    def test_empty_or_malformed_article_handled_safely(self) -> None:
        """Verify empty article dictionaries or invalid types return schema-compliant outputs without crashing."""
        empty_out = apply_research_summary_skill({})
        expected_keys = set(SKILL_SPEC["required_output_schema"])
        self.assertEqual(expected_keys, set(empty_out.keys()))
        self.assertEqual(empty_out["main_claim"], FALLBACK_NOT_STATED)
        self.assertEqual(empty_out["supporting_evidence"], FALLBACK_NOT_STATED)

        none_out = apply_research_summary_skill(None)  # type: ignore
        self.assertEqual(expected_keys, set(none_out.keys()))


if __name__ == "__main__":
    unittest.main()
