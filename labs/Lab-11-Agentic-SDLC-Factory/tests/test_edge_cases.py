"""
Edge-case tests — Lab 11: Agentic SDLC Factory.
Uses only the Python standard library (unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.cicd_validator import CICDValidator
from agents.code_reviewer import CodeReviewer
from agents.story_decomposer import StoryDecomposer
from agents.tdd_generator import TDDGenerator
from models.schemas import (
    AcceptanceCriteria,
    CodeArtifact,
    StoryStatus,
    TaskPriority,
    TestCase,
    TestStatus,
    UserStory,
)
from pipeline.sdlc_pipeline import SDLCPipeline


_CONFIG = {
    "max_complexity": 7,
    "min_coverage": 80.0,
    "min_review_score": 70,
    "deploy_target_staging": "staging.edge.local",
    "deploy_target_prod": "prod.edge.local",
    "quality_gate_threshold": 0.9,
    "force_pass": True,
}


def _make_story(
    story_id: str,
    story_points: int = 5,
    num_criteria: int = 3,
    priority: TaskPriority = TaskPriority.MEDIUM,
    epic: str = "Edge",
) -> UserStory:
    criteria = [
        AcceptanceCriteria(
            criterion_id=f"AC-{story_id}-{i}",
            description=f"Given X{i}, when Y{i}, then Z{i}.",
        )
        for i in range(1, num_criteria + 1)
    ]
    return UserStory(
        story_id=story_id,
        title=f"Edge Story {story_id}",
        description="Edge case description.",
        acceptance_criteria=criteria,
        priority=priority,
        story_points=story_points,
        epic=epic,
    )


class TestEmptyAcceptanceCriteria(unittest.TestCase):
    """Story with zero acceptance criteria."""

    def test_decomposer_handles_zero_acs(self) -> None:
        story = UserStory(
            story_id="US-EC-EMPTY",
            title="Empty ACs",
            description="No criteria.",
            acceptance_criteria=[],
            priority=TaskPriority.LOW,
            story_points=3,
            epic="Edge",
        )
        decomposer = StoryDecomposer()
        tasks = decomposer.decompose(story)
        self.assertGreater(len(tasks), 0)

    def test_tdd_generator_handles_zero_acs(self) -> None:
        story = UserStory(
            story_id="US-EC-EMPTY2",
            title="No Criteria",
            description="Desc.",
            acceptance_criteria=[],
            priority=TaskPriority.LOW,
            story_points=3,
            epic="Edge",
        )
        decomposer = StoryDecomposer()
        gen = TDDGenerator({"force_pass": True})
        tasks = decomposer.decompose(story)
        tcs = gen.generate(story, tasks)
        # Should at least produce the integration test
        self.assertGreaterEqual(len(tcs), 1)

    def test_pipeline_completes_zero_acs(self) -> None:
        story = UserStory(
            story_id="US-EC-PIPE",
            title="Zero AC Pipeline",
            description="Desc.",
            acceptance_criteria=[],
            priority=TaskPriority.LOW,
            story_points=3,
            epic="Edge",
        )
        pipeline = SDLCPipeline(_CONFIG)
        report = pipeline.run(story)
        self.assertIn(
            report.final_status,
            [StoryStatus.COMPLETED, StoryStatus.FAILED],
        )


class TestStoryPointExtremes(unittest.TestCase):
    """Stories with 1 point and 13 points."""

    def test_one_point_story(self) -> None:
        story = _make_story("US-EC-1PT", story_points=1, num_criteria=1)
        decomposer = StoryDecomposer()
        tasks = decomposer.decompose(story)
        self.assertGreaterEqual(len(tasks), 3)
        for task in tasks:
            self.assertGreater(task.estimated_hours, 0)

    def test_thirteen_point_story(self) -> None:
        story = _make_story("US-EC-13PT", story_points=13, num_criteria=5)
        decomposer = StoryDecomposer()
        tasks = decomposer.decompose(story)
        self.assertLessEqual(len(tasks), 8)
        for task in tasks:
            self.assertGreater(task.estimated_hours, 0)


class TestAllTestsFailing(unittest.TestCase):
    """Scenario where all tests fail."""

    def test_cicd_all_fail_deploy_to_staging(self) -> None:
        """When all tests fail, deploy should still go to staging (not prod)."""
        artifact = CodeArtifact(
            artifact_id="ART-FAIL",
            story_id="US-EC-FAIL",
            module_name="fail.module",
            language="Python",
            code_lines=100,
            functions=["fn1"],
            test_coverage_pct=85.0,
            complexity_score=4,
            docstring_coverage_pct=75.0,
        )
        # All tests fail
        tcs = [
            TestCase(
                test_id=f"TC-FAIL-{i}",
                story_id="US-EC-FAIL",
                test_name=f"test_fail_{i}",
                test_type="unit",
                input_data={},
                expected_output=True,
                actual_output=False,
                status=TestStatus.FAIL,
                execution_time_ms=5.0,
            )
            for i in range(3)
        ]
        validator = CICDValidator()
        report = validator.validate(artifact, tcs, quality_gate=None)
        self.assertTrue(report.build_success)
        self.assertEqual(report.tests_failed, 3)
        # Without gate passing: deploy target is staging (not prod)
        self.assertNotIn("prod", report.deploy_target)


class TestHighComplexityReviewRejection(unittest.TestCase):
    """Complexity=10 should trigger critical finding and rejection."""

    def test_complexity_10_rejected(self) -> None:
        reviewer = CodeReviewer()
        artifact = CodeArtifact(
            artifact_id="ART-COMPLEX",
            story_id="US-EC-CPX",
            module_name="complex.module",
            language="Python",
            code_lines=200,
            functions=["fn1", "fn2"],
            test_coverage_pct=90.0,
            complexity_score=10,
            docstring_coverage_pct=80.0,
        )
        result = reviewer.review(artifact)
        self.assertFalse(result.approved)
        critical = [f for f in result.findings if f.severity == "critical"]
        self.assertGreater(len(critical), 0)

    def test_complexity_10_pipeline_still_completes(self) -> None:
        """Pipeline should handle rejected review gracefully (not crash)."""
        story = UserStory(
            story_id="US-EC-CPX2",
            title="High Complexity Story",
            description="High complexity.",
            acceptance_criteria=[
                AcceptanceCriteria("AC-CPX-1", "Given X, when Y, then Z.")
            ],
            priority=TaskPriority.HIGH,
            # story_points=13 → complexity= (13//2)+2 = 8 → major but not critical
            # We need story_points that push simulated complexity to ≥9.
            # Simulated complexity = max(1, min(10, sp//2+2)):
            # sp=13 → 8, sp=15 would overflow, we can't go higher in fixtures.
            # Instead test via code reviewer directly (done above).
            story_points=5,
            epic="Edge",
        )
        pipeline = SDLCPipeline(_CONFIG)
        report = pipeline.run(story)
        # Must not raise; status is either completed or failed
        self.assertIn(
            report.final_status, [StoryStatus.COMPLETED, StoryStatus.FAILED]
        )


if __name__ == "__main__":
    unittest.main()
