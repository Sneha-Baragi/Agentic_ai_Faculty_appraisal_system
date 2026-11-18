"""Node 2: Teaching-Learning Data Collection Agent (Group B).

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from models.schemas import Activity, WorkflowState


class TeachingAgent:
    """Collects and normalizes teaching-learning records (instruction, aggregate feedback, FDPs)."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        """Initialize teaching agent with path to mock academic records."""
        if data_path is None:
            self.data_path = Path(__file__).resolve().parent.parent / "data" / "mock_teaching.json"
        else:
            self.data_path = Path(data_path)

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Execute teaching-learning data collection with privacy and consent guardrails.

        Guardrails:
        - Check faculty consent.
        - Use only authorized academic records.
        - Never expose individual student feedback; use aggregate feedback scores only.
        - Flag incomplete activity records.
        - Preserve source references.
        """
        # Guardrail 1: Check consent
        if not state.consent.get("teaching_learning", True):
            state.add_audit_entry(
                node_name="TeachingAgent",
                action="CONSENT_DENIED_SKIPPED",
                details={"reason": "Faculty denied consent for Teaching-Learning Data Collection"},
                status="WARNING",
            )
            state.teaching_activities = []
            return state

        if not self.data_path.exists():
            state.add_audit_entry(
                node_name="TeachingAgent",
                action="DATA_SOURCE_MISSING",
                details={"path": str(self.data_path)},
                status="FAILED",
            )
            return state

        with open(self.data_path, "r", encoding="utf-8") as f:
            raw_records: List[Dict[str, Any]] = json.load(f)

        collected: List[Dict[str, Any]] = []
        for rec in raw_records:
            if rec.get("faculty_id") == state.faculty_id:
                # Guardrail 2: Aggregate feedback privacy check
                # Ensure no individual student identifiers or raw unaggregated surveys leak
                sub_cat = rec.get("sub_category", "")
                desc = rec.get("description", "")
                if sub_cat == "Student_Feedback" and "individual" in desc.lower():
                    # Mask or sanitize to preserve privacy
                    desc = "Sanitized aggregate student feedback index"

                status = "CLAIMED"
                notes = None
                if not rec.get("title") or rec.get("claimed_points") is None:
                    status = "INCOMPLETE"
                    notes = "Missing mandatory title or claimed points"

                activity = Activity(
                    activity_id=rec.get("activity_id", f"TCH_{len(collected)+1:03d}"),
                    faculty_id=state.faculty_id,
                    title=rec.get("title", "Untitled Teaching Activity"),
                    category="Teaching_Learning",
                    sub_category=sub_cat or "Instructional_Delivery",
                    period=rec.get("period", state.appraisal_period),
                    description=desc,
                    claimed_points=float(rec.get("claimed_points", 0.0)),
                    source_system=rec.get("source_system", "Academic_Dean_ERP"),
                    evidence_ref=rec.get("evidence_ref", ""),
                    evidence_status=status,
                    validation_notes=notes,
                )
                collected.append(activity.to_dict())

        state.teaching_activities = collected
        state.add_audit_entry(
            node_name="TeachingAgent",
            action="COLLECTION_COMPLETE",
            details={
                "faculty_id": state.faculty_id,
                "activities_collected": len(collected),
                "source": "Academic_Dean_ERP",
                "privacy_guardrail": "Aggregate feedback only",
            },
            status="SUCCESS",
        )
        return state
