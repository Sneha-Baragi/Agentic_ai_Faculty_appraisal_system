"""
Test Runner Tool — Lab 11: Agentic SDLC Factory.

Executes a list of :class:`~models.schemas.TestCase` objects (simulated)
and returns a :class:`~models.schemas.CICDReport` with aggregated tallies.

This tool is a thin wrapper used by the SDLC pipeline to decouple test
execution from the CI/CD validator agent.
"""
from __future__ import annotations

import logging
from typing import Any

from models.schemas import CICDReport, TestCase, TestStatus

logger = logging.getLogger(__name__)


class TestRunner:
    """Tool that tallies test results from a list of TestCase objects.

    The tests are assumed to already have their ``status`` and
    ``actual_output`` fields populated by the TDD Generator agent.
    This tool simply aggregates the counts and assembles a CICDReport.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise the TestRunner.

        Args:
            config: Optional configuration (reserved for future use).
        """
        self.config: dict[str, Any] = config or {}
        logger.debug("TestRunner initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        story_id: str,
        test_cases: list[TestCase],
        build_success: bool = True,
        deploy_target: str = "staging",
        deploy_success: bool = True,
        build_duration_ms: float = 850.0,
        deploy_duration_ms: float = 400.0,
    ) -> CICDReport:
        """Aggregate test results and assemble a CICDReport.

        Args:
            story_id: Identifier of the story being tested.
            test_cases: Pre-executed test cases.
            build_success: Whether the build phase succeeded.
            deploy_target: Deployment target environment name.
            deploy_success: Whether deployment succeeded.
            build_duration_ms: Simulated build duration in milliseconds.
            deploy_duration_ms: Simulated deploy duration in milliseconds.

        Returns:
            A :class:`~models.schemas.CICDReport` with aggregated counts.
        """
        logger.info(
            "TestRunner: tallying %d test cases for story %s (build=%s)",
            len(test_cases),
            story_id,
            "✓" if build_success else "✗",
        )

        if not build_success:
            # All tests are considered skipped when the build fails.
            passed, failed, skipped = 0, 0, len(test_cases)
            logger.warning(
                "Build failed — all %d tests counted as skipped.", len(test_cases)
            )
        else:
            passed = sum(1 for tc in test_cases if tc.status == TestStatus.PASS)
            failed = sum(1 for tc in test_cases if tc.status == TestStatus.FAIL)
            skipped = sum(1 for tc in test_cases if tc.status == TestStatus.SKIPPED)

        logger.info(
            "Test tally for %s: %d passed, %d failed, %d skipped.",
            story_id,
            passed,
            failed,
            skipped,
        )

        return CICDReport(
            story_id=story_id,
            build_success=build_success,
            build_duration_ms=build_duration_ms,
            test_results=test_cases,
            tests_passed=passed,
            tests_failed=failed,
            tests_skipped=skipped,
            deploy_target=deploy_target,
            deploy_success=deploy_success,
            deploy_duration_ms=deploy_duration_ms,
        )
