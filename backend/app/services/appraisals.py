# from __future__ import annotations

# import hashlib
# import json
# from datetime import datetime, timezone

# from sqlalchemy import select
# from sqlalchemy.orm import Session, selectinload

# from app.agents.graph import compiled_graph
# from app.models import AppraisalReport, AppraisalScore, FacultyActivity, FacultyProfile, Rubric
# from app.scoring.engine import ENGINE_VERSION, load_demo_rubric
# from app.services.activities import activity_to_dict
# from app.services.cycles import get_or_create_run, get_open_cycle
# from app.services.evidence import evidence_to_dict
# from app.services.reports import build_report


# def load_workflow_payload(db: Session, *, faculty: FacultyProfile) -> dict:
#     cycle = get_open_cycle(db)
#     if cycle is None:
#         raise ValueError("No open appraisal cycle")
#     run = get_or_create_run(db, faculty=faculty, cycle=cycle)
#     activities = list(
#         db.scalars(
#             select(FacultyActivity)
#             .options(
#                 selectinload(FacultyActivity.evidence),
#                 selectinload(FacultyActivity.teaching),
#             )
#             .where(FacultyActivity.faculty_id == faculty.id, FacultyActivity.cycle_id == cycle.id)
#         )
#     )
#     activity_dicts = [activity_to_dict(item) for item in activities]
#     evidence_dicts = [evidence_to_dict(ev) for act in activities for ev in act.evidence]
#     profile = {
#         "id": str(faculty.id),
#         "full_name": faculty.full_name,
#         "employee_code": faculty.employee_code,
#         "department": faculty.department,
#         "designation": faculty.designation,
#         "institution": faculty.institution,
#         "joining_date": faculty.joining_date.isoformat() if faculty.joining_date else None,
#         "email": faculty.user.email if faculty.user else None,
#     }
#     return {
#         "run": run,
#         "cycle": cycle,
#         "activities": activity_dicts,
#         "evidence": evidence_dicts,
#         "profile": profile,
#     }


# def run_appraisal(db: Session, *, faculty: FacultyProfile) -> dict:
#     payload = load_workflow_payload(db, faculty=faculty)
#     run = payload["run"]
#     cycle = payload["cycle"]
#     state = compiled_graph.invoke(
#         {
#             "run_id": str(run.id),
#             "faculty_id": str(faculty.id),
#             "cycle_id": str(cycle.id),
#             "rubric_id": "DEMO_RUBRIC_v1",
#             "attempt": run.attempt_count,
#             "max_attempts": 3,
#             "errors": [],
#             "audit_events": [],
#             "all_activities": payload["activities"],
#         }
#     )
#     score = state.get("score_result") or {}
#     report_draft = state.get("report_draft") or {}
#     rubric = db.scalar(select(Rubric).where(Rubric.is_demo.is_(True)))
#     if rubric is None:
#         from app.scoring.engine import load_demo_rubric
#         definition = load_demo_rubric()
#         rubric = Rubric(
#             name=definition.get("name", "DEMO/TEST Faculty Appraisal Rubric"),
#             version=str(definition.get("version", "1.0")),
#             is_demo=True,
#             effective_from=None,
#             json_definition=definition,
#             created_by=None,
#         )
#         db.add(rubric)
#         db.flush()
#     breakdown = {
#         "research_score": (score.get("category_totals") or {}).get("research", 0),
#         "teaching_score": (score.get("category_totals") or {}).get("teaching", 0),
#         "administrative_score": (score.get("category_totals") or {}).get("administrative", 0),
#         "total_score": score.get("total", 0),
#         "line_items": score.get("line_items", []),
#         "disclaimer": score.get("disclaimer") or load_demo_rubric().get("disclaimer"),
#     }
#     score_row = AppraisalScore(
#         run_id=run.id,
#         faculty_id=faculty.id,
#         cycle_id=cycle.id,
#         rubric_id=rubric.id,
#         total=float(score.get("total") or 0),
#         breakdown=breakdown,
#         activity_score_refs=score.get("line_items") or [],
#         engine_version=score.get("engine_version") or ENGINE_VERSION,
#         computed_at=datetime.now(timezone.utc),
#     )
#     db.add(score_row)
#     db.flush()
#     built = build_report(
#         profile=payload["profile"],
#         cycle={"id": str(cycle.id), "name": cycle.name, "academic_year": cycle.academic_year, "status": cycle.status},
#         activities=payload["activities"],
#         evidence=payload["evidence"],
#         score=score,
#     )
#     version = (run.attempt_count or 0) + 1
#     content_hash = hashlib.sha256(json.dumps(built["json"], sort_keys=True).encode()).hexdigest()
#     report = AppraisalReport(
#         run_id=run.id,
#         version_number=version,
#         score_id=score_row.id,
#         summary_md=built["html"],
#         report_json=built["json"],
#         rating_recommendation=str(score.get("rating_recommendation") or "D"),
#         status="generated",
#         content_hash=content_hash,
#     )
#     db.add(report)
#     db.flush()
#     run.attempt_count = version
#     run.current_version_id = report.id
#     run.status = "awaiting_review"
#     run.approval_status = "awaiting_review"
#     run.graph_thread_id = str(run.id)
#     return {
#         "score": score_row,
#         "report": report,
#         "graph": {
#             "next_action": state.get("next_action"),
#             "validation": state.get("validation_result"),
#             "validated_set": state.get("validated_set"),
#         },
#         "report_draft": report_draft,
#     }


