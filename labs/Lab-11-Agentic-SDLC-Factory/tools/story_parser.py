"""
Story Parser Tool — Lab 11: Agentic SDLC Factory.

Converts raw JSON dictionaries (loaded from fixture files) into typed
:class:`~models.schemas.UserStory` objects.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from models.schemas import AcceptanceCriteria, TaskPriority, UserStory

logger = logging.getLogger(__name__)


class StoryParser:
    """Tool that parses user story dicts into :class:`~models.schemas.UserStory` objects.

    Accepts either raw dicts or the path to a JSON fixture file.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: Path) -> list[UserStory]:
        """Load user stories from a JSON file.

        Args:
            path: Path to a JSON file containing a list of story dicts.

        Returns:
            A list of :class:`~models.schemas.UserStory` objects.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the file is not valid JSON or the top-level value
                is not a list.
        """
        logger.info("Loading stories from %s", path)
        raw = path.read_text(encoding="utf-8")
        data: Any = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON list in {path}, got {type(data).__name__}")
        stories = [self.parse_dict(d) for d in data]
        logger.info("Loaded %d user stories from %s", len(stories), path)
        return stories

    def parse_dict(self, data: dict[str, Any]) -> UserStory:
        """Parse a single user story dictionary.

        Args:
            data: Raw story dictionary with keys matching the
                :class:`~models.schemas.UserStory` field names.

        Returns:
            A fully constructed :class:`~models.schemas.UserStory`.

        Raises:
            KeyError: If a required field is missing from *data*.
            ValueError: If the ``priority`` value is not a valid
                :class:`~models.schemas.TaskPriority` member.
        """
        story_id: str = data["story_id"]
        logger.debug("Parsing story %s", story_id)

        raw_criteria: list[dict[str, Any]] = data.get("acceptance_criteria", [])
        criteria: list[AcceptanceCriteria] = [
            AcceptanceCriteria(
                criterion_id=ac["criterion_id"],
                description=ac["description"],
                met=bool(ac.get("met", False)),
            )
            for ac in raw_criteria
        ]

        priority_str: str = str(data.get("priority", "medium")).lower()
        try:
            priority = TaskPriority(priority_str)
        except ValueError:
            logger.warning(
                "Unknown priority '%s' for story %s; defaulting to MEDIUM.",
                priority_str,
                story_id,
            )
            priority = TaskPriority.MEDIUM

        story = UserStory(
            story_id=story_id,
            title=data["title"],
            description=data["description"],
            acceptance_criteria=criteria,
            priority=priority,
            story_points=int(data.get("story_points", 1)),
            epic=str(data.get("epic", "General")),
        )
        logger.debug("Parsed story %s: '%s'", story_id, story.title)
        return story
