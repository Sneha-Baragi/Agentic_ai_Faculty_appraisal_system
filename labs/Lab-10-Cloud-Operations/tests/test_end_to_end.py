"""End-to-End Integration tests for Lab 10: Cloud Operations Agent."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.cloud_ops_agent import CloudOperationsAgent


class TestCloudOperationsEndToEnd(unittest.TestCase):
    """Verifies end-to-end incident workflows and report artifact generation."""

    def setUp(self) -> None:
        self.agent = CloudOperationsAgent()

    def test_e2e_core_payments_regression_workflow(self) -> None:
        report = self.agent.run_incident(
            scenario_id="core_payments_regression",
            urgency_prompt=True,
        )

        self.assertEqual(report.scenario_id, "core_payments_regression")
        self.assertEqual(report.severity, "degraded")
        self.assertEqual(report.incident_start, "14:03:40")
        self.assertEqual(report.risk_level, "high")
        self.assertIsNone(report.action_executed)
        self.assertIsNotNone(report.approval_request)
        self.assertEqual(report.approval_request["status"], "AWAITING HUMAN APPROVAL -- NOT EXECUTED")
        self.assertIn("not bypassing the gate", report.approval_request["note"])

    def test_e2e_assignment_1_db_pool_workflow(self) -> None:
        report = self.agent.run_incident(
            scenario_id="assignment_1_db_pool_exhaustion",
            urgency_prompt=False,
        )

        self.assertEqual(report.scenario_id, "assignment_1_db_pool_exhaustion")
        self.assertEqual(report.severity, "down")
        self.assertEqual(report.incident_start, "10:19:05")
        self.assertEqual(report.risk_level, "high")
        self.assertIsNone(report.action_executed)
        self.assertEqual(report.approval_request["proposed_action"], "scale")
        self.assertEqual(report.approval_request["status"], "AWAITING HUMAN APPROVAL -- NOT EXECUTED")
        self.assertNotIn("v1.1.9", report.approval_request["rollback_plan"])
        self.assertIn("N/A: Proposed action 'scale' is not a release rollback", report.approval_request["rollback_plan"])

    def test_e2e_assignment_2_safe_auto_remediation_workflow(self) -> None:
        report = self.agent.run_incident(
            scenario_id="assignment_2_safe_pod_restart",
            urgency_prompt=False,
        )

        self.assertEqual(report.scenario_id, "assignment_2_safe_pod_restart")
        self.assertEqual(report.severity, "early_warning")
        self.assertIsNone(report.incident_start)
        self.assertEqual(report.risk_level, "low")
        self.assertEqual(report.action_executed, "restart_single_pod")
        self.assertIsNone(report.approval_request)
        self.assertEqual(report.decision_trace.execution_outcome, "AUTO_EXECUTED")

    def test_e2e_markdown_and_json_report_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self.agent.run_incident("core_payments_regression", urgency_prompt=True)
            md_path, json_path = self.agent.save_report(report, output_dir=tmpdir)

            self.assertTrue(md_path.exists())
            self.assertTrue(json_path.exists())

            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            self.assertIn("Cloud Operations Incident Report", md_content)
            self.assertIn("AWAITING HUMAN APPROVAL -- NOT EXECUTED", md_content)
            self.assertIn("Simulation Disclaimer", md_content)

            with open(json_path, "r", encoding="utf-8") as f:
                loaded_json = json.load(f)
            self.assertEqual(loaded_json["severity"], "degraded")
            self.assertIsNone(loaded_json["action_executed"])


if __name__ == "__main__":
    unittest.main()
