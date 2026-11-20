"""
Quality Gate Tool — Lab 11: Agentic SDLC Factory.

Evaluates whether a pipeline run meets the minimum quality thresholds
required to advance to production deployment.

Thresholds (configurable via constructor):
* ``test_pass_rate``    ≥ 0.90
* ``code_coverage_pct`` ≥ 80.0
* ``review_score``      ≥ 70
* ``critical_findings`` == 0
* ``complexity_score``  ≤ 7.0
"""
from __future__ import annotations

import logging
from typing import Any

from models.schemas import (
    CICDReport,
    CodeArtifact,
    QualityGateReport,
    QualityGateStatus,
    ReviewResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default thresholds
# ---------------------------------------------------------------------------
_MIN_PASS_RATE = 0.90
_MIN_COVERAGE = 80.0
_MIN_REVIEW_SCORE = 70
_MAX_CRITICAL = 0
_MAX_COMPLEXITY = 7.0


class QualityGate:
    """Tool that evaluates quality thresholds and produces a QualityGateReport.

    All five checks must pass for the gate status to be ``PASSED``.
    If some (but not all) checks pass, the status is ``PARTIAL``.
    If none pass, the status is ``FAILED``.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise the QualityGate.

        Args:
            config: Optional configuration dictionary.  Keys:

                * ``quality_gate_threshold`` (float): Minimum test pass rate.
                * ``min_coverage`` (float): Minimum coverage percentage.
                * ``min_review_score`` (int): Minimum review score.
                * ``max_complexity`` (int|float): Maximum complexity score.
        """
        self.config: dict[str, Any] = config or {}
        self._min_pass_rate: float = float(
            self.config.get("quality_gate_threshold", _MIN_PASS_RATE)
        )
        self._min_coverage: float = float(
            self.config.get("min_coverage", _MIN_COVERAGE)
        )
        self._min_review_score: int = int(
            self.config.get("min_review_score", _MIN_REVIEW_SCORE)
        )
        self._max_complexity: float = float(
            self.config.get("max_complexity", _MAX_COMPLEXITY)
        )
        logger.debug(
            "QualityGate initialised (pass_rate≥%.2f, coverage≥%.1f, "
            "review_score≥%d, complexity≤%.1f)",
            self._min_pass_rate,
            self._min_coverage,
            self._min_review_score,
            self._max_complexity,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        story_id: str,
        cicd_report: CICDReport,
        artifact: CodeArtifact,
        review_result: ReviewResult,
    ) -> QualityGateReport:
        """Evaluate quality thresholds and produce a gate report.

        Args:
            story_id: Identifier of the story being evaluated.
            cicd_report: CI/CD report with test tallies.
            artifact: Code artifact with coverage and complexity metrics.
            review_result: Code review outcome.

        Returns:
            A :class:`~models.schemas.QualityGateReport` with per-check
            verdicts and an overall status.
        """
        total_tests = cicd_report.tests_passed + cicd_report.tests_failed
        pass_rate = (
            cicd_report.tests_passed / total_tests if total_tests > 0 else 0.0
        )
        critical_count = sum(
            1 for f in review_result.findings if f.severity == "critical"
        )

        # --- Individual gate checks --------------------------------------
        checks: dict[str, bool] = {
            "test_pass_rate": pass_rate >= self._min_pass_rate,
            "code_coverage": artifact.test_coverage_pct >= self._min_coverage,
            "review_score": review_result.overall_score >= self._min_review_score,
            "no_critical_findings": critical_count == _MAX_CRITICAL,
            "complexity": artifact.complexity_score <= self._max_complexity,
        }

        passed_count = sum(1 for v in checks.values() if v)
        total_checks = len(checks)

        if passed_count == total_checks:
            status = QualityGateStatus.PASSED
        elif passed_count == 0:
            status = QualityGateStatus.FAILED
        else:
            status = QualityGateStatus.PARTIAL

        logger.info(
            "Quality gate for %s: %d/%d checks passed → %s "
            "(pass_rate=%.2f, coverage=%.1f%%, score=%d, critical=%d, complexity=%.1f)",
            story_id,
            passed_count,
            total_checks,
            status.value,
            pass_rate,
            artifact.test_coverage_pct,
            review_result.overall_score,
            critical_count,
            artifact.complexity_score,
        )

        return QualityGateReport(
            story_id=story_id,
            test_pass_rate=pass_rate,
            code_coverage_pct=artifact.test_coverage_pct,
            review_score=review_result.overall_score,
            critical_findings=critical_count,
            complexity_score=float(artifact.complexity_score),
            status=status,
            gate_checks=checks,
        )
