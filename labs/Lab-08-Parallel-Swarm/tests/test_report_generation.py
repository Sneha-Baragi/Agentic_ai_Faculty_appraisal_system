"""Unit tests for Lab 8 Report Generation Agent.

Verifies:
- Structured appraisal report schema and category summaries.
- Versioning (v1, v2) within state.
- Distinct filenames per workflow run to prevent overwriting earlier reports.
- Automatic version increment when filename collision occurs on disk.
- Traceability metadata (scenario_name, run_id, faculty_id) preserved in payload.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.report_generation_agent import ReportGenerationAgent
from swarm.state import create_initial_state


class TestReportGeneration(unittest.TestCase):
    """Test suite for ReportGenerationAgent."""

    def setUp(self) -> None:
        """Create clean test state with mock validated activities."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
            run_id="RUN_REP_TEST",
            scenario_name="scenario_test",
        )
        self.state.merged_activities = [
            {"activity_id": "RES_1", "category": "Research", "claimed_points": 25.0},
            {"activity_id": "TEA_1", "category": "Teaching_Learning", "claimed_points": 25.0},
            {"activity_id": "ADM_1", "category": "Administrative", "claimed_points": 20.0},
        ]
        self.state.validated_activities = [
            {"activity_id": "RES_1", "category": "Research", "claimed_points": 25.0, "evidence_status": "VERIFIED"},
            {"activity_id": "TEA_1", "category": "Teaching_Learning", "claimed_points": 25.0, "evidence_status": "VERIFIED"},
            {"activity_id": "ADM_1", "category": "Administrative", "claimed_points": 20.0, "evidence_status": "VERIFIED"},
        ]
        self.state.api_score = {
            "overall_claimed_score": 24.0,
            "overall_verified_score": 24.0,
            "is_provisional": False,
            "score_status": "FINALIZED_PENDING_APPROVAL",
            "category_scores": {},
        }

    def test_report_structure_and_artifact_creation(self) -> None:
        """Test report payload contains all required fields and creates JSON artifact on disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))
            res_state = agent.execute(self.state)

            report = res_state.report
            self.assertEqual(report["version"], "v1")
            self.assertEqual(report["status"], "DRAFT_PENDING_APPROVAL")
            self.assertEqual(report["faculty_id"], "FAC001")
            self.assertEqual(report["faculty_name"], "Dr. Ananya Sharma")
            self.assertEqual(report["run_id"], "RUN_REP_TEST")
            self.assertEqual(report["scenario_name"], "scenario_test")

            # Check that file artifact exists
            artifact_file = Path(report["artifact_path"])
            self.assertTrue(artifact_file.exists())
            self.assertTrue(artifact_file.name.endswith(".json"))

    def test_report_versioning_within_workflow(self) -> None:
        """Test repeated generation of reports in same workflow state increments version number."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))

            # Run 1 -> v1
            state_v1 = agent.execute(self.state)
            self.assertEqual(state_v1.report["version"], "v1")
            path_v1 = Path(state_v1.report["artifact_path"])

            # Run 2 -> v2
            state_v2 = agent.execute(state_v1)
            self.assertEqual(state_v2.report["version"], "v2")
            path_v2 = Path(state_v2.report["artifact_path"])

            self.assertNotEqual(path_v1, path_v2)
            self.assertTrue(path_v1.exists())
            self.assertTrue(path_v2.exists())

    def test_multiple_workflow_runs_do_not_overwrite(self) -> None:
        """Test that distinct workflow runs preserve their respective reports on disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))

            # Run 1
            state_1 = create_initial_state(
                faculty_id="FAC001",
                appraisal_period="2025-2026",
                run_id="RUN_ALPHA",
                scenario_name="scenario_a_success",
            )
            state_1.api_score = dict(self.state.api_score)
            res_1 = agent.execute(state_1)
            path_1 = Path(res_1.report["artifact_path"])

            # Run 2 (same faculty and cycle, different run_id & scenario)
            state_2 = create_initial_state(
                faculty_id="FAC001",
                appraisal_period="2025-2026",
                run_id="RUN_BETA",
                scenario_name="scenario_b_missing_evidence",
            )
            state_2.api_score = dict(self.state.api_score)
            res_2 = agent.execute(state_2)
            path_2 = Path(res_2.report["artifact_path"])

            self.assertNotEqual(path_1, path_2)
            self.assertTrue(path_1.exists())
            self.assertTrue(path_2.exists())

            # Verify contents remain intact
            with open(path_1, "r", encoding="utf-8") as f:
                d1 = json.load(f)
            with open(path_2, "r", encoding="utf-8") as f:
                d2 = json.load(f)

            self.assertEqual(d1["run_id"], "RUN_ALPHA")
            self.assertEqual(d2["run_id"], "RUN_BETA")

    def test_version_increment_on_disk_collision(self) -> None:
        """Test that if a report with identical run_id exists, version increments to avoid overwrite."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))

            state_1 = create_initial_state(
                faculty_id="FAC001",
                appraisal_period="2025-2026",
                run_id="RUN_SAME",
                scenario_name="test_col",
            )
            state_1.api_score = dict(self.state.api_score)
            res_1 = agent.execute(state_1)
            path_1 = Path(res_1.report["artifact_path"])
            self.assertEqual(res_1.report["version"], "v1")

            state_2 = create_initial_state(
                faculty_id="FAC001",
                appraisal_period="2025-2026",
                run_id="RUN_SAME",
                scenario_name="test_col",
            )
            state_2.api_score = dict(self.state.api_score)
            res_2 = agent.execute(state_2)
            path_2 = Path(res_2.report["artifact_path"])

            self.assertEqual(res_2.report["version"], "v2")
            self.assertTrue(path_1.exists())
            self.assertTrue(path_2.exists())


if __name__ == "__main__":
    unittest.main()
