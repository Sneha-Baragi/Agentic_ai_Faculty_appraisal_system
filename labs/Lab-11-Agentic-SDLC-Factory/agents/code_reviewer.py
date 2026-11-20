"""
Code Reviewer Agent — Lab 11: Agentic SDLC Factory.

Deterministically reviews a :class:`~models.schemas.CodeArtifact` and
produces a :class:`~models.schemas.ReviewResult` with individual
:class:`~models.schemas.ReviewFinding` objects.

No LLM or external API calls are made; all checks are rule-based.
"""
from __future__ import annotations

import logging
from typing import Any

from models.schemas import CodeArtifact, ReviewFinding, ReviewResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Penalty / threshold constants
# ---------------------------------------------------------------------------
_MAX_COMPLEXITY = 7       # complexity > this triggers a major/critical finding
_MIN_COVERAGE = 80.0      # coverage < this triggers a major finding
_MIN_DOCSTRING = 70.0     # docstring coverage < this triggers a minor finding
_APPROVAL_THRESHOLD = 70  # overall_score must be >= this to approve

_COMPLEXITY_CRITICAL_THRESHOLD = 9  # complexity >= this → critical (not just major)


class CodeReviewer:
    """Agent that reviews a CodeArtifact and produces a ReviewResult.

    Checks performed
    ----------------
    1. **Complexity check** — flag artifacts with ``complexity_score > 7``.
       Scores ≥ 9 produce a *critical* finding; scores 8–8 produce *major*.
    2. **Coverage check** — flag artifacts with ``test_coverage_pct < 80``.
    3. **Docstring check** — flag artifacts with ``docstring_coverage_pct < 70``.
    4. **Code-lines check** — flag empty artifacts (``code_lines == 0``).

    Score computation
    -----------------
    ``overall_score = 100 - Σ penalties``

    Penalties:
    * critical finding : −25 pts each
    * major finding    : −15 pts each
    * minor finding    : −5 pts each
    * info finding     : −1 pt each

    Approval requires ``overall_score >= 70`` **and** zero critical findings.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise the CodeReviewer.

        Args:
            config: Optional configuration overrides.  Keys:

                * ``max_complexity`` (int): Maximum allowed complexity.
                * ``min_coverage`` (float): Minimum test-coverage percentage.
                * ``min_docstring`` (float): Minimum docstring-coverage percentage.
        """
        self.config: dict[str, Any] = config or {}
        self._max_complexity: int = int(
            self.config.get("max_complexity", _MAX_COMPLEXITY)
        )
        self._min_coverage: float = float(
            self.config.get("min_coverage", _MIN_COVERAGE)
        )
        self._min_docstring: float = float(
            self.config.get("min_docstring", _MIN_DOCSTRING)
        )
        logger.debug(
            "CodeReviewer initialised (max_complexity=%d, min_coverage=%.1f, "
            "min_docstring=%.1f)",
            self._max_complexity,
            self._min_coverage,
            self._min_docstring,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review(self, artifact: CodeArtifact) -> ReviewResult:
        """Review *artifact* and return a :class:`~models.schemas.ReviewResult`.

        Args:
            artifact: The code artifact to evaluate.

        Returns:
            A :class:`~models.schemas.ReviewResult` with findings, score, and
            approval verdict.
        """
        logger.info(
            "Reviewing artifact %s (module=%s, complexity=%d, coverage=%.1f%%)",
            artifact.artifact_id,
            artifact.module_name,
            artifact.complexity_score,
            artifact.test_coverage_pct,
        )

        findings: list[ReviewFinding] = []

        # --- Individual checks -------------------------------------------
        self._check_empty_artifact(artifact, findings)
        self._check_complexity(artifact, findings)
        self._check_coverage(artifact, findings)
        self._check_docstrings(artifact, findings)
        self._check_functions(artifact, findings)

        # --- Score computation -------------------------------------------
        overall_score = self._compute_score(findings)
        has_critical = any(f.severity == "critical" for f in findings)
        approved = overall_score >= _APPROVAL_THRESHOLD and not has_critical

        logger.info(
            "Review of %s: score=%d, findings=%d (critical=%d), approved=%s",
            artifact.artifact_id,
            overall_score,
            len(findings),
            sum(1 for f in findings if f.severity == "critical"),
            approved,
        )

        return ReviewResult(
            artifact_id=artifact.artifact_id,
            reviewer="CodeReviewerAgent",
            findings=findings,
            approved=approved,
            overall_score=overall_score,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_empty_artifact(
        artifact: CodeArtifact, findings: list[ReviewFinding]
    ) -> None:
        """Flag artifacts with zero lines of code as critical."""
        if artifact.code_lines == 0:
            findings.append(
                ReviewFinding(
                    finding_id=f"{artifact.artifact_id}-F-EMPTY",
                    severity="critical",
                    category="correctness",
                    description="Artifact contains zero lines of code.",
                    suggestion=(
                        "Implement the required functionality before submitting "
                        "for review."
                    ),
                )
            )
            logger.warning("Artifact %s is empty.", artifact.artifact_id)

    def _check_complexity(
        self, artifact: CodeArtifact, findings: list[ReviewFinding]
    ) -> None:
        """Flag high cyclomatic complexity."""
        if artifact.complexity_score > self._max_complexity:
            severity = (
                "critical"
                if artifact.complexity_score >= _COMPLEXITY_CRITICAL_THRESHOLD
                else "major"
            )
            findings.append(
                ReviewFinding(
                    finding_id=f"{artifact.artifact_id}-F-COMPLEX",
                    severity=severity,
                    category="performance",
                    description=(
                        f"Cyclomatic complexity score is {artifact.complexity_score} "
                        f"(threshold: {self._max_complexity})."
                    ),
                    suggestion=(
                        "Refactor complex methods by extracting helper functions "
                        "or applying the Strategy pattern."
                    ),
                )
            )
            logger.warning(
                "Artifact %s complexity=%d exceeds threshold=%d (severity=%s).",
                artifact.artifact_id,
                artifact.complexity_score,
                self._max_complexity,
                severity,
            )

    def _check_coverage(
        self, artifact: CodeArtifact, findings: list[ReviewFinding]
    ) -> None:
        """Flag insufficient test coverage."""
        if artifact.test_coverage_pct < self._min_coverage:
            findings.append(
                ReviewFinding(
                    finding_id=f"{artifact.artifact_id}-F-COV",
                    severity="major",
                    category="correctness",
                    description=(
                        f"Test coverage is {artifact.test_coverage_pct:.1f}% "
                        f"(minimum: {self._min_coverage:.1f}%)."
                    ),
                    suggestion=(
                        "Add unit tests for uncovered branches and edge cases "
                        "to reach the coverage threshold."
                    ),
                )
            )
            logger.warning(
                "Artifact %s coverage=%.1f%% < threshold=%.1f%%.",
                artifact.artifact_id,
                artifact.test_coverage_pct,
                self._min_coverage,
            )

    def _check_docstrings(
        self, artifact: CodeArtifact, findings: list[ReviewFinding]
    ) -> None:
        """Flag insufficient docstring coverage."""
        if artifact.docstring_coverage_pct < self._min_docstring:
            findings.append(
                ReviewFinding(
                    finding_id=f"{artifact.artifact_id}-F-DOC",
                    severity="minor",
                    category="style",
                    description=(
                        f"Docstring coverage is {artifact.docstring_coverage_pct:.1f}% "
                        f"(minimum: {self._min_docstring:.1f}%)."
                    ),
                    suggestion=(
                        "Add Google-style docstrings to all public functions "
                        "and classes."
                    ),
                )
            )

    @staticmethod
    def _check_functions(
        artifact: CodeArtifact, findings: list[ReviewFinding]
    ) -> None:
        """Flag artifacts with no exported functions."""
        if not artifact.functions:
            findings.append(
                ReviewFinding(
                    finding_id=f"{artifact.artifact_id}-F-NOFN",
                    severity="minor",
                    category="correctness",
                    description="No public functions or methods found in artifact.",
                    suggestion=(
                        "Ensure the module exposes at least one public callable."
                    ),
                )
            )

    # ------------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_score(findings: list[ReviewFinding]) -> int:
        """Compute the overall review score from accumulated findings.

        Args:
            findings: List of review findings.

        Returns:
            Integer score in the range [0, 100].
        """
        penalties: dict[str, int] = {
            "critical": 25,
            "major": 15,
            "minor": 5,
            "info": 1,
        }
        total_penalty = sum(penalties.get(f.severity, 0) for f in findings)
        return max(0, 100 - total_penalty)
