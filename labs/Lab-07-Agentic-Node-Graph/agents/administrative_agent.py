"""Node 3: Administrative Data Collection Agent (Group C).

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from models.schemas import Activity, WorkflowState


class AdministrativeAgent:
    """Collects and normalizes administrative and institutional governance responsibilities."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        """Initialize administrative agent with path to mock admin records."""
        if data_path is None:
            self.data_path = Path(__file__).resolve().parent.parent / "data" / "mock_administrative.json"
        else:
            self.data_path = Path(data_path)

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Execute administrative data collection with institutional guardrails.

        Guardrails:
        - Check faculty consent.
        - Use authorized administrative records only.
        - Cite the source office for every entry.
        - Flag undocumented responsibilities.
        """
        # Guardrail 1: Check consent
        if not state.consent.get("administrative", True):
            state.add_audit_entry(
                node_name="AdministrativeAgent",
                action="CONSENT_DENIED_SKIPPED",
                details={"reason": "Faculty denied consent for Administrative Data Collection"},
                status="WARNING",
            )
            state.administrative_activities = []
            return state

        if not self.data_path.exists():
            state.add_audit_entry(
                node_name="AdministrativeAgent",
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
                # Guardrail 2: Source office citation check
                source_office = rec.get("source_system", "Registrar_Administrative_Portal")
                status = "CLAIMED"
                notes = None
                if not rec.get("evidence_ref"):
                    status = "INCOMPLETE"
                    notes = "Undocumented administrative responsibility (missing evidence reference)"

                activity = Activity(
                    activity_id=rec.get("activity_id", f"ADM_{len(collected)+1:03d}"),
                    faculty_id=state.faculty_id,
                    title=rec.get("title", "Untitled Administrative Duty"),
                    category="Administrative",
                    sub_category=rec.get("sub_category", "Committee_Work"),
                    period=rec.get("period", state.appraisal_period),
                    description=rec.get("description", ""),
                    claimed_points=float(rec.get("claimed_points", 0.0)),
                    source_system=source_office,
                    evidence_ref=rec.get("evidence_ref", ""),
                    evidence_status=status,
                    validation_notes=notes,
                )
                collected.append(activity.to_dict())

        state.administrative_activities = collected
        state.add_audit_entry(
            node_name="AdministrativeAgent",
            action="COLLECTION_COMPLETE",
            details={
                "faculty_id": state.faculty_id,
                "activities_collected": len(collected),
                "source": "Registrar_Administrative_Portal",
            },
            status="SUCCESS",
        )
        return state
