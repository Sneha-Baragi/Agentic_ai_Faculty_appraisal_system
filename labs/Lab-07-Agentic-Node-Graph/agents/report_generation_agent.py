"""Node 6: Report Generation Agent (Group F).

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from models.schemas import WorkflowState


class ReportGenerationAgent:
    """Generates structured appraisal reports with versioning and dashboard summaries."""

    def __init__(self, reports_dir: Optional[Path] = None) -> None:
        """Initialize report generation agent."""
        if reports_dir is None:
            self.reports_dir = Path(__file__).resolve().parent.parent / "reports"
        else:
            self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Generate structured appraisal report distinguishing raw vs validated data.

        Guardrails:
        - Only use validated data for verified scores.
        - Clearly distinguish provisional vs approved API scores.
        - Implement report versioning (v1, v2, ...).
        - Mark report status as DRAFT/GENERATED (cannot publish before approval).
        - Ensure report filenames are unique and do not overwrite previous workflow runs.
        - Ensure report artifacts remain traceable to their scenario, faculty, and workflow run.
        """
        # Determine version based on previous audit history in state
        report_runs = [
            e for e in state.audit_log if e.get("action") == "REPORT_GENERATED"
        ]
        version_num = len(report_runs) + 1

        # Format scenario slug if scenario_name is specified
        scenario_slug = ""
        if getattr(state, "scenario_name", None):
            clean_scenario = "".join(
                c if c.isalnum() or c in ("-", "_") else "_"
                for c in str(state.scenario_name)
            ).strip("_")
            if clean_scenario:
                scenario_slug = f"{clean_scenario}_"

        # Ensure unique filename that does not overwrite an existing artifact on disk
        # and preserves versioning across multiple generations
        while True:
            version = f"v{version_num}"
            report_filename = (
                f"{state.faculty_id}_{state.appraisal_period}_{scenario_slug}{state.run_id}_{version}.json"
            )
            report_path = self.reports_dir / report_filename
            if not report_path.exists():
                break
            version_num += 1

        timestamp = datetime.now(timezone.utc).isoformat()
        api_data = state.api_score
        is_provisional = api_data.get("is_provisional", True)

        # Distinguish raw self-reported vs validated activities
        raw_activities = (
            state.research_activities
            + state.teaching_activities
            + state.administrative_activities
        )
        validated_activities = state.validated_activities
        verified_activities = [
            a for a in validated_activities if a.get("evidence_status") == "VERIFIED"
        ]

        # Construct unique, traceable report_id
        report_id_parts = ["REP", state.faculty_id]
        if scenario_slug:
            report_id_parts.append(scenario_slug.strip("_").upper())
        report_id_parts.append(state.run_id)
        report_id_parts.append(version.upper())
        report_id = "_".join(report_id_parts)

        report_payload = {
            "report_id": report_id,
            "run_id": state.run_id,
            "scenario_name": getattr(state, "scenario_name", None),
            "version": version,
            "generated_at": timestamp,
            "faculty_id": state.faculty_id,
            "faculty_name": state.faculty_name,
            "appraisal_period": state.appraisal_period,
            "status": "DRAFT_PENDING_APPROVAL",
            "is_provisional": is_provisional,
            "summary": {
                "total_claimed_activities": len(raw_activities),
                "total_verified_activities": len(verified_activities),
                "total_exceptions": len(state.evidence_exceptions),
                "claimed_raw_api_score": api_data.get("overall_claimed_score", 0.0),
                "verified_api_score": api_data.get("overall_verified_score", 0.0),
                "score_status": "PROVISIONAL" if is_provisional else "FINALIZED_PENDING_APPROVAL",
            },
            "category_breakdown": api_data.get("category_scores", {}),
            "evidence_exceptions": state.evidence_exceptions,
            "verified_activities": verified_activities,
            "raw_activities_count": len(raw_activities),
            "review_decision": None,
        }

        # Save report JSON artifact to reports/ directory
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2)
            f.write("\n")

        report_payload["artifact_path"] = str(report_path)
        state.report = report_payload
        state.workflow_status = "REPORT_GENERATED"

        state.add_audit_entry(
            node_name="ReportGenerationAgent",
            action="REPORT_GENERATED",
            details={
                "report_id": report_payload["report_id"],
                "run_id": state.run_id,
                "scenario_name": getattr(state, "scenario_name", None),
                "version": version,
                "is_provisional": is_provisional,
                "file": report_filename,
            },
            status="SUCCESS",
        )
        return state
