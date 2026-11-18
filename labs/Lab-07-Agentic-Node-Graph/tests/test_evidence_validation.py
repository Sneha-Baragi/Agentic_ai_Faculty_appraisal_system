"""Unit tests for Lab 7 Evidence Validation Agent (Group D).

Verifies validation logic: VERIFIED, MISSING_EVIDENCE, MISMATCHED_EVIDENCE
(faculty ID mismatch and category mismatch), and INCOMPLETE claims.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

# Ensure Lab 7 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.evidence_validation_agent import EvidenceValidationAgent
from graph.state import create_initial_state
from models.schemas import WorkflowState


class TestEvidenceValidation(unittest.TestCase):
    """Test suite for EvidenceValidationAgent."""

    def setUp(self) -> None:
        """Create test state and mock evidence files."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )

        self.mock_evidence = [
            {
                "evidence_id": "EVID_VALID_RES",
                "faculty_id": "FAC001",
                "category": "Research",
                "document_name": "IEEE_Paper.pdf",
                "issuing_authority": "IEEE",
                "issue_date": "2025-08-15",
                "verified_checksum": "sha256:abc123",
                "status": "VALID",
            },
            {
                "evidence_id": "EVID_OTHER_FAC",
                "faculty_id": "FAC002",  # Belongs to another faculty
                "category": "Research",
                "document_name": "Other_Faculty_Grant.pdf",
                "issuing_authority": "DST",
                "issue_date": "2025-05-10",
                "verified_checksum": "sha256:def456",
            },
            {
                "evidence_id": "EVID_CAT_MISMATCH",
                "faculty_id": "FAC001",
                "category": "Teaching_Learning",  # Registered as Teaching
                "document_name": "Teaching_Award.pdf",
                "issuing_authority": "Registrar",
                "issue_date": "2025-09-01",
                "verified_checksum": "sha256:789ghi",
            },
        ]

    def test_verified_claim(self) -> None:
        """Test valid claim matching registered evidence is marked VERIFIED."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ev_file = Path(tmp_dir) / "evidence.json"
            ev_file.write_text(json.dumps(self.mock_evidence), encoding="utf-8")

            self.state.research_activities = [
                {
                    "activity_id": "ACT_001",
                    "faculty_id": "FAC001",
                    "title": "IEEE Journal Paper",
                    "category": "Research",
                    "claimed_points": 25.0,
                    "evidence_ref": "EVID_VALID_RES",
                }
            ]

            agent = EvidenceValidationAgent(evidence_path=ev_file)
            res_state = agent.execute(self.state)

            self.assertEqual(len(res_state.evidence_exceptions), 0)
            self.assertEqual(len(res_state.validated_activities), 1)
            self.assertEqual(res_state.validated_activities[0]["evidence_status"], "VERIFIED")

    def test_missing_evidence(self) -> None:
        """Test claim referencing non-existent evidence is flagged as MISSING_EVIDENCE."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ev_file = Path(tmp_dir) / "evidence.json"
            ev_file.write_text(json.dumps(self.mock_evidence), encoding="utf-8")

            self.state.research_activities = [
                {
                    "activity_id": "ACT_MISSING",
                    "faculty_id": "FAC001",
                    "title": "Unregistered Patent",
                    "category": "Research",
                    "claimed_points": 15.0,
                    "evidence_ref": "EVID_NON_EXISTENT",
                }
            ]

            agent = EvidenceValidationAgent(evidence_path=ev_file)
            res_state = agent.execute(self.state)

            self.assertEqual(len(res_state.evidence_exceptions), 1)
            exc = res_state.evidence_exceptions[0]
            self.assertEqual(exc["evidence_status"], "MISSING_EVIDENCE")
            self.assertIn("not found in registry", exc["validation_notes"])

    def test_mismatched_faculty_evidence(self) -> None:
        """Test claim using another faculty member's evidence is flagged as MISMATCHED_EVIDENCE."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ev_file = Path(tmp_dir) / "evidence.json"
            ev_file.write_text(json.dumps(self.mock_evidence), encoding="utf-8")

            self.state.research_activities = [
                {
                    "activity_id": "ACT_MISMATCH_FAC",
                    "faculty_id": "FAC001",
                    "title": "Claimed Other Grant",
                    "category": "Research",
                    "claimed_points": 30.0,
                    "evidence_ref": "EVID_OTHER_FAC",
                }
            ]

            agent = EvidenceValidationAgent(evidence_path=ev_file)
            res_state = agent.execute(self.state)

            self.assertEqual(len(res_state.evidence_exceptions), 1)
            exc = res_state.evidence_exceptions[0]
            self.assertEqual(exc["evidence_status"], "MISMATCHED_EVIDENCE")
            self.assertIn("document belongs to 'FAC002'", exc["validation_notes"])

    def test_mismatched_category_evidence(self) -> None:
        """Test claim where activity category does not match evidence category."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ev_file = Path(tmp_dir) / "evidence.json"
            ev_file.write_text(json.dumps(self.mock_evidence), encoding="utf-8")

            # Claimed under Research, but evidence is Teaching_Learning
            self.state.research_activities = [
                {
                    "activity_id": "ACT_MISMATCH_CAT",
                    "faculty_id": "FAC001",
                    "title": "Claimed under Research",
                    "category": "Research",
                    "claimed_points": 20.0,
                    "evidence_ref": "EVID_CAT_MISMATCH",
                }
            ]

            agent = EvidenceValidationAgent(evidence_path=ev_file)
            res_state = agent.execute(self.state)

            self.assertEqual(len(res_state.evidence_exceptions), 1)
            exc = res_state.evidence_exceptions[0]
            self.assertEqual(exc["evidence_status"], "MISMATCHED_EVIDENCE")
            self.assertIn("Category mismatch", exc["validation_notes"])

    def test_incomplete_claim(self) -> None:
        """Test incomplete claims with missing title or non-positive points."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ev_file = Path(tmp_dir) / "evidence.json"
            ev_file.write_text(json.dumps(self.mock_evidence), encoding="utf-8")

            self.state.teaching_activities = [
                {
                    "activity_id": "ACT_INCOMPLETE",
                    "faculty_id": "FAC001",
                    "title": "",
                    "category": "Teaching_Learning",
                    "claimed_points": 0.0,
                    "evidence_ref": "EVID_VALID_RES",
                }
            ]

            agent = EvidenceValidationAgent(evidence_path=ev_file)
            res_state = agent.execute(self.state)

            self.assertEqual(len(res_state.evidence_exceptions), 1)
            exc = res_state.evidence_exceptions[0]
            self.assertEqual(exc["evidence_status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
