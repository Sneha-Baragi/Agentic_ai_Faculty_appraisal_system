"""
Data schemas for Lab 11: Agentic SDLC Factory.

Defines all dataclasses, enums, and typed structures used throughout
the SDLC pipeline simulation.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class StoryStatus(str, Enum):
    """Lifecycle status of a user story or pipeline stage."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(str, Enum):
    """Business priority of a task or user story."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestStatus(str, Enum):
    """Outcome of a single test-case execution."""

    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"


class PipelineStage(str, Enum):
    """Ordered stages of the SDLC pipeline."""

    STORY_DECOMPOSITION = "story_decomposition"
    TDD_GENERATION = "tdd_generation"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    CI_BUILD = "ci_build"
    CD_DEPLOY = "cd_deploy"
    QUALITY_GATE = "quality_gate"


class QualityGateStatus(str, Enum):
    """Overall verdict of the quality gate evaluation."""

    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AcceptanceCriteria:
    """A single acceptance criterion for a user story.

    Attributes:
        criterion_id: Unique identifier (e.g. ``AC-001-1``).
        description: Human-readable criterion text (Given/When/Then).
        met: Whether the criterion was satisfied during the pipeline run.
    """

    criterion_id: str
    description: str
    met: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class UserStory:
    """An agile user story to be processed by the SDLC pipeline.

    Attributes:
        story_id: Unique story identifier (e.g. ``US-001``).
        title: Short title of the story.
        description: Full user story description.
        acceptance_criteria: List of acceptance criteria.
        priority: Business priority level.
        story_points: Relative size estimate.
        epic: Parent epic name.
        status: Current lifecycle status.
    """

    story_id: str
    title: str
    description: str
    acceptance_criteria: list[AcceptanceCriteria]
    priority: TaskPriority
    story_points: int
    epic: str
    status: StoryStatus = StoryStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class Task:
    """A decomposed implementation task derived from a user story.

    Attributes:
        task_id: Unique task identifier.
        story_id: Parent story identifier.
        title: Short task title.
        description: Detailed task description.
        task_type: Category such as ``implementation``, ``test``, ``review``,
            ``deployment``, ``setup``, ``documentation``.
        estimated_hours: Estimated effort in hours.
        dependencies: List of task IDs that must complete first.
        status: Current lifecycle status.
    """

    task_id: str
    story_id: str
    title: str
    description: str
    task_type: str
    estimated_hours: float
    dependencies: list[str]
    status: StoryStatus = StoryStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class TestCase:
    """A generated test case for a user story acceptance criterion.

    Attributes:
        test_id: Unique test identifier.
        story_id: Parent story identifier.
        test_name: Descriptive test function name.
        test_type: ``unit``, ``integration``, or ``e2e``.
        input_data: Mapping of test input parameters.
        expected_output: Expected return value or side-effect.
        actual_output: Actual result after execution (``None`` if not run).
        status: Execution outcome.
        execution_time_ms: Wall-clock execution time in milliseconds.
    """

    test_id: str
    story_id: str
    test_name: str
    test_type: str
    input_data: dict[str, Any]
    expected_output: Any
    actual_output: Any | None = None
    status: TestStatus = TestStatus.SKIPPED
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class CodeArtifact:
    """Metadata describing a generated code module.

    Attributes:
        artifact_id: Unique artifact identifier.
        story_id: Parent story identifier.
        module_name: Python module name (e.g. ``auth.jwt_handler``).
        language: Programming language (default ``Python``).
        code_lines: Total non-blank, non-comment lines of code.
        functions: List of function/method names in the module.
        test_coverage_pct: Percentage of code covered by tests (0-100).
        complexity_score: Cyclomatic complexity score (1-10).
        docstring_coverage_pct: Percentage of callables with docstrings (0-100).
    """

    artifact_id: str
    story_id: str
    module_name: str
    language: str
    code_lines: int
    functions: list[str]
    test_coverage_pct: float
    complexity_score: int
    docstring_coverage_pct: float

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class ReviewFinding:
    """A single finding raised during code review.

    Attributes:
        finding_id: Unique finding identifier.
        severity: ``critical``, ``major``, ``minor``, or ``info``.
        category: ``correctness``, ``style``, ``security``, or ``performance``.
        description: What the reviewer found.
        suggestion: Recommended remediation action.
    """

    finding_id: str
    severity: str
    category: str
    description: str
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class ReviewResult:
    """Aggregated outcome of a code-review pass.

    Attributes:
        artifact_id: The reviewed artifact identifier.
        reviewer: Name of the reviewer agent.
        findings: List of individual review findings.
        approved: Whether the artifact was approved for merge.
        overall_score: Composite quality score (0-100).
    """

    artifact_id: str
    reviewer: str
    findings: list[ReviewFinding]
    approved: bool
    overall_score: int

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class PipelineStageResult:
    """Outcome of a single pipeline stage execution.

    Attributes:
        stage: Which pipeline stage this result belongs to.
        status: Pass/fail status of the stage.
        duration_ms: Wall-clock time taken in milliseconds.
        artifacts: List of artifact IDs produced.
        logs: Ordered list of log messages emitted.
        metrics: Arbitrary key-value metrics for observability.
    """

    stage: PipelineStage
    status: StoryStatus
    duration_ms: float
    artifacts: list[str]
    logs: list[str]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class QualityGateReport:
    """Quality-gate evaluation report for a story's pipeline run.

    Attributes:
        story_id: The story that was evaluated.
        test_pass_rate: Fraction of tests that passed (0.0–1.0).
        code_coverage_pct: Code coverage percentage (0–100).
        review_score: Overall review score (0–100).
        critical_findings: Count of critical review findings.
        complexity_score: Average complexity score (1–10).
        status: Overall gate verdict.
        gate_checks: Individual boolean checks with descriptive keys.
    """

    story_id: str
    test_pass_rate: float
    code_coverage_pct: float
    review_score: int
    critical_findings: int
    complexity_score: float
    status: QualityGateStatus
    gate_checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class CICDReport:
    """Report from the CI/CD validation stage.

    Attributes:
        story_id: The story processed.
        build_success: Whether the build phase succeeded.
        build_duration_ms: Time spent in the build phase.
        test_results: Individual test-case results.
        tests_passed: Count of passing tests.
        tests_failed: Count of failing tests.
        tests_skipped: Count of skipped tests.
        deploy_target: Hostname/environment targeted for deployment.
        deploy_success: Whether the deployment succeeded.
        deploy_duration_ms: Time spent in the deploy phase.
    """

    story_id: str
    build_success: bool
    build_duration_ms: float
    test_results: list[TestCase]
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    deploy_target: str
    deploy_success: bool
    deploy_duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


@dataclass
class SDLCFactoryReport:
    """Top-level report produced by a full SDLC pipeline run.

    Attributes:
        run_id: Unique run identifier (UUID-like string).
        story_id: Story that was processed.
        story_title: Human-readable story title.
        pipeline_start: ISO-8601 timestamp of pipeline start.
        pipeline_end: ISO-8601 timestamp of pipeline end.
        total_duration_ms: Total wall-clock pipeline time in milliseconds.
        stage_results: Ordered list of per-stage outcomes.
        tasks_generated: Number of tasks produced in decomposition.
        test_cases_generated: Number of test cases generated.
        code_artifact: Generated code artifact metadata (or ``None``).
        review_result: Code review outcome (or ``None``).
        cicd_report: CI/CD validation report (or ``None``).
        quality_gate: Quality gate evaluation report (or ``None``).
        final_status: Overall story pipeline status.
        simulation_disclaimer: Fixed disclaimer string.
    """

    run_id: str
    story_id: str
    story_title: str
    pipeline_start: str
    pipeline_end: str
    total_duration_ms: float
    stage_results: list[PipelineStageResult]
    tasks_generated: int
    test_cases_generated: int
    code_artifact: CodeArtifact | None
    review_result: ReviewResult | None
    cicd_report: CICDReport | None
    quality_gate: QualityGateReport | None
    final_status: StoryStatus
    simulation_disclaimer: str = (
        "Simulation: No real code is compiled/executed/deployed."
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)
