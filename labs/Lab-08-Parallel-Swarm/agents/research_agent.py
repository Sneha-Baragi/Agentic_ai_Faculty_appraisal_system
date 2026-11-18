"""Research Data Collection Specialist Agent for Lab 8 - Parallel Swarm.

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


class ResearchDataCollectionAgent:
    """Specialist collector agent for research activities (publications, grants, PhD guidance)."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        """Initialize research collection agent with path to mock research records."""
        if data_path is None:
            self.data_path = Path(__file__).resolve().parent.parent / "data" / "mock_research.json"
        else:
            self.data_path = Path(data_path)

    def execute(self, state: WorkflowState) -> CollectorResult:
        """Collect and normalize research records with privacy, consent, and failure handling.

        Guardrails:
        - Check faculty consent for research data collection.
        - Capture failure modes gracefully without terminating other swarm branches.
        - Normalize structured fields: faculty_id, activity_id, category, description, points, source, evidence_ref.
        """
        t0 = time.perf_counter()
        start_ts = datetime.now(timezone.utc).isoformat()
        role_name = "ResearchDataCollectionAgent"

        # Guardrail 1: Check faculty consent
        if not state.consent.get("research", True):
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            state.add_audit_entry(
                node_name=role_name,
                action="CONSENT_DENIED_SKIPPED",
                details={"reason": "Faculty withheld consent for Research Data Collection"},
                status="WARNING",
            )
            return CollectorResult(
                collector_role=role_name,
                category="Research",
                status="SKIPPED",
                start_time=start_ts,
                end_time=end_ts,
                duration_ms=dur,
                activities=[],
                error="Faculty consent withheld for research collection",
            )

        # Guardrail 2: Test injection failure simulation
        if state.test_injection == "FAIL_RESEARCH" or state.test_injection == "FAIL_COLLECTOR":
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            state.add_audit_entry(
                node_name=role_name,
                action="COLLECTOR_FAILURE_SIMULATED",
                details={"error": "Connection timeout connecting to Research Office Portal database"},
                status="FAILED",
            )
            raise ConnectionError("Connection timeout connecting to Research Office Portal database")

        # Load research records
        if not self.data_path.exists():
            dur = round((time.perf_counter() - t0) * 1000, 2)
            end_ts = datetime.now(timezone.utc).isoformat()
            return CollectorResult(
                collector_role=role_name,
                category="Research",
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
                if act_id == "RES_MISSING" and state.test_injection != "MISSING_EVIDENCE":
                    continue
                if act_id == "RES_MISMATCH" and state.test_injection != "MISMATCHED_EVIDENCE":
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
            category="Research",
            status="SUCCESS",
            start_time=start_ts,
            end_time=end_ts,
            duration_ms=dur,
            activities=collected,
            error=None,
        )
