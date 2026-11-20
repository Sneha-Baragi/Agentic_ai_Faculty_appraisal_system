"""
Tests for CICDValidator — Lab 11: Agentic SDLC Factory.
Uses only the Python standard library (unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.cicd_validator import CICDValidator
from models.schemas import (
    CodeArtifact,
    QualityGateReport,
    QualityGateStatus,
    TestCase,
    TestStatus,
)


def _make_artifact(
    artifact_id: str = "ART-CI",
    story_id: str = "US-001",
    code_lines: int = 200,
    complexity_score: int = 5,
) -> CodeArtifact:
    return CodeArtifact(
        artifact_id=artifact_id,
        story_id=story_id,
        module_name="auth.ci_test",
        language="Python",
        code_lines=code_lines,
        functions=["login", "logout"],
        test_coverage_pct=90.0,
        complexity_score=complexity_score,
        docstring_coverage_pct=80.0,
    )


def _make_tests(
    story_id: str = "US-001",
    count: int = 4,
    fail_index: int = -1,
) -> list[TestCase]:
    tcs = []
    for i in range(count):
        status = TestStatus.FAIL if i == fail_index else TestStatus.PASS
        tcs.append(
            TestCase(
                test_id=f"TC-{story_id}-{i}",
                story_id=story_id,
                test_name=f"test_case_{i}",
                test_type="unit",
                input_data={"i": i},
                expected_output=True,
                actual_output=status == TestStatus.PASS,
                status=status,
                execution_time_ms=10.0,
            )
        )
    return tcs


def _make_gate(passed: bool = True) -> QualityGateReport:
    status = QualityGateStatus.PASSED if passed else QualityGateStatus.FAILED
    return QualityGateReport(
        story_id="US-001",
        test_pass_rate=1.0 if passed else 0.5,
        code_coverage_pct=90.0,
        review_score=85,
        critical_findings=0,
        complexity_score=5.0,
        status=status,
        gate_checks={
            "test_pass_rate": passed,
            "code_coverage": True,
            "review_score": True,
            "no_critical_findings": True,
            "complexity": True,
        },
    )


class TestCICDBuildSuccess(unittest.TestCase):
    """Verify CI build phase outcomes."""

    def setUp(self) -> None:
        self.validator = CICDValidator()

    def test_valid_artifact_build_succeeds(self) -> None:
        artifact = _make_artifact()
        tcs = _make_tests()
        report = self.validator.validate(artifact, tcs)
        self.assertTrue(report.build_success)

    def test_empty_artifact_build_fails(self) -> None:
        artifact = _make_artifact(code_lines=0)
        tcs = _make_tests()
        report = self.validator.validate(artifact, tcs)
        self.assertFalse(report.build_success)

    def test_high_complexity_build_fails(self) -> None:
        # complexity=8 > default max_complexity=7 → build fail
        artifact = _make_artifact(complexity_score=8)
        tcs = _make_tests()
        report = self.validator.validate(artifact, tcs)
        self.assertFalse(report.build_success)


class TestCICDTestTally(unittest.TestCase):
    """Verify test-tally accuracy."""

    def setUp(self) -> None:
        self.validator = CICDValidator()

    def test_all_pass_tally(self) -> None:
        artifact = _make_artifact()
        tcs = _make_tests(count=5)
        report = self.validator.validate(artifact, tcs)
        self.assertEqual(report.tests_passed, 5)
        self.assertEqual(report.tests_failed, 0)

    def test_one_fail_tally(self) -> None:
        artifact = _make_artifact()
        tcs = _make_tests(count=4, fail_index=0)
        report = self.validator.validate(artifact, tcs)
        self.assertEqual(report.tests_failed, 1)
        self.assertEqual(report.tests_passed, 3)

    def test_build_fail_all_skipped(self) -> None:
        artifact = _make_artifact(code_lines=0)
        tcs = _make_tests(count=4)
        report = self.validator.validate(artifact, tcs)
        self.assertFalse(report.build_success)
        self.assertEqual(report.tests_skipped, 4)
        self.assertEqual(report.tests_passed, 0)


class TestCICDDeployTarget(unittest.TestCase):
    """Verify deployment target selection logic."""

    def setUp(self) -> None:
        self.validator = CICDValidator()

    def test_deploy_to_staging_when_no_gate(self) -> None:
        artifact = _make_artifact()
        tcs = _make_tests()
        report = self.validator.validate(artifact, tcs, quality_gate=None)
        self.assertIn("staging", report.deploy_target)

    def test_deploy_to_prod_when_gate_passed_and_all_tests_pass(self) -> None:
        artifact = _make_artifact()
        tcs = _make_tests()
        gate = _make_gate(passed=True)
        report = self.validator.validate(artifact, tcs, quality_gate=gate)
        self.assertIn("prod", report.deploy_target)

    def test_deploy_fails_when_build_fails(self) -> None:
        artifact = _make_artifact(code_lines=0)
        tcs = _make_tests()
        report = self.validator.validate(artifact, tcs)
        self.assertFalse(report.deploy_success)
        self.assertEqual(report.deploy_target, "none")

    def test_story_id_matches(self) -> None:
        artifact = _make_artifact(story_id="US-999")
        tcs = _make_tests(story_id="US-999")
        report = self.validator.validate(artifact, tcs)
        self.assertEqual(report.story_id, "US-999")


if __name__ == "__main__":
    unittest.main()
