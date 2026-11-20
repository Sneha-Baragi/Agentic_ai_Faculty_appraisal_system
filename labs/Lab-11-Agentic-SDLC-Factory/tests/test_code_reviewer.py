"""
Tests for CodeReviewer — Lab 11: Agentic SDLC Factory.
Uses only the Python standard library (unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.code_reviewer import CodeReviewer
from models.schemas import CodeArtifact


def _make_artifact(
    artifact_id: str = "ART-TEST",
    story_id: str = "US-001",
    code_lines: int = 150,
    complexity_score: int = 5,
    test_coverage_pct: float = 90.0,
    docstring_coverage_pct: float = 80.0,
    functions: list[str] | None = None,
) -> CodeArtifact:
    # Use `is None` check so callers can explicitly pass an empty list.
    funcs = ["login", "logout", "verify_token"] if functions is None else functions
    return CodeArtifact(
        artifact_id=artifact_id,
        story_id=story_id,
        module_name=f"auth.{story_id.lower()}",
        language="Python",
        code_lines=code_lines,
        functions=funcs,
        test_coverage_pct=test_coverage_pct,
        complexity_score=complexity_score,
        docstring_coverage_pct=docstring_coverage_pct,
    )


class TestCodeReviewerHighComplexity(unittest.TestCase):
    """Verify that high complexity generates appropriate findings."""

    def setUp(self) -> None:
        self.reviewer = CodeReviewer()

    def test_complexity_8_generates_major_finding(self) -> None:
        artifact = _make_artifact(complexity_score=8)
        result = self.reviewer.review(artifact)
        severities = [f.severity for f in result.findings]
        self.assertIn("major", severities)

    def test_complexity_9_generates_critical_finding(self) -> None:
        artifact = _make_artifact(complexity_score=9)
        result = self.reviewer.review(artifact)
        severities = [f.severity for f in result.findings]
        self.assertIn("critical", severities)

    def test_complexity_within_threshold_no_complexity_finding(self) -> None:
        artifact = _make_artifact(complexity_score=5)
        result = self.reviewer.review(artifact)
        complexity_findings = [
            f for f in result.findings if "complexity" in f.description.lower()
        ]
        self.assertEqual(len(complexity_findings), 0)


class TestCodeReviewerLowCoverage(unittest.TestCase):
    """Verify that low coverage generates a finding."""

    def setUp(self) -> None:
        self.reviewer = CodeReviewer()

    def test_coverage_below_80_generates_major_finding(self) -> None:
        artifact = _make_artifact(test_coverage_pct=60.0)
        result = self.reviewer.review(artifact)
        severities = [f.severity for f in result.findings]
        self.assertIn("major", severities)

    def test_coverage_exactly_80_no_coverage_finding(self) -> None:
        artifact = _make_artifact(test_coverage_pct=80.0)
        result = self.reviewer.review(artifact)
        coverage_findings = [
            f for f in result.findings if "coverage" in f.description.lower()
        ]
        self.assertEqual(len(coverage_findings), 0)


class TestCodeReviewerApproval(unittest.TestCase):
    """Verify approval logic."""

    def setUp(self) -> None:
        self.reviewer = CodeReviewer()

    def test_approved_true_when_score_gte_70_no_critical(self) -> None:
        artifact = _make_artifact(
            complexity_score=5, test_coverage_pct=92.0, docstring_coverage_pct=85.0
        )
        result = self.reviewer.review(artifact)
        self.assertTrue(result.approved)
        self.assertGreaterEqual(result.overall_score, 70)

    def test_approved_false_when_critical_finding_present(self) -> None:
        # complexity=10 → critical finding → not approved
        artifact = _make_artifact(complexity_score=10)
        result = self.reviewer.review(artifact)
        self.assertFalse(result.approved)

    def test_approved_false_when_empty_artifact(self) -> None:
        artifact = _make_artifact(code_lines=0)
        result = self.reviewer.review(artifact)
        self.assertFalse(result.approved)

    def test_score_range(self) -> None:
        artifact = _make_artifact()
        result = self.reviewer.review(artifact)
        self.assertGreaterEqual(result.overall_score, 0)
        self.assertLessEqual(result.overall_score, 100)


class TestCodeReviewerFindings(unittest.TestCase):
    """Verify individual finding fields."""

    def setUp(self) -> None:
        self.reviewer = CodeReviewer()

    def test_finding_fields_populated(self) -> None:
        artifact = _make_artifact(complexity_score=9, test_coverage_pct=50.0)
        result = self.reviewer.review(artifact)
        self.assertGreater(len(result.findings), 0)
        for finding in result.findings:
            self.assertTrue(finding.finding_id)
            self.assertIn(finding.severity, ["critical", "major", "minor", "info"])
            self.assertTrue(finding.description)
            self.assertTrue(finding.suggestion)

    def test_reviewer_name_set(self) -> None:
        artifact = _make_artifact()
        result = self.reviewer.review(artifact)
        self.assertEqual(result.reviewer, "CodeReviewerAgent")

    def test_no_functions_generates_finding(self) -> None:
        artifact = _make_artifact(functions=[])
        result = self.reviewer.review(artifact)
        no_fn_findings = [f for f in result.findings if "NOFN" in f.finding_id]
        self.assertGreater(len(no_fn_findings), 0)


if __name__ == "__main__":
    unittest.main()
