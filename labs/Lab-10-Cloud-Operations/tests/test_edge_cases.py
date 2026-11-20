"""Unit tests for Edge Cases and Safety Guardrails in Lab 10."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.audit import redact_data, redact_sensitive_text
from agent.cloud_ops_agent import CloudOperationsAgent
from agent.diagnostics import classify_severity
from models.schemas import SeverityLevel


class TestEdgeCasesAndSafety(unittest.TestCase):
    """Verifies edge case handling, metric validation, unknown actions, and redaction."""

    def setUp(self) -> None:
        self.agent = CloudOperationsAgent()

    def test_zero_baseline_metric_rejected_without_silent_replacement(self) -> None:
        # Condition 2A: Must not replace 0 with 0.001
        res = classify_severity({"baseline_error_rate": 0.0, "current_error_rate": 1.5})
        self.assertFalse(res.is_valid)
        self.assertEqual(res.severity, SeverityLevel.INVALID_METRICS)
        self.assertIn("strictly positive", res.error_message)

    def test_negative_baseline_metric_rejected(self) -> None:
        res = classify_severity({"baseline_error_rate": -0.5, "current_error_rate": 1.5})
        self.assertFalse(res.is_valid)
        self.assertEqual(res.severity, SeverityLevel.INVALID_METRICS)

    def test_negative_current_rate_rejected(self) -> None:
        res = classify_severity({"baseline_error_rate": 0.5, "current_error_rate": -1.0})
        self.assertFalse(res.is_valid)
        self.assertEqual(res.severity, SeverityLevel.INVALID_METRICS)

    def test_missing_and_none_metrics_rejected(self) -> None:
        res = classify_severity(None)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.severity, SeverityLevel.INVALID_METRICS)

        res2 = classify_severity({"baseline_error_rate": None, "current_error_rate": None})
        self.assertFalse(res2.is_valid)
        self.assertEqual(res2.severity, SeverityLevel.INVALID_METRICS)

    def test_agent_diagnose_rejects_invalid_metrics_safely(self) -> None:
        diag = self.agent.diagnose_and_propose(
            logs=[{"ts": "14:03:40", "level": "ERROR", "msg": "test error"}],
            deploys=[],
            metrics={"baseline_error_rate": 0.0, "current_error_rate": 1.0},
            proposed_action="rollback",
        )
        self.assertEqual(diag["severity"], "invalid_metrics")
        self.assertEqual(diag["status"], "REJECTED_INVALID_METRICS")
        self.assertNotIn("action_executed", diag)

    def test_missing_deployment_history_handled_safely(self) -> None:
        # Condition 2B: Does not crash, notes that rollback target cannot be determined
        diag = self.agent.diagnose_and_propose(
            logs=[{"ts": "11:02:10", "level": "ERROR", "msg": "catalog-service failed"}],
            deploys=[],
            metrics={"baseline_error_rate": 0.5, "current_error_rate": 1.5},
            proposed_action="rollback",
        )
        self.assertEqual(diag["status"], "AWAITING HUMAN APPROVAL -- NOT EXECUTED")
        self.assertIn("CANNOT DETERMINE AUTOMATIC ROLLBACK TARGET", diag["rollback_plan"])
        self.assertIn("cannot be determined", diag["diagnosis"])

    def test_unknown_action_safely_rejected(self) -> None:
        # Condition 2E: Never treated as low-risk
        diag = self.agent.diagnose_and_propose(
            logs=[{"ts": "14:03:40", "level": "ERROR", "msg": "error"}],
            deploys=[],
            metrics={"baseline_error_rate": 0.5, "current_error_rate": 1.5},
            proposed_action="drop_database_table",
        )
        self.assertEqual(diag["risk_level"], "unknown")
        self.assertEqual(diag["execution_outcome"], "BLOCKED_UNKNOWN_ACTION")
        self.assertIn("BLOCKED_UNKNOWN_ACTION", diag["status"])
        self.assertNotIn("action_executed", diag)

    def test_sensitive_data_redaction(self) -> None:
        text_with_secrets = (
            "Connecting with password=SuperSecretPassword123 and token=abc123xyzTokenSecret. "
            "DB URI: postgres://dbuser:super_secret_pw@postgres-db.internal:5432/app"
        )
        redacted = redact_sensitive_text(text_with_secrets)

        self.assertNotIn("SuperSecretPassword123", redacted)
        self.assertNotIn("super_secret_pw", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_redact_dict_removes_sensitive_keys(self) -> None:
        data = {
            "service": "auth-service",
            "db_password": "PlaintextPassword!",
            "api_key": "sk-1234567890abcdef",
            "nested": {
                "token": "bearer-token-val",
                "normal": "normal-value",
            },
        }
        cleaned = redact_data(data)
        self.assertEqual(cleaned["db_password"], "[REDACTED]")
        self.assertEqual(cleaned["api_key"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["token"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["normal"], "normal-value")


if __name__ == "__main__":
    unittest.main()
