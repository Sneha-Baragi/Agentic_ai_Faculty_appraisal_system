"""
Story Decomposer Agent — Lab 11: Agentic SDLC Factory.

Deterministically decomposes a UserStory into an ordered list of Tasks.
No LLM or external API calls are made; decomposition rules are based on
story points and acceptance-criteria count.
"""
from __future__ import annotations

import logging
from typing import Any

from models.schemas import StoryStatus, Task, TaskPriority, UserStory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task-type catalogue ordered by pipeline phase
# ---------------------------------------------------------------------------
_TASK_TYPES: list[tuple[str, str, float]] = [
    # (task_type, title_template, base_hours)
    ("setup", "Project Setup & Environment Configuration", 1.0),
    ("implementation", "Core Implementation", 3.0),
    ("unit_test", "Unit Test Implementation", 2.0),
    ("integration_test", "Integration Test Implementation", 2.0),
    ("review", "Code Review & Refactoring", 1.5),
    ("documentation", "Documentation & Docstrings", 1.0),
]


class StoryDecomposer:
    """Agent that breaks a UserStory into concrete Tasks.

    Rules
    -----
    * Stories with **1–3 points** get 3 tasks (setup, implementation, unit_test).
    * Stories with **4–7 points** get 5 tasks (adds integration_test, review).
    * Stories with **8+ points** get all 6 tasks.
    * Additionally, one extra task is generated per acceptance criterion beyond
      the first (capped so the total never exceeds 8 tasks).
    * ``estimated_hours`` scales linearly with story points.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise the StoryDecomposer.

        Args:
            config: Optional configuration dictionary (unused today; reserved
                for future tuning of hour-estimation multipliers).
        """
        self.config: dict[str, Any] = config or {}
        logger.debug("StoryDecomposer initialised with config: %s", self.config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decompose(self, story: UserStory) -> list[Task]:
        """Decompose *story* into an ordered list of Tasks.

        Args:
            story: The user story to decompose.

        Returns:
            An ordered list of :class:`~models.schemas.Task` objects whose
            ``story_id`` matches ``story.story_id``.
        """
        logger.info(
            "Decomposing story %s (%s, %d pts, %d ACs)",
            story.story_id,
            story.title,
            story.story_points,
            len(story.acceptance_criteria),
        )

        base_task_count = self._base_task_count(story.story_points)
        ac_extra = max(0, len(story.acceptance_criteria) - 1)
        total_tasks = min(base_task_count + ac_extra, 8)

        logger.debug(
            "Story %s → base=%d, ac_extra=%d, total=%d tasks",
            story.story_id,
            base_task_count,
            ac_extra,
            total_tasks,
        )

        hours_multiplier = self._hours_multiplier(story.story_points)
        selected_types = _TASK_TYPES[:total_tasks]

        tasks: list[Task] = []
        previous_task_ids: list[str] = []

        for idx, (task_type, title_template, base_hours) in enumerate(
            selected_types, start=1
        ):
            task_id = f"{story.story_id}-T{idx:02d}"
            estimated_hours = round(base_hours * hours_multiplier, 1)
            description = self._build_description(
                task_type, story, title_template
            )

            task = Task(
                task_id=task_id,
                story_id=story.story_id,
                title=f"[{story.story_id}] {title_template}",
                description=description,
                task_type=task_type,
                estimated_hours=estimated_hours,
                dependencies=list(previous_task_ids),
                status=StoryStatus.PENDING,
            )
            tasks.append(task)
            previous_task_ids.append(task_id)

            logger.debug(
                "  Created task %s (%s, %.1f hrs)", task_id, task_type, estimated_hours
            )

        logger.info(
            "Story %s decomposed into %d tasks (%.1f total hrs)",
            story.story_id,
            len(tasks),
            sum(t.estimated_hours for t in tasks),
        )
        return tasks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _base_task_count(story_points: int) -> int:
        """Return the base number of tasks for a given story-point estimate."""
        if story_points <= 3:
            return 3
        if story_points <= 7:
            return 5
        return 6

    @staticmethod
    def _hours_multiplier(story_points: int) -> float:
        """Return an hours multiplier proportional to story points."""
        if story_points <= 2:
            return 0.5
        if story_points <= 5:
            return 1.0
        if story_points <= 8:
            return 1.5
        return 2.0

    @staticmethod
    def _build_description(
        task_type: str, story: UserStory, title_template: str
    ) -> str:
        """Build a human-readable task description.

        Args:
            task_type: One of the canonical task type strings.
            story: The parent user story.
            title_template: Short template title for the task.

        Returns:
            A multi-sentence description string.
        """
        base = f"[{story.story_id}] {title_template} for epic '{story.epic}'."
        specifics: dict[str, str] = {
            "setup": (
                f"Initialise repository structure, configure dependencies, "
                f"and prepare CI skeleton for the '{story.epic}' epic."
            ),
            "implementation": (
                f"Implement the core business logic described in: "
                f"\"{story.description}\". "
                f"Ensure all {len(story.acceptance_criteria)} acceptance "
                f"criteria are addressed."
            ),
            "unit_test": (
                f"Write unit tests covering each acceptance criterion "
                f"({len(story.acceptance_criteria)} criteria). "
                f"Target ≥90 % branch coverage."
            ),
            "integration_test": (
                f"Write integration tests that exercise the full request/response "
                f"cycle for story {story.story_id}. "
                f"Include happy-path and error-path scenarios."
            ),
            "review": (
                f"Conduct a peer code review for all implementation and test "
                f"modules related to {story.story_id}. "
                f"Check style, security, and performance."
            ),
            "documentation": (
                f"Add module-level and function-level docstrings, update the "
                f"API reference, and write a usage guide for {story.story_id}."
            ),
        }
        return f"{base} {specifics.get(task_type, '')}"
