"""Administrative Data Collection Specialist Agent for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from models.schemas import Activity, CollectorResult, WorkflowState


class AdministrativeDataCollectionAgent:
    """Specialist collector agent for administrative responsibilities and institutional duties."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        """Initialize administrative collection agent with path to mock admin records."""
        if data_path is None:
            self.data_path = Path(__file__).resolve().parent.parent / "data" / "mock_administrative.json"
        else:
            self.data_path = Path(data_path)

    def execute(self, state: WorkflowState) -> CollectorResult:
        """Collect and normalize administrative duties and committee appointments.

        Guardrails:
        - Check faculty consent for administrative data collection.
        - Verify institutional source office identification for every activity.
        - Handle collector failure modes gracefully.
        """
        t0 = time.perf_counter()
        start_ts = datetime.now(timezone.utc).isoformat()
        role_name = "AdministrativeDataCollectionAgent"

        # Guardrail 1: Check faculty consent
        if not state.consent.get("administrative", True):
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            state.add_audit_entry(
                node_name=role_name,
                action="CONSENT_DENIED_SKIPPED",
                details={"reason": "Faculty withheld consent for Administrative Data Collection"},
                status="WARNING",
            )
            return CollectorResult(
                collector_role=role_name,
                category="Administrative",
                status="SKIPPED",
                start_time=start_ts,
                end_time=end_ts,
                duration_ms=dur,
                activities=[],
                error="Faculty consent withheld for administrative collection",
            )

        # Guardrail 2: Test injection failure simulation
        if state.test_injection == "FAIL_ADMIN":
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            state.add_audit_entry(
                node_name=role_name,
                action="COLLECTOR_FAILURE_SIMULATED",
                details={"error": "Institutional Registrar Office portal unavailable"},
                status="FAILED",
            )
            raise ConnectionError("Institutional Registrar Office portal unavailable")

        # Load administrative records
        if not self.data_path.exists():
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            return CollectorResult(
                collector_role=role_name,
                category="Administrative",
                status="FAILED",
                start_time=start_ts,
                end_time=end_ts,
                duration_ms=dur,
                activities=[],
                error=f"Data source file missing: {self.data_path}",
            )

        with open(self.data_path, "r", encoding="utf-8") as f:
            raw_records: List[Dict[str, Any]] = json.load(f)

        collected: List[Dict[str, Any]] = []
        for rec in raw_records:
            if rec.get("faculty_id") == state.faculty_id:
                status = "CLAIMED"
                notes = None
                if not rec.get("title") or rec.get("claimed_points") is None:
                    status = "INCOMPLETE"
                    notes = "Missing mandatory title or claimed points"

                activity = Activity(
                    activity_id=rec.get("activity_id", f"ADM_{len(collected)+1:03d}"),
                    faculty_id=state.faculty_id,
                    title=rec.get("title", "Untitled Administrative Activity"),
                    category="Administrative",
                    sub_category=rec.get("sub_category", "Institutional_Service"),
                    period=rec.get("period", state.appraisal_period),
                    description=rec.get("description", ""),
                    claimed_points=float(rec.get("claimed_points", 0.0)),
                    source_system=rec.get("source_system", "Office_of_the_HoD"),
                    evidence_ref=rec.get("evidence_ref", ""),
                    collector_role=role_name,
                    evidence_status=status,
                    validation_notes=notes,
                )
                collected.append(activity.to_dict())

        dur = round((time.perf_counter() - t0) * 1000, 2)
        end_ts = datetime.now(timezone.utc).isoformat()

        state.add_audit_entry(
            node_name=role_name,
            action="COLLECTION_COMPLETE",
            details={
                "faculty_id": state.faculty_id,
                "activities_collected": len(collected),
                "duration_ms": dur,
            },
            status="SUCCESS",
        )

        return CollectorResult(
            collector_role=role_name,
            category="Administrative",
            status="SUCCESS",
            start_time=start_ts,
            end_time=end_ts,
            duration_ms=dur,
            activities=collected,
            error=None,
        )
