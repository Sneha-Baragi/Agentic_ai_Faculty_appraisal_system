"""Unit tests for Lab 7 Report Generation Agent (Group F).

Verifies report structure, versioning (v1, v2), distinguishing raw vs verified
metrics, artifact persistence in reports/ directory, and draft status.
"""

from pathlib import Path
import sys
import tempfile
import unittest

# Ensure Lab 7 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.report_generation_agent import ReportGenerationAgent
from graph.state import create_initial_state
from models.schemas import WorkflowState


class TestReportGeneration(unittest.TestCase):
    """Test suite for ReportGenerationAgent."""

    def setUp(self) -> None:
        """Create test state with mock validated activities and scores."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        self.state.research_activities = [
            {"activity_id": "RES_1", "claimed_points": 25.0}
        ]
        self.state.teaching_activities = [
            {"activity_id": "TEA_1", "claimed_points": 20.0}
        ]
        self.state.administrative_activities = [
            {"activity_id": "ADM_1", "claimed_points": 15.0}
        ]
        self.state.validated_activities = [
            {"activity_id": "RES_1", "claimed_points": 25.0, "evidence_status": "VERIFIED"},
            {"activity_id": "TEA_1", "claimed_points": 20.0, "evidence_status": "VERIFIED"},
            {"activity_id": "ADM_1", "claimed_points": 15.0, "evidence_status": "VERIFIED"},
        ]
        self.state.api_score = {
            "overall_claimed_score": 21.0,
            "overall_verified_score": 21.0,
            "is_provisional": False,
            "score_status": "FINALIZED_PENDING_APPROVAL",
            "category_scores": {},
        }

    def test_report_structure_and_artifact_creation(self) -> None:
        """Test report contains all required fields and writes JSON artifact to reports dir."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))
            res_state = agent.execute(self.state)

            report = res_state.report
            self.assertEqual(report["version"], "v1")
            self.assertEqual(report["status"], "DRAFT_PENDING_APPROVAL")
            self.assertEqual(report["faculty_id"], "FAC001")
            self.assertEqual(report["faculty_name"], "Dr. Jane Doe")
            self.assertFalse(report["is_provisional"])

            summary = report["summary"]
            self.assertEqual(summary["total_claimed_activities"], 3)
            self.assertEqual(summary["total_verified_activities"], 3)
            self.assertEqual(summary["total_exceptions"], 0)

            # Check that file artifact was created on disk
            artifact_file = Path(report["artifact_path"])
            self.assertTrue(artifact_file.exists())
            self.assertTrue(artifact_file.name.endswith(".json"))

    def test_report_versioning(self) -> None:
        """Test repeated generation of reports increments version number."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))

            # Run 1 -> v1
            state_v1 = agent.execute(self.state)
            self.assertEqual(state_v1.report["version"], "v1")

            # Run 2 -> v2
            state_v2 = agent.execute(state_v1)
            self.assertEqual(state_v2.report["version"], "v2")

    def test_provisional_report_flagging(self) -> None:
        """Test report reflects provisional score status when exceptions exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.state.api_score["is_provisional"] = True
            self.state.api_score["score_status"] = "PROVISIONAL"
            self.state.evidence_exceptions = [
                {"activity_id": "RES_MISSING", "evidence_status": "MISSING_EVIDENCE"}
            ]

            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))
            res_state = agent.execute(self.state)

            self.assertTrue(res_state.report["is_provisional"])
            self.assertEqual(res_state.report["summary"]["score_status"], "PROVISIONAL")
            self.assertEqual(res_state.report["summary"]["total_exceptions"], 1)

    def test_multiple_workflow_runs_do_not_overwrite(self) -> None:
        """Test that distinct workflow runs preserve their respective reports on disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))

            # Run 1: Scenario A
            state_1 = create_initial_state(
                faculty_id="FAC001",
                faculty_name="Dr. Jane Doe",
                appraisal_period="2025-2026",
                run_id="RUN_AAA111",
                scenario_name="scenario_a_success",
            )
            state_1.api_score = dict(self.state.api_score)
            res_1 = agent.execute(state_1)
            path_1 = Path(res_1.report["artifact_path"])

            # Run 2: Scenario B (same faculty, same cycle, different scenario & run_id)
            state_2 = create_initial_state(
                faculty_id="FAC001",
                faculty_name="Dr. Jane Doe",
                appraisal_period="2025-2026",
                run_id="RUN_BBB222",
                scenario_name="scenario_b_missing_evidence",
            )
            state_2.api_score = dict(self.state.api_score)
            res_2 = agent.execute(state_2)
            path_2 = Path(res_2.report["artifact_path"])

            # Verify paths are distinct and both exist
            self.assertNotEqual(path_1, path_2)
            self.assertTrue(path_1.exists(), "Report 1 was deleted or overwritten")
            self.assertTrue(path_2.exists(), "Report 2 was not created")

            # Verify contents of report 1 remain uncorrupted
            import json
            with open(path_1, "r", encoding="utf-8") as f:
                data_1 = json.load(f)
            with open(path_2, "r", encoding="utf-8") as f:
                data_2 = json.load(f)

            self.assertEqual(data_1["run_id"], "RUN_AAA111")
            self.assertEqual(data_1["scenario_name"], "scenario_a_success")
            self.assertEqual(data_2["run_id"], "RUN_BBB222")
            self.assertEqual(data_2["scenario_name"], "scenario_b_missing_evidence")

    def test_version_increment_on_disk_collision(self) -> None:
        """Test automatic version increment when an artifact with the same name exists on disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))

            # Run 1 with explicit run_id
            state_1 = create_initial_state(
                faculty_id="FAC001",
                appraisal_period="2025-2026",
                run_id="RUN_SAME_ID",
                scenario_name="scenario_test",
            )
            state_1.api_score = dict(self.state.api_score)
            res_1 = agent.execute(state_1)
            path_1 = Path(res_1.report["artifact_path"])
            self.assertEqual(res_1.report["version"], "v1")
            self.assertTrue(path_1.name.endswith("_v1.json"))

            # Run 2 with same run_id but fresh state (audit log has 0 entries)
            state_2 = create_initial_state(
                faculty_id="FAC001",
                appraisal_period="2025-2026",
                run_id="RUN_SAME_ID",
                scenario_name="scenario_test",
            )
            state_2.api_score = dict(self.state.api_score)
            res_2 = agent.execute(state_2)
            path_2 = Path(res_2.report["artifact_path"])

            # Verify version incremented to avoid overwrite
            self.assertEqual(res_2.report["version"], "v2")
            self.assertTrue(path_2.name.endswith("_v2.json"))
            self.assertTrue(path_1.exists())
            self.assertTrue(path_2.exists())

    def test_traceability_metadata_preservation(self) -> None:
        """Test report payload contains all traceability metadata."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = ReportGenerationAgent(reports_dir=Path(tmp_dir))
            state = create_initial_state(
                faculty_id="FAC005",
                faculty_name="Dr. Test Scholar",
                appraisal_period="2025-2026",
                run_id="RUN_TRACE_001",
                scenario_name="scenario_d_human_rejection",
            )
            state.api_score = dict(self.state.api_score)
            res = agent.execute(state)

            report = res.report
            self.assertEqual(report["faculty_id"], "FAC005")
            self.assertEqual(report["faculty_name"], "Dr. Test Scholar")
            self.assertEqual(report["appraisal_period"], "2025-2026")
            self.assertEqual(report["run_id"], "RUN_TRACE_001")
            self.assertEqual(report["scenario_name"], "scenario_d_human_rejection")
            self.assertIn("RUN_TRACE_001", report["report_id"])
            self.assertIn("SCENARIO_D_HUMAN_REJECTION", report["report_id"])


if __name__ == "__main__":
    unittest.main()
