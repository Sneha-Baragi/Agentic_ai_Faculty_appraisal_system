"""
TDD Generator Agent — Lab 11: Agentic SDLC Factory.

Generates :class:`~models.schemas.TestCase` objects from a UserStory's
acceptance criteria following Test-Driven Development principles.
Tests are generated *before* the code artifact, as TDD demands.

All execution simulation is deterministic and seeded on the story_id hash.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from models.schemas import (
    AcceptanceCriteria,
    Task,
    TestCase,
    TestStatus,
    UserStory,
)

logger = logging.getLogger(__name__)

# Fraction of stories (by hash) that are allowed to have some failing tests.
# A story whose numeric hash mod 100 == 7 will have ~1 failing test (1% of stories).
# Using mod 100 so realistic fixture stories all pass by default.
_FAIL_HASH_MODULO = 100
_FAIL_HASH_VALUE = 7


class TDDGenerator:
    """Agent that generates test cases from a UserStory using TDD principles.

    For each acceptance criterion, one **unit test** is produced.
    Additionally, at least one **integration test** is generated per story,
    and one **e2e test** is generated for stories with ≥4 acceptance criteria.

    Test-execution simulation is deterministic: the story_id is hashed to
    decide which (if any) tests fail, ensuring reproducible pipeline runs.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise the TDDGenerator.

        Args:
            config: Optional configuration dictionary.  Keys supported:

                * ``force_pass`` (bool): Force all tests to pass regardless of
                  story hash.  Defaults to ``False``.
        """
        self.config: dict[str, Any] = config or {}
        self._force_pass: bool = bool(self.config.get("force_pass", False))
        logger.debug(
            "TDDGenerator initialised (force_pass=%s)", self._force_pass
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, story: UserStory, tasks: list[Task]) -> list[TestCase]:
        """Generate test cases for *story*.

        Args:
            story: The user story whose acceptance criteria drive test generation.
            tasks: Decomposed tasks (used to tag test IDs with their source task).

        Returns:
            An ordered list of :class:`~models.schemas.TestCase` objects with
            simulated execution results.
        """
        logger.info(
            "Generating tests for story %s (%d ACs)",
            story.story_id,
            len(story.acceptance_criteria),
        )

        story_hash = self._story_hash(story.story_id)
        should_fail_one = (
            not self._force_pass and story_hash % _FAIL_HASH_MODULO == _FAIL_HASH_VALUE
        )

        test_cases: list[TestCase] = []

        # -- Unit tests: one per acceptance criterion -----------------------
        for ac_idx, ac in enumerate(story.acceptance_criteria, start=1):
            tc = self._build_unit_test(story, ac, ac_idx)
            test_cases.append(tc)

        # -- Integration test: always at least one -------------------------
        int_tc = self._build_integration_test(story, len(test_cases) + 1)
        test_cases.append(int_tc)

        # -- E2E test: for larger stories (≥4 ACs) -------------------------
        if len(story.acceptance_criteria) >= 4:
            e2e_tc = self._build_e2e_test(story, len(test_cases) + 1)
            test_cases.append(e2e_tc)

        # -- Simulate execution --------------------------------------------
        self._simulate_execution(test_cases, should_fail_one)

        logger.info(
            "Story %s: generated %d tests (%d unit, 1 integration%s)",
            story.story_id,
            len(test_cases),
            len(story.acceptance_criteria),
            ", 1 e2e" if len(story.acceptance_criteria) >= 4 else "",
        )
        return test_cases

    # ------------------------------------------------------------------
    # Private builders
    # ------------------------------------------------------------------

    @staticmethod
    def _verb_noun_from_ac(ac: AcceptanceCriteria) -> tuple[str, str]:
        """Extract a verb and noun pair from an acceptance criterion description.

        Args:
            ac: The acceptance criterion to parse.

        Returns:
            A ``(verb, noun)`` tuple suitable for embedding in a test name.
        """
        # Simple keyword extraction — no NLP needed.
        desc = ac.description.lower()
        verb = "verify"
        noun = "behaviour"
        # Look for 'then I <verb> …'
        if "then i " in desc:
            fragment = desc.split("then i ", 1)[1]
            words = fragment.split()
            if words:
                verb = words[0].strip(".,;")
            if len(words) > 1:
                noun = words[1].strip(".,;")
        elif "when i " in desc:
            fragment = desc.split("when i ", 1)[1]
            words = fragment.split()
            if words:
                verb = words[0].strip(".,;")
        return verb, noun

    def _build_unit_test(
        self,
        story: UserStory,
        ac: AcceptanceCriteria,
        ac_idx: int,
    ) -> TestCase:
        """Build a unit test for a single acceptance criterion.

        Args:
            story: Parent story.
            ac: Acceptance criterion driving this test.
            ac_idx: 1-based index of the criterion within the story.

        Returns:
            A :class:`~models.schemas.TestCase` instance.
        """
        verb, noun = self._verb_noun_from_ac(ac)
        condition = f"ac{ac_idx}"
        test_name = f"test_{verb}_{noun}_{condition}"

        # Derive realistic input / expected output from the criterion text.
        input_data: dict[str, Any] = {
            "story_id": story.story_id,
            "criterion_id": ac.criterion_id,
            "scenario": ac.description[:60],
        }
        expected_output: Any = True  # criterion is met

        return TestCase(
            test_id=f"{ac.criterion_id}-UT",
            story_id=story.story_id,
            test_name=test_name,
            test_type="unit",
            input_data=input_data,
            expected_output=expected_output,
        )

    @staticmethod
    def _build_integration_test(story: UserStory, seq: int) -> TestCase:
        """Build an integration test for the story as a whole.

        Args:
            story: Parent story.
            seq: Sequential test number for ID generation.

        Returns:
            A :class:`~models.schemas.TestCase` instance.
        """
        module_slug = story.epic.lower().replace(" ", "_")
        test_name = f"test_integration_{module_slug}_{story.story_id.lower()}"
        return TestCase(
            test_id=f"{story.story_id}-IT-{seq:02d}",
            story_id=story.story_id,
            test_name=test_name,
            test_type="integration",
            input_data={
                "story_id": story.story_id,
                "epic": story.epic,
                "all_criteria": [
                    ac.criterion_id for ac in story.acceptance_criteria
                ],
            },
            expected_output={"all_criteria_met": True},
        )

    @staticmethod
    def _build_e2e_test(story: UserStory, seq: int) -> TestCase:
        """Build an end-to-end test for a large story.

        Args:
            story: Parent story.
            seq: Sequential test number for ID generation.

        Returns:
            A :class:`~models.schemas.TestCase` instance.
        """
        module_slug = story.epic.lower().replace(" ", "_")
        test_name = (
            f"test_e2e_{module_slug}_{story.story_id.lower()}_full_flow"
        )
        return TestCase(
            test_id=f"{story.story_id}-E2E-{seq:02d}",
            story_id=story.story_id,
            test_name=test_name,
            test_type="e2e",
            input_data={
                "story_id": story.story_id,
                "simulate_user": "faculty_member",
                "flow": "complete",
            },
            expected_output={"flow_completed": True, "errors": []},
        )

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    def _simulate_execution(
        self, test_cases: list[TestCase], fail_one: bool
    ) -> None:
        """Simulate test execution by setting status and timing on each case.

        Args:
            test_cases: Mutable list of test cases to update in-place.
            fail_one: If ``True``, the second test (index 1) will be marked as
                FAIL to exercise the failure-handling path.
        """
        base_time_ms = 12.5
        for idx, tc in enumerate(test_cases):
            if fail_one and idx == 1:
                tc.status = TestStatus.FAIL
                tc.actual_output = False
                tc.execution_time_ms = base_time_ms * (idx + 1)
                logger.debug(
                    "  Test %s (%s) → FAIL (deterministic)", tc.test_id, tc.test_name
                )
            else:
                tc.status = TestStatus.PASS
                tc.actual_output = tc.expected_output
                tc.execution_time_ms = base_time_ms * (idx + 1)
                logger.debug(
                    "  Test %s (%s) → PASS", tc.test_id, tc.test_name
                )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _story_hash(story_id: str) -> int:
        """Return a stable integer hash of a story ID.

        Args:
            story_id: The story identifier string.

        Returns:
            An unsigned integer derived from the MD5 of ``story_id``.
        """
        return int(hashlib.md5(story_id.encode()).hexdigest(), 16)
