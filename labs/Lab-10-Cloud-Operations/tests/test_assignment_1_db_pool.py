"""Unit tests for Assignment 1: Database Connection-Pool Exhaustion."""

import sys
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.cloud_ops_agent import CloudOperationsAgent


class TestAssignment1DatabasePoolExhaustion(unittest.TestCase):
    """Verifies Assignment 1 diagnosis, severity, and governance gating."""

    def setUp(self) -> None:
        self.agent = CloudOperationsAgent()
        self.scenario = self.agent.get_scenario("assignment_1_db_pool_exhaustion")

    def test_db_pool_severity_is_down(self) -> None:
        metrics = self.scenario["metrics"]
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=metrics,
            proposed_action=self.scenario["proposed_action"],
        )
        # 58% error rate exceeds 50% threshold -> DOWN
        self.assertEqual(res["severity"], "down")

    def test_db_pool_incident_start_detection(self) -> None:
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action=self.scenario["proposed_action"],
        )
        self.assertEqual(res["incident_start"], "10:19:05")

    def test_db_pool_diagnosis_distinct_from_payments(self) -> None:
        payments_scenario = self.agent.get_scenario("core_payments_regression")
        res_payments = self.agent.diagnose_and_propose(
            logs=payments_scenario["logs"],
            deploys=payments_scenario["deploy_history"],
            metrics=payments_scenario["metrics"],
            proposed_action="rollback",
        )

        res_db = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action="scale",
        )

        # Severities differ: payments is degraded (3.2x), db is down (580x)
        self.assertEqual(res_payments["severity"], "degraded")
        self.assertEqual(res_db["severity"], "down")

        # Diagnoses and affected paths differ: payments is refund, db is database_pool
        self.assertIn("database_pool", res_db["diagnosis"].lower())
        self.assertIn("refund", res_payments["diagnosis"].lower())

    def test_db_pool_high_risk_scale_action_routes_to_human_approval(self) -> None:
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action="scale",
        )

        self.assertNotIn("action_executed", res)
        self.assertEqual(res["status"], "AWAITING HUMAN APPROVAL -- NOT EXECUTED")
        self.assertEqual(res["proposed_action"], "scale")
        self.assertEqual(res["risk_level"], "high")

    def test_db_pool_does_not_correlate_with_unrelated_data_exporter(self) -> None:
        """Verify data-exporter is NOT blamed for database connection-pool exhaustion."""
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action="scale",
        )

        diagnosis = res.get("diagnosis", "")
        # Must NOT claim that data-exporter caused the issue
        self.assertNotIn("shortly after the 09:30:00 deploy of data-exporter", diagnosis)
        self.assertIn("No relevant deployment correlates", diagnosis)
        self.assertIn("data-exporter", diagnosis)  # Notes that data-exporter does not correlate

    def test_no_rollback_target_fabricated_for_unrelated_service(self) -> None:
        """Verify rollback plan does not target unrelated data-exporter."""
        res = self.agent.diagnose_and_propose(
            logs=self.scenario["logs"],
            deploys=self.scenario["deploy_history"],
            metrics=self.scenario["metrics"],
            proposed_action="scale",
        )

        rollback_plan = res.get("rollback_plan", "")
        self.assertNotIn("Revert to v1.1.9", rollback_plan)
        self.assertIn("N/A: Proposed action 'scale' is not a release rollback", rollback_plan)


if __name__ == "__main__":
    unittest.main()
