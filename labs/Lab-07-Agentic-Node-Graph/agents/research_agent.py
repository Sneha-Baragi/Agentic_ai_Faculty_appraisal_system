"""Node 1: Research Data Collection Agent (Group A).

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from models.schemas import Activity, WorkflowState


class ResearchAgent:
    """Collects and normalizes faculty research records (publications, grants, guidance)."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        """Initialize research agent with path to mock research records."""
        if data_path is None:
            self.data_path = Path(__file__).resolve().parent.parent / "data" / "mock_research.json"
        else:
            self.data_path = Path(data_path)

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Execute research data collection with faculty consent guardrails.

        Guardrails:
        - Check faculty consent before collecting records.
        - If consent is False, abort collection for this source and record denial.
        - Flag incomplete activity records.
        - Preserve the source of each activity.
        """
        # Guardrail 1: Check consent
        if not state.consent.get("research", True):
            state.add_audit_entry(
                node_name="ResearchAgent",
                action="CONSENT_DENIED_SKIPPED",
                details={"reason": "Faculty denied consent for Research Data Collection"},
                status="WARNING",
            )
            state.research_activities = []
            return state

        # Load research records
        if not self.data_path.exists():
            state.add_audit_entry(
                node_name="ResearchAgent",
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
                act_id = rec.get("activity_id")
                if act_id == "RES_MISSING" and not state.include_missing_evidence:
                    continue
                if act_id == "RES_MISMATCH" and not state.include_mismatched_evidence:
                    continue

                # Flag incomplete records
                status = "CLAIMED"
                notes = None
                if not rec.get("title") or rec.get("claimed_points") is None:
                    status = "INCOMPLETE"
                    notes = "Missing mandatory title or claimed points"

                activity = Activity(
                    activity_id=rec.get("activity_id", f"RES_{len(collected)+1:03d}"),
                    faculty_id=state.faculty_id,
                    title=rec.get("title", "Untitled Research Activity"),
                    category="Research",
                    sub_category=rec.get("sub_category", "General"),
                    period=rec.get("period", state.appraisal_period),
                    description=rec.get("description", ""),
                    claimed_points=float(rec.get("claimed_points", 0.0)),
                    source_system=rec.get("source_system", "Research_Office_Portal"),
                    evidence_ref=rec.get("evidence_ref", ""),
                    evidence_status=status,
                    validation_notes=notes,
                )
                collected.append(activity.to_dict())

        state.research_activities = collected
        state.add_audit_entry(
            node_name="ResearchAgent",
            action="COLLECTION_COMPLETE",
            details={
                "faculty_id": state.faculty_id,
                "activities_collected": len(collected),
                "source": "Research_Office_Portal",
            },
            status="SUCCESS",
        )
        return state
