"""
Tests for StoryDecomposer — Lab 11: Agentic SDLC Factory.
Uses only the Python standard library (unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.story_decomposer import StoryDecomposer
from models.schemas import AcceptanceCriteria, StoryStatus, TaskPriority, UserStory


def _make_story(
    story_id: str = "US-001",
    story_points: int = 5,
    num_criteria: int = 3,
    priority: TaskPriority = TaskPriority.HIGH,
    epic: str = "TestEpic",
) -> UserStory:
    criteria = [
        AcceptanceCriteria(
            criterion_id=f"AC-{story_id}-{i}",
            description=f"Given X, when Y, then Z number {i}.",
        )
        for i in range(1, num_criteria + 1)
    ]
    return UserStory(
        story_id=story_id,
        title=f"Test Story {story_id}",
        description="A test story description.",
        acceptance_criteria=criteria,
        priority=priority,
        story_points=story_points,
        epic=epic,
    )


class TestStoryDecomposerTaskCount(unittest.TestCase):
    """Verify correct task count for different story sizes."""

    def setUp(self) -> None:
        self.decomposer = StoryDecomposer()

    def test_small_story_min_tasks(self) -> None:
        """1-point story should produce 3 tasks (base minimum)."""
        story = _make_story(story_points=1, num_criteria=1)
        tasks = self.decomposer.decompose(story)
        self.assertGreaterEqual(len(tasks), 3)

    def test_medium_story_task_count(self) -> None:
        """5-point story with 3 ACs should produce at least 5 tasks."""
        story = _make_story(story_points=5, num_criteria=3)
        tasks = self.decomposer.decompose(story)
        self.assertGreaterEqual(len(tasks), 5)

    def test_large_story_task_count(self) -> None:
        """8-point story with 4 ACs should produce ≥6 tasks."""
        story = _make_story(story_points=8, num_criteria=4)
        tasks = self.decomposer.decompose(story)
        self.assertGreaterEqual(len(tasks), 6)

    def test_max_tasks_capped_at_eight(self) -> None:
        """Very large story should never exceed 8 tasks."""
        story = _make_story(story_points=13, num_criteria=10)
        tasks = self.decomposer.decompose(story)
        self.assertLessEqual(len(tasks), 8)


class TestStoryDecomposerTaskTypes(unittest.TestCase):
    """Verify that task types are from the allowed set."""

    _VALID_TYPES = {
        "setup",
        "implementation",
        "unit_test",
        "integration_test",
        "review",
        "documentation",
    }

    def setUp(self) -> None:
        self.decomposer = StoryDecomposer()

    def test_all_task_types_valid(self) -> None:
        story = _make_story(story_points=8, num_criteria=4)
        tasks = self.decomposer.decompose(story)
        for task in tasks:
            self.assertIn(
                task.task_type,
                self._VALID_TYPES,
                f"Unexpected task_type: {task.task_type}",
            )

    def test_setup_task_first(self) -> None:
        """The first task should always be a 'setup' task."""
        story = _make_story(story_points=5)
        tasks = self.decomposer.decompose(story)
        self.assertEqual(tasks[0].task_type, "setup")

    def test_implementation_task_present(self) -> None:
        story = _make_story(story_points=5)
        tasks = self.decomposer.decompose(story)
        types = [t.task_type for t in tasks]
        self.assertIn("implementation", types)


class TestStoryDecomposerTaskFields(unittest.TestCase):
    """Verify that all required fields are populated correctly."""

    def setUp(self) -> None:
        self.decomposer = StoryDecomposer()
        self.story = _make_story("US-042", story_points=5, num_criteria=3)
        self.tasks = self.decomposer.decompose(self.story)

    def test_all_tasks_have_story_id(self) -> None:
        for task in self.tasks:
            self.assertEqual(task.story_id, "US-042")

    def test_all_tasks_have_positive_hours(self) -> None:
        for task in self.tasks:
            self.assertGreater(
                task.estimated_hours, 0, f"Task {task.task_id} has non-positive hours"
            )

    def test_task_ids_are_unique(self) -> None:
        ids = [t.task_id for t in self.tasks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_initial_status_is_pending(self) -> None:
        for task in self.tasks:
            self.assertEqual(task.status, StoryStatus.PENDING)

    def test_dependencies_are_lists(self) -> None:
        for task in self.tasks:
            self.assertIsInstance(task.dependencies, list)

    def test_task_titles_contain_story_id(self) -> None:
        for task in self.tasks:
            self.assertIn("US-042", task.title)


class TestStoryDecomposerDeterminism(unittest.TestCase):
    """Verify that decomposition is deterministic."""

    def test_same_story_same_tasks(self) -> None:
        decomposer = StoryDecomposer()
        story = _make_story(story_points=5, num_criteria=3)
        tasks1 = decomposer.decompose(story)
        tasks2 = decomposer.decompose(story)
        self.assertEqual(
            [t.task_id for t in tasks1],
            [t.task_id for t in tasks2],
        )
        self.assertEqual(
            [t.estimated_hours for t in tasks1],
            [t.estimated_hours for t in tasks2],
        )


if __name__ == "__main__":
    unittest.main()
