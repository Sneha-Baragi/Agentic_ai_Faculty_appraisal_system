"""Unit tests for Diagnostics module in Lab 10."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.diagnostics import (
    classify_severity,
    correlate_with_recent_changes,
    find_incident_start,
)
from models.schemas import LogEntry, MetricsPayload, SeverityLevel


class TestDiagnostics(unittest.TestCase):
    """Verifies severity classification, timing detection, and deploy correlation."""

    def test_classify_severity_down_when_current_exceeds_fifty_percent(self) -> None:
        metrics = {"baseline_error_rate": 0.5, "current_error_rate": 55.0}
        res = classify_severity(metrics)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.severity, SeverityLevel.DOWN)
        self.assertEqual(res.ratio, 110.0)

    def test_classify_severity_degraded_when_ratio_exceeds_two(self) -> None:
        metrics = {"baseline_error_rate": 0.5, "current_error_rate": 1.6}
        res = classify_severity(metrics)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.severity, SeverityLevel.DEGRADED)
        self.assertEqual(res.ratio, 3.2)

    def test_classify_severity_early_warning_when_ratio_under_two(self) -> None:
        metrics = {"baseline_error_rate": 0.5, "current_error_rate": 0.8}
        res = classify_severity(metrics)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.severity, SeverityLevel.EARLY_WARNING)
        self.assertEqual(res.ratio, 1.6)

    def test_find_incident_start_earliest_error(self) -> None:
        logs = [
            {"ts": "14:00:00", "level": "INFO", "msg": "deploy started"},
            {"ts": "14:03:10", "level": "WARN", "msg": "latency elevated"},
            {"ts": "14:03:40", "level": "ERROR", "msg": "NullPointerException in RefundHandler"},
            {"ts": "14:04:05", "level": "ERROR", "msg": "NullPointerException in RefundHandler"},
        ]
        start = find_incident_start(logs)
        self.assertEqual(start, "14:03:40")

    def test_find_incident_start_no_errors_returns_none(self) -> None:
        logs = [
            {"ts": "08:00:10", "level": "INFO", "msg": "telemetry active"},
            {"ts": "08:05:20", "level": "WARN", "msg": "memory usage at 88%"},
        ]
        start = find_incident_start(logs)
        self.assertIsNone(start)

    def test_correlate_with_recent_changes_matching_deploy(self) -> None:
        logs = [
            {"ts": "14:03:40", "level": "ERROR", "msg": "refund endpoint: NullPointerException in RefundHandler"}
        ]
        deploys = [
            {"ts": "14:00:00", "service": "payments-service", "version": "v2.4.1", "prev_version": "v2.4.0"}
        ]
        hyp = correlate_with_recent_changes(logs, deploys, "14:03:40")

        self.assertIsNotNone(hyp.suspect_deploy)
        self.assertEqual(hyp.affected_path, "refund")
        self.assertIn("payments-service v2.4.1", hyp.hypothesis)
        self.assertIn("14:03:40", hyp.hypothesis)
        self.assertIn("refund code path", hyp.hypothesis)

    def test_correlate_with_missing_deploys(self) -> None:
        logs = [
            {"ts": "11:02:10", "level": "ERROR", "msg": "failed to connect to database pool"}
        ]
        hyp = correlate_with_recent_changes(logs, [], "11:02:10")

        self.assertIsNone(hyp.suspect_deploy)
        self.assertEqual(hyp.affected_path, "database_pool")
        self.assertIn("cannot be determined", hyp.hypothesis)

    def test_unrelated_deploy_with_earlier_timestamp_not_selected(self) -> None:
        """Verify an unrelated service deploy before the incident is NOT blamed."""
        logs = [
            {"ts": "10:19:05", "level": "ERROR", "msg": "database pool exhausted: ConnectionPoolTimeoutException in AuthHandler"}
        ]
        deploys = [
            {"ts": "09:30:00", "service": "data-exporter", "version": "v1.2.0", "prev_version": "v1.1.9"}
        ]
        hyp = correlate_with_recent_changes(logs, deploys, "10:19:05")

        self.assertIsNone(hyp.suspect_deploy)
        self.assertEqual(hyp.affected_path, "database_pool")
        self.assertIn("No relevant deployment correlates", hyp.hypothesis)
        self.assertIn("data-exporter", hyp.hypothesis)

    def test_genuinely_relevant_deploy_is_correlated(self) -> None:
        """Verify a genuinely relevant service deploy is correctly correlated."""
        logs = [
            {"ts": "15:10:00", "level": "ERROR", "msg": "catalog-service: database query failed"}
        ]
        deploys = [
            {"ts": "15:00:00", "service": "catalog-service", "version": "v3.0.1", "prev_version": "v3.0.0"}
        ]
        hyp = correlate_with_recent_changes(logs, deploys, "15:10:00")

        self.assertIsNotNone(hyp.suspect_deploy)
        self.assertEqual(hyp.suspect_deploy["service"], "catalog-service")
        self.assertIn("catalog-service v3.0.1", hyp.hypothesis)


if __name__ == "__main__":
    unittest.main()
