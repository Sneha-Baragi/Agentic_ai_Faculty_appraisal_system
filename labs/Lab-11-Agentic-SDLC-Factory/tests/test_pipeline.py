"""
Tests for SDLCPipeline — Lab 11: Agentic SDLC Factory.
Uses only the Python standard library (unittest).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import AcceptanceCriteria, StoryStatus, TaskPriority, UserStory
from pipeline.sdlc_pipeline import SDLCPipeline


_DEFAULT_CONFIG = {
    "max_complexity": 7,
    "min_coverage": 80.0,
    "min_review_score": 70,
    "deploy_target_staging": "staging.test.local",
    "deploy_target_prod": "prod.test.local",
    "quality_gate_threshold": 0.9,
    "force_pass": True,  # make TDD tests deterministically pass
}


def _make_story(
    story_id: str,
    story_points: int = 5,
    num_criteria: int = 3,
    epic: str = "TestEpic",
) -> UserStory:
    criteria = [
        AcceptanceCriteria(
            criterion_id=f"AC-{story_id}-{i}",
            description=f"Given state{i}, when action{i}, then result{i}.",
        )
        for i in range(1, num_criteria + 1)
    ]
    return UserStory(
        story_id=story_id,
        title=f"Pipeline Test Story {story_id}",
        description="Pipeline test.",
        acceptance_criteria=criteria,
        priority=TaskPriority.MEDIUM,
        story_points=story_points,
        epic=epic,
    )


class TestPipelineReportFields(unittest.TestCase):
    """Verify that SDLCFactoryReport has all required fields populated."""

    def setUp(self) -> None:
        self.pipeline = SDLCPipeline(_DEFAULT_CONFIG)
        self.story = _make_story("US-P01")
        self.report = self.pipeline.run(self.story)

    def test_run_id_is_non_empty(self) -> None:
        self.assertTrue(self.report.run_id)
        self.assertGreater(len(self.report.run_id), 0)

    def test_story_id_matches(self) -> None:
        self.assertEqual(self.report.story_id, "US-P01")

    def test_story_title_matches(self) -> None:
        self.assertEqual(self.report.story_title, self.story.title)

    def test_pipeline_timestamps_set(self) -> None:
        self.assertTrue(self.report.pipeline_start)
        self.assertTrue(self.report.pipeline_end)

    def test_total_duration_positive(self) -> None:
        self.assertGreater(self.report.total_duration_ms, 0)

    def test_stage_results_populated(self) -> None:
        self.assertGreater(len(self.report.stage_results), 0)

    def test_tasks_generated_positive(self) -> None:
        self.assertGreater(self.report.tasks_generated, 0)

    def test_test_cases_generated_positive(self) -> None:
        self.assertGreater(self.report.test_cases_generated, 0)

    def test_code_artifact_not_none(self) -> None:
        self.assertIsNotNone(self.report.code_artifact)

    def test_review_result_not_none(self) -> None:
        self.assertIsNotNone(self.report.review_result)

    def test_cicd_report_not_none(self) -> None:
        self.assertIsNotNone(self.report.cicd_report)

    def test_quality_gate_not_none(self) -> None:
        self.assertIsNotNone(self.report.quality_gate)

    def test_simulation_disclaimer_present(self) -> None:
        self.assertIn("Simulation", self.report.simulation_disclaimer)

    def test_to_dict_is_json_serialisable(self) -> None:
        data = self.report.to_dict()
        # Should not raise
        json.dumps(data, default=str)


class TestPipelineRunIdUniqueness(unittest.TestCase):
    """Verify that each pipeline run produces a unique run_id."""

    def test_run_ids_unique_per_run(self) -> None:
        pipeline = SDLCPipeline(_DEFAULT_CONFIG)
        story = _make_story("US-P02")
        report1 = pipeline.run(story)
        report2 = pipeline.run(story)
        self.assertNotEqual(report1.run_id, report2.run_id)


class TestPipelineAllSevenStages(unittest.TestCase):
    """Verify that all 7 pipeline stages produce results."""

    def test_seven_stages_present(self) -> None:
        pipeline = SDLCPipeline(_DEFAULT_CONFIG)
        story = _make_story("US-P03", story_points=5, num_criteria=3)
        report = pipeline.run(story)
        self.assertEqual(len(report.stage_results), 7)

    def test_all_stage_durations_positive(self) -> None:
        pipeline = SDLCPipeline(_DEFAULT_CONFIG)
        story = _make_story("US-P04")
        report = pipeline.run(story)
        for sr in report.stage_results:
            self.assertGreaterEqual(sr.duration_ms, 0)


if __name__ == "__main__":
    unittest.main()
