"""
Tests for TDDGenerator — Lab 11: Agentic SDLC Factory.
Uses only the Python standard library (unittest).
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.story_decomposer import StoryDecomposer
from agents.tdd_generator import TDDGenerator
from models.schemas import AcceptanceCriteria, TaskPriority, TestStatus, UserStory


def _make_story(
    story_id: str = "US-T01",
    story_points: int = 5,
    num_criteria: int = 3,
    epic: str = "Auth",
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
        title=f"Story {story_id}",
        description="Description.",
        acceptance_criteria=criteria,
        priority=TaskPriority.HIGH,
        story_points=story_points,
        epic=epic,
    )


class TestTDDGeneratorTestCount(unittest.TestCase):
    """Verify that the correct number of test cases is generated."""

    def setUp(self) -> None:
        self.gen = TDDGenerator({"force_pass": True})
        self.decomposer = StoryDecomposer()

    def test_one_unit_test_per_criterion(self) -> None:
        story = _make_story(num_criteria=3)
        tasks = self.decomposer.decompose(story)
        tcs = self.gen.generate(story, tasks)
        unit_tests = [tc for tc in tcs if tc.test_type == "unit"]
        self.assertEqual(len(unit_tests), 3)

    def test_at_least_one_integration_test(self) -> None:
        story = _make_story(num_criteria=2)
        tasks = self.decomposer.decompose(story)
        tcs = self.gen.generate(story, tasks)
        int_tests = [tc for tc in tcs if tc.test_type == "integration"]
        self.assertGreaterEqual(len(int_tests), 1)

    def test_e2e_test_for_large_story(self) -> None:
        """Stories with ≥4 ACs should get an e2e test."""
        story = _make_story(num_criteria=4)
        tasks = self.decomposer.decompose(story)
        tcs = self.gen.generate(story, tasks)
        e2e_tests = [tc for tc in tcs if tc.test_type == "e2e"]
        self.assertGreaterEqual(len(e2e_tests), 1)

    def test_no_e2e_for_small_story(self) -> None:
        """Stories with <4 ACs should NOT get an e2e test."""
        story = _make_story(num_criteria=3)
        tasks = self.decomposer.decompose(story)
        tcs = self.gen.generate(story, tasks)
        e2e_tests = [tc for tc in tcs if tc.test_type == "e2e"]
        self.assertEqual(len(e2e_tests), 0)


class TestTDDGeneratorTestNames(unittest.TestCase):
    """Verify test-name conventions."""

    _NAME_PATTERN = re.compile(r"^test_[a-z]+_[a-z0-9_]+$")

    def setUp(self) -> None:
        self.gen = TDDGenerator({"force_pass": True})
        self.decomposer = StoryDecomposer()

    def test_unit_test_names_follow_convention(self) -> None:
        story = _make_story(num_criteria=3)
        tasks = self.decomposer.decompose(story)
        tcs = self.gen.generate(story, tasks)
        for tc in tcs:
            self.assertTrue(
                tc.test_name.startswith("test_"),
                f"Test name '{tc.test_name}' does not start with 'test_'",
            )


class TestTDDGeneratorTestFields(unittest.TestCase):
    """Verify test case fields are correctly populated."""

    def setUp(self) -> None:
        self.gen = TDDGenerator({"force_pass": True})
        self.decomposer = StoryDecomposer()
        self.story = _make_story("US-TF1", num_criteria=3)
        self.tasks = self.decomposer.decompose(self.story)
        self.tcs = self.gen.generate(self.story, self.tasks)

    def test_all_test_cases_have_story_id(self) -> None:
        for tc in self.tcs:
            self.assertEqual(tc.story_id, "US-TF1")

    def test_all_test_cases_have_status_set(self) -> None:
        for tc in self.tcs:
            self.assertIn(tc.status, list(TestStatus))

    def test_all_test_cases_have_input_data(self) -> None:
        for tc in self.tcs:
            self.assertIsInstance(tc.input_data, dict)
            self.assertGreater(len(tc.input_data), 0)

    def test_expected_output_not_none(self) -> None:
        for tc in self.tcs:
            self.assertIsNotNone(tc.expected_output)

    def test_test_ids_are_unique(self) -> None:
        ids = [tc.test_id for tc in self.tcs]
        self.assertEqual(len(ids), len(set(ids)))


class TestTDDGeneratorForcePass(unittest.TestCase):
    """Verify force_pass config overrides failure simulation."""

    def test_force_pass_all_tests_pass(self) -> None:
        gen = TDDGenerator({"force_pass": True})
        decomposer = StoryDecomposer()
        story = _make_story("US-FP", num_criteria=3)
        tasks = decomposer.decompose(story)
        tcs = gen.generate(story, tasks)
        failing = [tc for tc in tcs if tc.status == TestStatus.FAIL]
        self.assertEqual(len(failing), 0, "force_pass should prevent any FAIL status")

    def test_execution_time_positive(self) -> None:
        gen = TDDGenerator({"force_pass": True})
        decomposer = StoryDecomposer()
        story = _make_story(num_criteria=3)
        tasks = decomposer.decompose(story)
        tcs = gen.generate(story, tasks)
        for tc in tcs:
            self.assertGreater(tc.execution_time_ms, 0)


if __name__ == "__main__":
    unittest.main()
