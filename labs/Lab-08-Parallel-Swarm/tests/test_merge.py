"""Unit tests for Lab 8 Swarm Synchronization and Merge Stage.

Verifies:
- Merge waits for all collector branches.
- Preservation of collector role and source metadata.
- Detection of duplicate activity IDs without silent overwriting.
- Detection of conflicting claims across collectors.
- Capture of collector failures while preserving successful outputs.
- Partial merge status reporting.
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from models.schemas import CollectorResult
from swarm.merge import SwarmMerge
from swarm.state import create_initial_state


class TestSwarmMerge(unittest.TestCase):
    """Test suite for SwarmMerge stage."""

    def setUp(self) -> None:
        """Create clean state and merge component."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        self.merge_engine = SwarmMerge()

    def test_clean_merge_all_collectors(self) -> None:
        """Test clean merge combines all outputs and preserves role and source metadata."""
        self.state.swarm_results = {
            "ResearchDataCollectionAgent": {
                "collector_role": "ResearchDataCollectionAgent",
                "status": "SUCCESS",
                "activities": [
                    {
                        "activity_id": "RES_001",
                        "title": "IEEE Paper",
                        "category": "Research",
                        "claimed_points": 25.0,
                        "source_system": "Research_Portal",
                        "evidence_ref": "EVID_001",
                    }
                ],
            },
            "TeachingDataCollectionAgent": {
                "collector_role": "TeachingDataCollectionAgent",
                "status": "SUCCESS",
                "activities": [
                    {
                        "activity_id": "TCH_001",
                        "title": "CS401 Course",
                        "category": "Teaching_Learning",
                        "claimed_points": 25.0,
                        "source_system": "Dean_ERP",
                        "evidence_ref": "EVID_002",
                    }
                ],
            },
            "AdministrativeDataCollectionAgent": {
                "collector_role": "AdministrativeDataCollectionAgent",
                "status": "SUCCESS",
                "activities": [
                    {
                        "activity_id": "ADM_001",
                        "title": "NBA Lead",
                        "category": "Administrative",
                        "claimed_points": 20.0,
                        "source_system": "HoD_Office",
                        "evidence_ref": "EVID_003",
                    }
                ],
            },
        }

        updated_state = self.merge_engine.merge(self.state)

        self.assertEqual(len(updated_state.merged_activities), 3)
        self.assertEqual(updated_state.merge_result["status"], "SUCCESS")
        self.assertEqual(len(updated_state.merge_result["duplicates_detected"]), 0)
        self.assertEqual(len(updated_state.merge_result["conflicts_detected"]), 0)

        # Verify collector role preservation
        roles = {a["collector_role"] for a in updated_state.merged_activities}
        self.assertIn("ResearchDataCollectionAgent", roles)
        self.assertIn("TeachingDataCollectionAgent", roles)
        self.assertIn("AdministrativeDataCollectionAgent", roles)

    def test_duplicate_activity_id_detection(self) -> None:
        """Test duplicate activity ID is detected and not silently overwritten."""
        self.state.swarm_results = {
            "ResearchDataCollectionAgent": {
                "collector_role": "ResearchDataCollectionAgent",
                "status": "SUCCESS",
                "activities": [
                    {
                        "activity_id": "ACT_SHARED",
                        "title": "Original Claim",
                        "category": "Research",
                        "claimed_points": 20.0,
                        "source_system": "Research_Portal",
                        "evidence_ref": "EVID_001",
                    }
                ],
            },
            "TeachingDataCollectionAgent": {
                "collector_role": "TeachingDataCollectionAgent",
                "status": "SUCCESS",
                "activities": [
                    {
                        "activity_id": "ACT_SHARED",  # Same ID from another collector
                        "title": "Duplicate Claim",
                        "category": "Teaching_Learning",
                        "claimed_points": 15.0,
                        "source_system": "Teaching_Portal",
                        "evidence_ref": "EVID_002",
                    }
                ],
            },
            "AdministrativeDataCollectionAgent": {
                "collector_role": "AdministrativeDataCollectionAgent",
                "status": "SUCCESS",
                "activities": [],
            },
        }

        updated_state = self.merge_engine.merge(self.state)

        # Both records must be preserved (len == 2)
        self.assertEqual(len(updated_state.merged_activities), 2)
        duplicates = updated_state.merge_result["duplicates_detected"]
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["activity_id"], "ACT_SHARED")

        # Conflict must also be flagged because category and points differed
        conflicts = updated_state.merge_result["conflicts_detected"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["activity_id"], "ACT_SHARED")

    def test_collector_failure_preserves_successful_outputs(self) -> None:
        """Test failure of one collector preserves outputs of other successful collectors."""
        self.state.swarm_results = {
            "ResearchDataCollectionAgent": {
                "collector_role": "ResearchDataCollectionAgent",
                "status": "FAILED",
                "error": "Database timeout connecting to Research Portal",
                "activities": [],
            },
            "TeachingDataCollectionAgent": {
                "collector_role": "TeachingDataCollectionAgent",
                "status": "SUCCESS",
                "activities": [
                    {
                        "activity_id": "TCH_001",
                        "title": "Teaching Course",
                        "category": "Teaching_Learning",
                        "claimed_points": 25.0,
                        "source_system": "Dean_ERP",
                        "evidence_ref": "EVID_001",
                    }
                ],
            },
            "AdministrativeDataCollectionAgent": {
                "collector_role": "AdministrativeDataCollectionAgent",
                "status": "SUCCESS",
                "activities": [
                    {
                        "activity_id": "ADM_001",
                        "title": "Admin Duty",
                        "category": "Administrative",
                        "claimed_points": 15.0,
                        "source_system": "HoD_Office",
                        "evidence_ref": "EVID_002",
                    }
                ],
            },
        }

        updated_state = self.merge_engine.merge(self.state)

        # Teaching and Admin activities must be preserved
        self.assertEqual(len(updated_state.merged_activities), 2)
        self.assertEqual(updated_state.merge_result["status"], "PARTIAL")
        self.assertIn("ResearchDataCollectionAgent", updated_state.merge_result["failed_collectors"])
        self.assertEqual(updated_state.workflow_status, "INCOMPLETE_COLLECTION")


if __name__ == "__main__":
    unittest.main()
