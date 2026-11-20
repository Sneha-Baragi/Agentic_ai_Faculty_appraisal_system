"""Unit tests for Assignment 2: Warning-Level Safe Auto-Remediation."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.cloud_ops_agent import CloudOperationsAgent


class TestAssignment2SafeAutoRemediation(unittest.TestCase):
    """Verifies Assignment 2 safe auto-remediation and strict rollback protection."""

    def setUp(self) -> None:
        self.agent = CloudOperationsAgent()
        self.scenario = self.agent.get_scenario("assignment_2_safe_pod_restart")

    def test_warning_level_severity_classification(self) -> None:
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action="restart_single_pod",
        )
        self.assertEqual(res["severity"], "early_warning")
        self.assertIsNone(res["incident_start"])

    def test_restart_single_pod_auto_executes_in_simulation(self) -> None:
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action="restart_single_pod",
        )

        self.assertIn("action_executed", res)
        self.assertEqual(res["action_executed"], "restart_single_pod")
        self.assertEqual(res["status"], "AUTOMATICALLY_EXECUTED")
        self.assertEqual(res["risk_level"], "low")

    def test_open_ticket_low_risk_action_auto_executes(self) -> None:
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action="open_ticket",
        )
        self.assertIn("action_executed", res)
        self.assertEqual(res["action_executed"], "open_ticket")

    def test_rollback_on_warning_scenario_still_requires_approval(self) -> None:
        # Crucial invariant: Proposing rollback even on a warning scenario must NOT auto-execute
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action="rollback",
            urgency_prompt=False,
        )

        self.assertNotIn(
            "action_executed",
            res,
            "SAFETY VIOLATION: Rollback action must never auto-execute even at warning level!",
        )
        self.assertEqual(res["status"], "AWAITING HUMAN APPROVAL -- NOT EXECUTED")
        self.assertEqual(res["risk_level"], "high")


if __name__ == "__main__":
    unittest.main()
