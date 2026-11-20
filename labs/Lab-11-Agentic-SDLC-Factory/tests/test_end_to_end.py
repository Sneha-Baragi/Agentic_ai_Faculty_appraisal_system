"""
End-to-end tests — Lab 11: Agentic SDLC Factory.
Runs all 5 fixture stories through the full pipeline.
Asserts that at least 4 out of 5 complete successfully.
Uses only the Python standard library (unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import StoryStatus
from pipeline.sdlc_pipeline import SDLCPipeline
from tools.story_parser import StoryParser

_CONFIG = {
    "max_complexity": 7,
    "min_coverage": 80.0,
    "min_review_score": 70,
    "deploy_target_staging": "staging.e2e.local",
    "deploy_target_prod": "prod.e2e.local",
    "quality_gate_threshold": 0.9,
    "force_pass": True,  # all TDD tests pass deterministically
}

_FIXTURE_PATH = Path(__file__).parent.parent / "data" / "story_fixtures.json"


class TestEndToEndAllFixtures(unittest.TestCase):
    """Run every fixture story and verify overall pass rate."""

    @classmethod
    def setUpClass(cls) -> None:
        parser = StoryParser()
        cls.stories = parser.parse_file(_FIXTURE_PATH)
        cls.pipeline = SDLCPipeline(_CONFIG)
        cls.reports = [cls.pipeline.run(story) for story in cls.stories]

    def test_all_five_stories_processed(self) -> None:
        """Exactly 5 fixture stories should be processed."""
        self.assertEqual(len(self.reports), 5)

    def test_at_least_four_stories_complete(self) -> None:
        """At least 4 out of 5 stories must reach COMPLETED status."""
        completed = sum(
            1 for r in self.reports if r.final_status == StoryStatus.COMPLETED
        )
        self.assertGreaterEqual(
            completed,
            4,
            msg=(
                f"Expected ≥4/5 stories to complete, "
                f"but only {completed} did.\n"
                + "\n".join(
                    f"  {r.story_id}: {r.final_status.value}" for r in self.reports
                )
            ),
        )

    def test_every_report_has_run_id(self) -> None:
        for report in self.reports:
            self.assertTrue(report.run_id, f"{report.story_id} has empty run_id")

    def test_every_report_has_stage_results(self) -> None:
        for report in self.reports:
            self.assertGreater(
                len(report.stage_results),
                0,
                f"{report.story_id} has no stage results",
            )

    def test_every_report_has_code_artifact(self) -> None:
        for report in self.reports:
            self.assertIsNotNone(
                report.code_artifact,
                f"{report.story_id} missing code_artifact",
            )

    def test_every_report_has_cicd_report(self) -> None:
        for report in self.reports:
            self.assertIsNotNone(
                report.cicd_report,
                f"{report.story_id} missing cicd_report",
            )

    def test_every_report_has_quality_gate(self) -> None:
        for report in self.reports:
            self.assertIsNotNone(
                report.quality_gate,
                f"{report.story_id} missing quality_gate",
            )

    def test_all_run_ids_unique(self) -> None:
        run_ids = [r.run_id for r in self.reports]
        self.assertEqual(
            len(run_ids),
            len(set(run_ids)),
            "Duplicate run IDs detected across pipeline runs",
        )

    def test_total_duration_positive_for_all(self) -> None:
        for report in self.reports:
            self.assertGreater(
                report.total_duration_ms,
                0,
                f"{report.story_id} has non-positive duration",
            )

    def test_simulation_disclaimer_present_for_all(self) -> None:
        for report in self.reports:
            self.assertIn(
                "Simulation",
                report.simulation_disclaimer,
                f"{report.story_id} missing simulation disclaimer",
            )


class TestEndToEndIndividualStories(unittest.TestCase):
    """Individual story assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        parser = StoryParser()
        stories = parser.parse_file(_FIXTURE_PATH)
        pipeline = SDLCPipeline(_CONFIG)
        cls.report_map = {s.story_id: pipeline.run(s) for s in stories}

    def test_us001_jwt_auth_completes(self) -> None:
        report = self.report_map["US-001"]
        self.assertEqual(report.final_status, StoryStatus.COMPLETED)

    def test_us001_has_seven_stages(self) -> None:
        report = self.report_map["US-001"]
        self.assertEqual(len(report.stage_results), 7)

    def test_us002_research_submission_has_tasks(self) -> None:
        report = self.report_map["US-002"]
        self.assertGreater(report.tasks_generated, 0)

    def test_us003_teaching_records_has_tests(self) -> None:
        report = self.report_map["US-003"]
        self.assertGreater(report.test_cases_generated, 0)

    def test_us005_appraisal_score_has_review(self) -> None:
        report = self.report_map["US-005"]
        self.assertIsNotNone(report.review_result)


if __name__ == "__main__":
    unittest.main()
