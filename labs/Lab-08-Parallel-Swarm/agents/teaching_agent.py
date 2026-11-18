"""Teaching-Learning Data Collection Specialist Agent for Lab 8 - Parallel Swarm.

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


class TeachingDataCollectionAgent:
    """Specialist collector agent for teaching workload, aggregate feedback, and course outcomes."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        """Initialize teaching collection agent with path to mock teaching records."""
        if data_path is None:
            self.data_path = Path(__file__).resolve().parent.parent / "data" / "mock_teaching.json"
        else:
            self.data_path = Path(data_path)

    def execute(self, state: WorkflowState) -> CollectorResult:
        """Collect and normalize teaching records with student privacy guardrails.

        Guardrails:
        - Check faculty consent for teaching-learning data collection.
        - Privacy preservation: Only aggregate student feedback is permitted.
        - Individual student roll numbers, USNs, and raw comments must never be exposed.
        - Handle collector failure modes gracefully.
        """
        t0 = time.perf_counter()
        start_ts = datetime.now(timezone.utc).isoformat()
        role_name = "TeachingDataCollectionAgent"

        # Guardrail 1: Check faculty consent
        if not state.consent.get("teaching_learning", True):
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            state.add_audit_entry(
                node_name=role_name,
                action="CONSENT_DENIED_SKIPPED",
                details={"reason": "Faculty withheld consent for Teaching-Learning Data Collection"},
                status="WARNING",
            )
            return CollectorResult(
                collector_role=role_name,
                category="Teaching_Learning",
                status="SKIPPED",
                start_time=start_ts,
                end_time=end_ts,
                duration_ms=dur,
                activities=[],
                error="Faculty consent withheld for teaching collection",
            )

        # Guardrail 2: Test injection failure simulation
        if state.test_injection == "FAIL_TEACHING":
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            state.add_audit_entry(
                node_name=role_name,
                action="COLLECTOR_FAILURE_SIMULATED",
                details={"error": "Academic ERP database connection failure"},
                status="FAILED",
            )
            raise ConnectionError("Academic ERP database connection failure")

        # Load teaching records
        if not self.data_path.exists():
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            return CollectorResult(
                collector_role=role_name,
                category="Teaching_Learning",
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
                # Handle test injections
                act_id = rec.get("activity_id")
                if act_id == "TCH_MISMATCH" and state.test_injection not in ("MISMATCHED_EVIDENCE", "MISMATCHED_TEACHING"):
                    continue

                # Guardrail 3: Privacy preservation - aggregate student feedback only
                description = rec.get("description", "")
                if rec.get("sub_category") == "Student_Feedback":
                    for forbidden in ["usn", "student_name", "email", "phone", "student_id", "roll_number"]:
                        if forbidden in description.lower():
                            description = "[REDACTED] Non-aggregate feedback removed for student privacy"

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
                    sub_category=rec.get("sub_category", "Instructional_Delivery"),
                    period=rec.get("period", state.appraisal_period),
                    description=description,
                    claimed_points=float(rec.get("claimed_points", 0.0)),
                    source_system=rec.get("source_system", "Academic_Dean_ERP"),
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
                "privacy_preserved": True,
                "duration_ms": dur,
            },
            status="SUCCESS",
        )

        return CollectorResult(
            collector_role=role_name,
            category="Teaching_Learning",
            status="SUCCESS",
            start_time=start_ts,
            end_time=end_ts,
            duration_ms=dur,
            activities=collected,
            error=None,
        )