# def latest_score(db: Session, *, faculty_id, cycle_id) -> AppraisalScore | None:
#     return db.scalar(
#         select(AppraisalScore)
#         .where(AppraisalScore.faculty_id == faculty_id, AppraisalScore.cycle_id == cycle_id)
#         .order_by(AppraisalScore.computed_at.desc())
#     )


# def latest_report(db: Session, *, run_id) -> AppraisalReport | None:
#     return db.scalar(
#         select(AppraisalReport)
#         .where(AppraisalReport.run_id == run_id)
#         .order_by(AppraisalReport.version_number.desc())
#     )

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.graph import checkpointed_graph
from app.core.config import get_settings
from app.models import (
    AppraisalReport,
    AppraisalScore,
    FacultyActivity,
    FacultyProfile,
    Rubric,
    AuditLog,
)
from app.scoring.engine import ENGINE_VERSION, load_demo_rubric
from app.services.activities import activity_to_dict
from app.services.cycles import get_or_create_run, get_open_cycle
from app.services.evidence import evidence_to_dict
from app.services.deep_research import run_deep_research_verification
from app.services.google_scholar import GoogleScholarError, GoogleScholarService
from app.services.memory import retrieve_faculty_memory
from app.services.reports import build_report
from app.services.runtime import AppraisalRuntime
from app.services.student_feedback import get_student_feedback_record


def load_workflow_payload(db: Session, *, faculty: FacultyProfile) -> dict:
    cycle = get_open_cycle(db)
    if cycle is None:
        raise ValueError("No open appraisal cycle")

    run = get_or_create_run(db, faculty=faculty, cycle=cycle)
    memory_context = retrieve_faculty_memory(
        db,
        faculty=faculty,
        current_cycle_id=cycle.id,
    )

    activities = list(
        db.scalars(
            select(FacultyActivity)
            .options(
                selectinload(FacultyActivity.evidence),
                selectinload(FacultyActivity.teaching),
            )
            .where(
                FacultyActivity.faculty_id == faculty.id,
                FacultyActivity.cycle_id == cycle.id,
            )
        )
    )

    activity_dicts = [activity_to_dict(item) for item in activities]
    evidence_dicts = [
        evidence_to_dict(ev)
        for act in activities
        for ev in act.evidence
    ]

    profile = {
        "id": str(faculty.id),
        "full_name": faculty.full_name,
        "employee_code": faculty.employee_code,
        "department": faculty.department,
        "designation": faculty.designation,
        "institution": faculty.institution,
        "joining_date": (
            faculty.joining_date.isoformat()
            if faculty.joining_date
            else None
        ),
        "email": faculty.user.email if faculty.user else None,
    }

    return {
        "run": run,
        "cycle": cycle,
        "activities": activity_dicts,
        "evidence": evidence_dicts,
        "profile": profile,
        "memory_context": memory_context,
    }


