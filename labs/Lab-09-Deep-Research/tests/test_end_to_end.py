"""End-to-End Integration tests for Lab 9 Deep Research Agent."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.deep_research_agent import DeepResearchAgent


class TestDeepResearchAgentEndToEnd(unittest.TestCase):
    """Verifies complete five-stage workflow, scenario execution, and report artifact generation."""

    def setUp(self) -> None:
        self.agent = DeepResearchAgent()

    def test_e2e_full_four_source_briefing(self) -> None:
        question = "Does Retrieval-Augmented Generation reliably reduce factual hallucinations in LLMs?"
        report = self.agent.conduct_research(
            research_question=question, source_ids=["S1", "S2", "S3", "S4"]
        )

        self.assertEqual(report.research_question, question)
        self.assertEqual(len(report.source_list), 4)
        self.assertEqual(len(report.evidence_table), 4)
        self.assertGreaterEqual(len(report.agreements), 1)
        self.assertEqual(len(report.contradictions), 1)
        self.assertGreaterEqual(len(report.evidence_gaps), 3)
        self.assertGreaterEqual(len(report.recommended_next_questions), 3)

        metrics = report.evaluation_metrics
        self.assertEqual(metrics["eqi"], 0.775)
        self.assertEqual(metrics["reliability_score"], 0.3875)
        self.assertEqual(metrics["status"], "CONTESTED_TIER_1_CONFLICT")
        self.assertTrue(metrics["human_review_required"])

    def test_e2e_baseline_three_source_briefing(self) -> None:
        question = "What is the baseline consensus on RAG accuracy and latency overhead?"
        report = self.agent.conduct_research(
            research_question=question, source_ids=["S1", "S2", "S3"]
        )

        self.assertEqual(len(report.source_list), 3)
        self.assertEqual(len(report.contradictions), 0)
        metrics = report.evaluation_metrics
        self.assertEqual(metrics["eqi"], 0.7)
        self.assertEqual(metrics["reliability_score"], 0.7)
        self.assertFalse(metrics["human_review_required"])

    def test_e2e_markdown_and_json_formatting(self) -> None:
        question = "Faculty Appraisal: Evaluating RAG Factual Grounding Claims"
        report = self.agent.conduct_research(
            research_question=question, source_ids=["S1", "S2", "S3", "S4"]
        )

        md = self.agent.format_markdown(report)
        self.assertIn("# AI Topic Briefing:", md)
        self.assertIn("## 1. Executive Summary", md)
        self.assertIn("## 2. Six-Field Evidence Comparison Table", md)
        self.assertIn("## 3. Cross-Source Analysis", md)
        self.assertIn("## 4. Evidence-Quality Tiering & Evaluation (Assignment 2)", md)
        self.assertIn("## 5. Recommended Next Questions", md)

        # JSON round-trip
        report_dict = report.to_dict()
        json_str = json.dumps(report_dict)
        self.assertIn("CONTESTED_TIER_1_CONFLICT", json_str)

    def test_e2e_save_report_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            question = "Testing Report Artifact Writing"
            report = self.agent.conduct_research(
                research_question=question, source_ids=["S1", "S2", "S3", "S4"]
            )
            md_path, json_path = self.agent.save_report(report, output_dir=tmpdir)

            self.assertTrue(md_path.exists())
            self.assertTrue(json_path.exists())

            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            self.assertIn("AI Topic Briefing:", md_content)

            with open(json_path, "r", encoding="utf-8") as f:
                loaded_json = json.load(f)
            self.assertEqual(loaded_json["evaluation_metrics"]["eqi"], 0.775)


if __name__ == "__main__":
    unittest.main()
