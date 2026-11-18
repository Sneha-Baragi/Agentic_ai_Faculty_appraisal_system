"""Report Generation Specialist Agent for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.schemas import WorkflowState


class ReportGenerationAgent:
    """Generates structured, versioned appraisal reports and saves non-overwriting JSON artifacts."""

    def __init__(self, reports_dir: Optional[Path] = None) -> None:
        """Initialize report generation agent with output directory."""
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
        - Implement versioning (v1, v2, ...).
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
        api_data = state.api_score or {}
        is_provisional = api_data.get("is_provisional", True)

        raw_activities = state.merged_activities
        validated_activities = state.validated_activities
        verified_activities = [
            a for a in validated_activities if a.get("evidence_status") == "VERIFIED"
        ]

        # Summaries by category
        research_raw = [a for a in raw_activities if a.get("category") == "Research"]
        teaching_raw = [a for a in raw_activities if a.get("category") == "Teaching_Learning"]
        admin_raw = [a for a in raw_activities if a.get("category") == "Administrative"]

        cat_scores_data = api_data.get("category_scores", {})
        res_info = cat_scores_data.get("Research", {})
        tch_info = cat_scores_data.get("Teaching_Learning", {})
        adm_info = cat_scores_data.get("Administrative", {})

        category_summaries = {
            "research": {
                "collection_status": res_info.get("collection_status", "COLLECTED"),
                "status": res_info.get("status", "VERIFIED"),
                "is_collected": res_info.get("is_collected", True),
                "is_verified_zero": res_info.get("is_verified_zero", False),
                "claimed_count": len(research_raw),
                "claimed_points": res_info.get("raw_claimed_points"),
                "verified_points": res_info.get("verified_points"),
                "claimed_score": res_info.get("raw_weighted_score"),
                "verified_score": res_info.get("verified_weighted_score"),
                "notes": res_info.get("notes", ""),
            },
            "teaching_learning": {
                "collection_status": tch_info.get("collection_status", "COLLECTED"),
                "status": tch_info.get("status", "VERIFIED"),
                "is_collected": tch_info.get("is_collected", True),
                "is_verified_zero": tch_info.get("is_verified_zero", False),
                "claimed_count": len(teaching_raw),
                "claimed_points": tch_info.get("raw_claimed_points"),
                "verified_points": tch_info.get("verified_points"),
                "claimed_score": tch_info.get("raw_weighted_score"),
                "verified_score": tch_info.get("verified_weighted_score"),
                "notes": tch_info.get("notes", ""),
            },
            "administrative": {
                "collection_status": adm_info.get("collection_status", "COLLECTED"),
                "status": adm_info.get("status", "VERIFIED"),
                "is_collected": adm_info.get("is_collected", True),
                "is_verified_zero": adm_info.get("is_verified_zero", False),
                "claimed_count": len(admin_raw),
                "claimed_points": adm_info.get("raw_claimed_points"),
                "verified_points": adm_info.get("verified_points"),
                "claimed_score": adm_info.get("raw_weighted_score"),
                "verified_score": adm_info.get("verified_weighted_score"),
                "notes": adm_info.get("notes", ""),
            },
        }

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
                "score_status": api_data.get("score_status", "PROVISIONAL"),
                "score_type": api_data.get("score_type", "FINAL"),
                "score_label": api_data.get("score_label", ""),
                "is_consent_limited": api_data.get("is_consent_limited", False),
                "skipped_categories": api_data.get("skipped_categories", []),
            },
            "category_summaries": category_summaries,
            "category_breakdown": api_data.get("category_scores", {}),
            "evidence_exceptions": state.evidence_exceptions,
            "verified_activities": verified_activities,
            "raw_activities_count": len(raw_activities),
            "swarm_results_summary": {
                role: {
                    "status": res.get("status"),
                    "duration_ms": res.get("duration_ms"),
                    "activities_count": len(res.get("activities", [])),
                }
                for role, res in (state.swarm_results or {}).items()
            },
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