def run_appraisal(
    db: Session,
    *,
    faculty: FacultyProfile,
) -> dict:
    payload = load_workflow_payload(db, faculty=faculty)

    run = payload["run"]
    cycle = payload["cycle"]
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    research_metrics: dict = {
        "status": "unavailable",
        "provider": "serpapi_google_scholar_author",
        "scholar_id": faculty.google_scholar_id,
        "scholar_url": faculty.google_scholar_url,
        "attempted_at": retrieved_at,
        "metrics": None,
        "publications": [],
        "error_category": "missing_scholar_id",
        "human_review_required": True,
    }
    if faculty.google_scholar_id:
        try:
            scholar_data = GoogleScholarService(get_settings().serpapi_api_key).fetch_profile(
                faculty.google_scholar_id,
                scholar_url=faculty.google_scholar_url,
            )
            research_metrics = {
                "status": "retrieved",
                "provider": scholar_data["source"],
                "scholar_id": scholar_data["scholar_id"],
                "scholar_url": scholar_data["scholar_url"],
                "scholar_name": scholar_data["scholar_name"],
                "retrieved_at": scholar_data["retrieved_at"],
                "metrics": {
                    "total_citations": scholar_data["total_citations"],
                    "citations_since_2016": scholar_data["citations_since_2016"],
                    "h_index": scholar_data["h_index"],
                    "h_index_since_2016": scholar_data["h_index_since_2016"],
                    "i10_index": scholar_data["i10_index"],
                    "i10_index_since_2016": scholar_data["i10_index_since_2016"],
                },
                "publications": scholar_data["publications"],
                "human_review_required": False,
            }
        except GoogleScholarError as exc:
            research_metrics["error_category"] = exc.category
    db.add(
        AuditLog(
            actor_id=faculty.user_id,
            action=(
                "appraisal_research_metrics_success"
                if research_metrics["status"] == "retrieved"
                else "appraisal_research_metrics_failure"
            ),
            entity_type="faculty_profile",
            entity_id=str(faculty.id),
            before=None,
            after={
                "success": research_metrics["status"] == "retrieved",
                "provider": research_metrics["provider"],
                "scholar_id": faculty.google_scholar_id,
                "retrieved_at": research_metrics.get("retrieved_at")
                or research_metrics["attempted_at"],
                "error_category": research_metrics.get("error_category"),
            },
        )
    )

    # Use a stable LangGraph thread ID for this appraisal run.
    thread_id = run.graph_thread_id or str(run.id)
    run.graph_thread_id = thread_id

    runtime = AppraisalRuntime()
    runtime_context = runtime.create_context(
        faculty_id=str(faculty.id),
        cycle_id=str(cycle.id),
        run_id=str(run.id),
        thread_id=thread_id,
        execution_scope={
            "faculty_id": str(faculty.id),
            "cycle_id": str(cycle.id),
            "run_id": str(run.id),
            "allowed_scope": {
                "faculty_id": str(faculty.id),
                "cycle_id": str(cycle.id),
                "run_id": str(run.id),
            },
        },
        memory_context=payload.get("memory_context"),
        audit_context={"events": []},
    )

    feedback_data = get_student_feedback_record(faculty.full_name)
    db.add(
        AuditLog(
            actor_id=faculty.user_id,
            action=(
                "appraisal_student_feedback_matched"
                if feedback_data and feedback_data.get("status") == "matched"
                else "appraisal_student_feedback_unmatched"
            ),
            entity_type="faculty_profile",
            entity_id=str(faculty.id),
            before=None,
            after={
                "faculty_name": faculty.full_name,
                "status": feedback_data.get("status") if feedback_data else "missing",
                "feedback_percentage": (
                    feedback_data.get("feedback_percentage") if feedback_data else None
                ),
                "source_file": feedback_data.get("source_file") if feedback_data else None,
            },
        )
    )

    graph_input = {
        "run_id": str(run.id),
        "faculty_id": str(faculty.id),
        "faculty_name": faculty.full_name,
        "cycle_id": str(cycle.id),
        "rubric_id": "DEMO_RUBRIC_v1",
        "attempt": run.attempt_count,
        "max_attempts": 3,
        "errors": [],
        "audit_events": [],
        "all_activities": payload["activities"],
        "memory_context": payload["memory_context"],
        "research_metrics_status": research_metrics["status"],
        "research_metrics_issue": research_metrics.get("error_category"),
        "research_metrics": research_metrics,
        "configured_scholar_id": faculty.google_scholar_id,
        "cycle_academic_year": cycle.academic_year,
        "student_feedback": feedback_data,
    }

    runtime.record_start(
        runtime_context,
        source="run_appraisal",
        graph_thread_id=thread_id,
        state={"phase": "graph_start"},
    )

    # Phase 5C / Lab 3:
    # Execute the checkpointed graph with a stable thread ID.
    state = checkpointed_graph.invoke(
        graph_input,
        config={
            "configurable": {
                "thread_id": thread_id,
            }
        },
    )

    runtime_snapshot = runtime.snapshot(runtime_context, state)

    score = state.get("score_result") or {}
    report_draft = state.get("report_draft") or {}
    research_metrics = state.get("research_metrics") or research_metrics

    # The graph reaches interrupt() at human_gate().
    # At that point the score/report data has already been calculated,
    # but the graph is waiting for the human governance decision.

    rubric = db.scalar(
        select(Rubric).where(Rubric.is_demo.is_(True))
    )

    if rubric is None:
        definition = load_demo_rubric()

        rubric = Rubric(
            name=definition.get(
                "name",
                "DEMO/TEST Faculty Appraisal Rubric",
            ),
            version=str(definition.get("version", "1.0")),
            is_demo=True,
            effective_from=None,
            json_definition=definition,
            created_by=None,
        )

        db.add(rubric)
        db.flush()

    breakdown = {
        "research_score": (
            score.get("category_totals") or {}
        ).get("research", 0),
        "teaching_score": (
            score.get("category_totals") or {}
        ).get("teaching", 0),
        "administrative_score": (
            score.get("category_totals") or {}
        ).get("administrative", 0),
        "total_score": score.get("total", 0),
        "line_items": score.get("line_items", []),
        "category_raw_totals": score.get("category_raw_totals", {}),
        "category_weights": score.get("category_weights") or {
            name: float(spec.get("weight", 0.0))
            for name, spec in load_demo_rubric()["categories"].items()
        },
        "disclaimer": (
            score.get("disclaimer")
            or load_demo_rubric().get("disclaimer")
        ),
    }

    score_row = AppraisalScore(
        run_id=run.id,
        faculty_id=faculty.id,
        cycle_id=cycle.id,
        rubric_id=rubric.id,
        total=float(score.get("total") or 0),
        breakdown=breakdown,
        activity_score_refs=score.get("line_items") or [],
        engine_version=score.get("engine_version") or ENGINE_VERSION,
        computed_at=datetime.now(timezone.utc),
    )

    db.add(score_row)
    db.flush()

    deep_research_verification = run_deep_research_verification(
        activities=payload["activities"],
        evidence=payload["evidence"],
        research_metrics=research_metrics,
    )

    db.add(
        AuditLog(
            actor_id=faculty.user_id,
            action="appraisal_deep_research_verification",
            entity_type="faculty_profile",
            entity_id=str(faculty.id),
            before=None,
            after={
                "analyzed_claims": deep_research_verification["total_claims_analyzed"],
                "verified_count": deep_research_verification["verified_count"],
                "discrepant_count": deep_research_verification["discrepant_count"],
                "unverified_count": deep_research_verification["unverified_count"],
            },
        )
    )

    built = build_report(
        profile=payload["profile"],
        cycle={
            "id": str(cycle.id),
            "name": cycle.name,
            "academic_year": cycle.academic_year,
            "status": cycle.status,
        },
        activities=payload["activities"],
        evidence=payload["evidence"],
        score=score,
        research_metrics=research_metrics,
        deep_research_verification=deep_research_verification,
        student_feedback=state.get("student_feedback") or feedback_data,
        memory_context=payload.get("memory_context"),
    )

    version = (run.attempt_count or 0) + 1

    content_hash = hashlib.sha256(
        json.dumps(
            built["json"],
            sort_keys=True,
        ).encode()
    ).hexdigest()

    report = AppraisalReport(
        run_id=run.id,
        version_number=version,
        score_id=score_row.id,
        summary_md=built["html"],
        report_json=built["json"],
        rating_recommendation=str(
            score.get("rating_recommendation") or "D"
        ),
        status="generated",
        content_hash=content_hash,
    )

    db.add(report)
    db.flush()

    run.attempt_count = version
    run.current_version_id = report.id

    # The graph is now paused at the governance gate.
    run.status = "awaiting_review"
    run.approval_status = "awaiting_review"
    run.updated_at = datetime.now(timezone.utc)

    db.flush()

    return {
        "score": score_row,
        "report": report,
        "graph": {
            "next_action": state.get("next_action"),
            "validation": state.get("validation_result"),
            "validated_set": state.get("validated_set"),
            "thread_id": thread_id,
            "awaiting_human": True,
        },
        "report_draft": report_draft,
        "runtime_snapshot": runtime_snapshot,
    }


def latest_score(
    db: Session,
    *,
    faculty_id,
    cycle_id,
) -> AppraisalScore | None:
    return db.scalar(
        select(AppraisalScore)
        .where(
            AppraisalScore.faculty_id == faculty_id,
            AppraisalScore.cycle_id == cycle_id,
        )
        .order_by(AppraisalScore.computed_at.desc())
    )


def latest_report(
    db: Session,
    *,
    run_id,
) -> AppraisalReport | None:
    return db.scalar(
        select(AppraisalReport)
        .where(AppraisalReport.run_id == run_id)
        .order_by(AppraisalReport.version_number.desc())
    )