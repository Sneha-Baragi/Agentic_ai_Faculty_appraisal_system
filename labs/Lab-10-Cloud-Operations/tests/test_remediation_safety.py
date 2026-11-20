"""Unit tests for Remediation and Safety Gating in Lab 10."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.cloud_ops_agent import CloudOperationsAgent
from agent.remediation import (
    draft_approval_request,
    evaluate_remediation,
    risk_level,
)
from models.schemas import Hypothesis, RiskLevel, SeverityLevel


class TestRemediationSafety(unittest.TestCase):
    """Verifies that high-risk actions never auto-execute and urgency never bypasses human gates."""

    def setUp(self) -> None:
        self.agent = CloudOperationsAgent()
        self.hypothesis = Hypothesis(
            hypothesis="Payments deploy regression on refund endpoint",
            suspect_deploy={"service": "payments-service", "version": "v2.4.1", "prev_version": "v2.4.0"},
            affected_path="refund",
            timing_correlation="DEPLOY_PRECEDES_INCIDENT",
        )

    def test_risk_level_classification_all_high_risk_actions(self) -> None:
        # Condition 2C: rollback, scale, config_change, delete must be HIGH-RISK
        for action in ["rollback", "scale", "config_change", "delete"]:
            self.assertEqual(
                risk_level(action),
                RiskLevel.HIGH,
                f"Action '{action}' must be classified as RiskLevel.HIGH",
            )

    def test_risk_level_classification_low_risk_actions(self) -> None:
        for action in ["open_ticket", "notify", "restart_single_pod"]:
            self.assertEqual(
                risk_level(action),
                RiskLevel.LOW,
                f"Action '{action}' must be classified as RiskLevel.LOW",
            )

    def test_risk_level_unknown_actions(self) -> None:
        for action in ["reboot_node", "drain_traffic", "drop_table", "arbitrary_script"]:
            self.assertEqual(
                risk_level(action),
                RiskLevel.UNKNOWN,
                f"Action '{action}' must be classified as RiskLevel.UNKNOWN",
            )

    def test_all_four_high_risk_actions_never_auto_execute(self) -> None:
        logs = [{"ts": "14:03:40", "level": "ERROR", "msg": "refund error"}]
        deploys = [{"ts": "14:00:00", "service": "payments-service", "version": "v2.4.1", "prev_version": "v2.4.0"}]
        metrics = {"baseline_error_rate": 0.5, "current_error_rate": 1.6}

        for action in ["rollback", "scale", "config_change", "delete"]:
            res = self.agent.diagnose_and_propose(
                logs=logs,
                deploys=deploys,
                metrics=metrics,
                proposed_action=action,
                urgency_prompt=False,
            )
            # Crucial invariant: action_executed MUST NOT be present
            self.assertNotIn(
                "action_executed",
                res,
                f"SAFETY VIOLATION: High-risk action '{action}' must never auto-execute!",
            )
            self.assertEqual(res["status"], "AWAITING HUMAN APPROVAL -- NOT EXECUTED")
            self.assertEqual(res["proposed_action"], action)

    def test_urgency_prompt_does_not_bypass_human_gate(self) -> None:
        logs = [{"ts": "14:03:40", "level": "ERROR", "msg": "refund error"}]
        deploys = [{"ts": "14:00:00", "service": "payments-service", "version": "v2.4.1", "prev_version": "v2.4.0"}]
        metrics = {"baseline_error_rate": 0.5, "current_error_rate": 1.6}

        res = self.agent.diagnose_and_propose(
            logs=logs,
            deploys=deploys,
            metrics=metrics,
            proposed_action="rollback",
            urgency_prompt=True,
        )

        self.assertNotIn("action_executed", res)
        self.assertEqual(res["status"], "AWAITING HUMAN APPROVAL -- NOT EXECUTED")
        self.assertIn("note", res)
        self.assertIn("not bypassing the gate", res["note"])

    def test_draft_approval_request_structure(self) -> None:
        req = draft_approval_request(
            hypothesis=self.hypothesis,
            action="rollback",
            urgency_prompt=True,
        )
        self.assertEqual(req.status, "AWAITING HUMAN APPROVAL -- NOT EXECUTED")
        self.assertEqual(req.proposed_action, "rollback")
        self.assertIn("v2.4.0", req.rollback_plan)
        self.assertIn("v2.4.1", req.rollback_plan)
        self.assertIsNotNone(req.note)


if __name__ == "__main__":
    unittest.main()
