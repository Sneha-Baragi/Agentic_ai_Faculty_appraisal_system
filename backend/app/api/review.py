import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.graph import checkpointed_graph
from app.api.deps import get_db, require_roles
from app.models import ApprovalDecision, AppraisalReport, AppraisalScore, AuditLog, Evidence, FacultyActivity, FacultyAppraisalRun, FacultyProfile, User
from app.services.activities import activity_to_dict
from app.services.appraisals import latest_report, latest_score
from app.services.cycles import get_open_cycle
from app.services.evidence import evidence_to_dict
from app.services.reports import update_report_approval

router = APIRouter(prefix="/api/v1/review", tags=["review"])
REVIEWER = require_roles("hod", "dean", "iqac", "committee", "admin")


class ApprovalRequest(BaseModel):
    reason: str | None = None
    comment: str | None = None


class ReportEditRequest(BaseModel):
    summary_md: str | None = None
    rating_recommendation: str | None = None
    comment: str | None = None


class ReportOverrideRequest(BaseModel):
    reason: str
    rating_recommendation: str | None = None
    total_score: float | None = None
    category_scores: dict[str, float] | None = None


class RollbackRequest(BaseModel):
    version_id: str
    reason: str


def _review_run(db: Session, faculty_id: str) -> tuple[FacultyAppraisalRun, AppraisalReport]:
    cycle = get_open_cycle(db)
    if cycle is None:
        raise HTTPException(status_code=404, detail="No open appraisal cycle")
    run = db.scalar(select(FacultyAppraisalRun).where(FacultyAppraisalRun.faculty_id == faculty_id, FacultyAppraisalRun.cycle_id == cycle.id))
    if run is None or run.current_version_id is None:
        raise HTTPException(status_code=404, detail="Appraisal not found")
    report = db.get(AppraisalReport, run.current_version_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Appraisal report not found")
    return run, report


def _new_report_version(db: Session, run: FacultyAppraisalRun, report: AppraisalReport, *, action: str, reviewer: User, reason: str | None = None, changes: dict | None = None) -> AppraisalReport:
    if report.status == "published":
        raise HTTPException(status_code=409, detail="Published report versions are immutable")
    payload = deepcopy(report.report_json or {})
    if changes:
        payload.update(changes)
    if "rating_recommendation" in changes:
        payload.setdefault("score", {})["rating"] = changes["rating_recommendation"]
    payload["approval_status"] = "awaiting_review"
    payload["approval"] = {}
    version = AppraisalReport(
        run_id=run.id,
        version_number=(run.attempt_count or 0) + 1,
        parent_version_id=report.id,
        score_id=report.score_id,
        summary_md=payload.get("summary_md", report.summary_md),
        report_json=payload,
        rating_recommendation=payload.get("score", {}).get("rating", report.rating_recommendation),
        status="generated",
        content_hash=hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest(),
    )
    db.add(version)
    db.flush()
    before = {"version_id": str(report.id), "version_number": report.version_number, "approval_status": _approval_status(run)}
    run.current_version_id = version.id
    run.attempt_count = version.version_number
    run.approval_status = "awaiting_review"
    run.reviewer_id = None
    run.approved_at = None
    run.rejection_reason = None
    run.change_request_reason = None
    run.approval_comment = None
    db.add(ApprovalDecision(report_id=version.id, reviewer_id=reviewer.id, action=action, comments=reason))
    db.add(AuditLog(actor_id=reviewer.id, action=f"report_{action}", entity_type="appraisal_report", entity_id=str(version.id), before=before, after={"version_number": version.version_number, "parent_version_id": str(report.id), "reason": reason}))
    return version


@router.get("/faculty/{faculty_id}/reports/history")
def report_history(faculty_id: str, db: Session = Depends(get_db), _user: User = Depends(REVIEWER)) -> list[dict]:
    run, _ = _review_run(db, faculty_id)
    reports = db.scalars(select(AppraisalReport).where(AppraisalReport.run_id == run.id).order_by(AppraisalReport.version_number.desc())).all()
    return [{"id": str(item.id), "version_number": item.version_number, "status": item.status, "rating_recommendation": item.rating_recommendation, "is_current": item.id == run.current_version_id, "published_at": item.published_at.isoformat() if item.published_at else None} for item in reports]


@router.patch("/faculty/{faculty_id}/report/edit")
def edit_report(faculty_id: str, request: ReportEditRequest, db: Session = Depends(get_db), reviewer: User = Depends(REVIEWER)) -> dict:
    run, report = _review_run(db, faculty_id)
    changes = {key: value for key, value in {"summary_md": request.summary_md, "rating_recommendation": request.rating_recommendation}.items() if value is not None}
    if not changes:
        raise HTTPException(status_code=422, detail="At least one report field is required")
    version = _new_report_version(db, run, report, action="edit", reviewer=reviewer, reason=request.comment, changes=changes)
    db.commit()
    return {"id": str(version.id), "version_number": version.version_number, "approval_status": run.approval_status}


@router.post("/faculty/{faculty_id}/report/override")
def override_report(faculty_id: str, request: ReportOverrideRequest, db: Session = Depends(get_db), reviewer: User = Depends(REVIEWER)) -> dict:
    if not request.reason.strip():
        raise HTTPException(status_code=422, detail="Override reason is required")
    run, report = _review_run(db, faculty_id)
    score = deepcopy((report.report_json or {}).get("score", {}))
    if request.total_score is not None:
        score["total"] = request.total_score
    if request.category_scores is not None:
        score["breakdown"] = request.category_scores
    if request.rating_recommendation is not None:
        score["rating"] = request.rating_recommendation
    version = _new_report_version(db, run, report, action="override", reviewer=reviewer, reason=request.reason, changes={"score": score})
    db.commit()
    return {"id": str(version.id), "version_number": version.version_number, "approval_status": run.approval_status}


@router.post("/faculty/{faculty_id}/report/rollback")
def rollback_report(faculty_id: str, request: RollbackRequest, db: Session = Depends(get_db), reviewer: User = Depends(REVIEWER)) -> dict:
    if not request.reason.strip():
        raise HTTPException(status_code=422, detail="Rollback reason is required")
    run, current = _review_run(db, faculty_id)
    target = db.scalar(select(AppraisalReport).where(AppraisalReport.id == request.version_id, AppraisalReport.run_id == run.id))
    if target is None:
        raise HTTPException(status_code=404, detail="Report version not found")
    version = _new_report_version(db, run, current, action="rollback", reviewer=reviewer, reason=request.reason, changes=deepcopy(target.report_json or {}))
    db.commit()
    return {"id": str(version.id), "version_number": version.version_number, "rolled_back_to": str(target.id), "approval_status": run.approval_status}


@router.post("/faculty/{faculty_id}/report/publish")
def publish_report(faculty_id: str, db: Session = Depends(get_db), reviewer: User = Depends(REVIEWER)) -> dict:
    run, report = _review_run(db, faculty_id)
    if report.status == "published":
        return {"id": str(report.id), "version_number": report.version_number, "status": "published", "message": "Report is already published"}
    if _approval_status(run) != "approved":
        raise HTTPException(status_code=409, detail="Only an approved version may be published")
    published_at = datetime.now(timezone.utc)
    report.status = "published"
    report.published_by = reviewer.id
    report.published_at = published_at
    db.add(AuditLog(actor_id=reviewer.id, action="report_publish", entity_type="appraisal_report", entity_id=str(report.id), before={"status": "approved"}, after={"status": "published", "version_number": report.version_number}))
    db.commit()
    return {"id": str(report.id), "version_number": report.version_number, "status": report.status, "published_at": published_at.isoformat()}


def _approval_status(run: FacultyAppraisalRun) -> str:
    return run.approval_status if run.approval_status != "not_generated" else run.status


# def _decide(db: Session, *, faculty_id: str, action: str, request: ApprovalRequest, reviewer: User) -> dict:
#     cycle = get_open_cycle(db)
#     if cycle is None:
#         raise HTTPException(status_code=404, detail="No open appraisal cycle")
#     profile = db.scalar(select(FacultyProfile).where(FacultyProfile.id == faculty_id))
#     if profile is None:
#         raise HTTPException(status_code=404, detail="Faculty not found")
#     run = db.scalar(select(FacultyAppraisalRun).where(FacultyAppraisalRun.faculty_id == profile.id, FacultyAppraisalRun.cycle_id == cycle.id))
#     if run is None:
#         raise HTTPException(status_code=404, detail="Appraisal not found")
#     current = _approval_status(run)
#     if action == "approve" and current == "approved":
#         return {"status": current, "message": "Appraisal is already approved"}
#     if current != "awaiting_review":
#         raise HTTPException(status_code=409, detail=f"Cannot {action} appraisal from status '{current}'")
#     if action in {"reject", "request_changes"} and not (request.reason or "").strip():
#         raise HTTPException(status_code=422, detail="A reason is required")
#     report = latest_report(db, run_id=run.id)
#     if report is None:
#         raise HTTPException(status_code=409, detail="Appraisal report not found")
#     decided_at = datetime.now(timezone.utc)
#     status_value = {"approve": "approved", "reject": "rejected", "request_changes": "changes_requested"}[action]
#     reason = request.reason.strip() if request.reason else None
#     comment = request.comment.strip() if request.comment else None
#     run.approval_status = status_value
#     run.reviewer_id = reviewer.id
#     run.approved_at = decided_at
#     run.rejection_reason = reason if action == "reject" else None
#     run.change_request_reason = reason if action == "request_changes" else None
#     run.approval_comment = comment
#     run.updated_at = decided_at
#     update_report_approval(report, status=status_value, reviewer=reviewer.email, decided_at=decided_at, reason=reason, comment=comment)
#     db.add(ApprovalDecision(report_id=report.id, reviewer_id=reviewer.id, action=action, comments=reason or comment))
#     db.add(AuditLog(actor_id=reviewer.id, action=f"appraisal_{action}", entity_type="faculty_appraisal_run", entity_id=str(run.id), before={"approval_status": current}, after={"approval_status": status_value, "report_id": str(report.id), "comment": reason or comment}))
#     db.commit()
#     return {"status": status_value, "message": f"Appraisal {status_value}", "reviewer": reviewer.email, "decided_at": decided_at.isoformat(), "reason": reason, "comment": comment}

def _decide(
    db: Session,
    *,
    faculty_id: str,
    action: str,
    request: ApprovalRequest,
    reviewer: User,
) -> dict:
    cycle = get_open_cycle(db)

    if cycle is None:
        raise HTTPException(
            status_code=404,
            detail="No open appraisal cycle",
        )

    profile = db.scalar(
        select(FacultyProfile).where(
            FacultyProfile.id == faculty_id
        )
    )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Faculty not found",
        )

    run = db.scalar(
        select(FacultyAppraisalRun).where(
            FacultyAppraisalRun.faculty_id == profile.id,
            FacultyAppraisalRun.cycle_id == cycle.id,
        )
    )

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Appraisal not found",
        )

    current = _approval_status(run)

    if action not in {
        "approve",
        "reject",
        "request_changes",
    }:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid governance action: {action}",
        )

    if action == "approve" and current == "approved":
        return {
            "status": current,
            "message": "Appraisal is already approved",
        }

    if current != "awaiting_review":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot {action} appraisal "
                f"from status '{current}'"
            ),
        )

    if not run.graph_thread_id:
        raise HTTPException(
            status_code=409,
            detail="Appraisal has no LangGraph thread ID",
        )

    if action in {"reject", "request_changes"} and not (
        request.reason or ""
    ).strip():
        raise HTTPException(
            status_code=422,
            detail="A reason is required",
        )

    report = latest_report(
        db,
        run_id=run.id,
    )

    if report is None:
        raise HTTPException(
            status_code=409,
            detail="Appraisal report not found",
        )

    reason = (
        request.reason.strip()
        if request.reason
        else None
    )

    comment = (
        request.comment.strip()
        if request.comment
        else None
    )

    # ---------------------------------------------------------
    # Phase 5C / Lab 3:
    # Resume the SAME interrupted LangGraph thread.
    #
    # The authenticated reviewer identity is NOT taken from
    # client input. The graph only receives the governance
    # action and reason.
    # ---------------------------------------------------------

    try:
        resumed_state = checkpointed_graph.invoke(
            Command(
                resume={
                    "action": action,
                    "reason": reason,
                }
            ),
            config={
                "configurable": {
                    "thread_id": run.graph_thread_id,
                }
            },
        )
    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "Unable to resume the appraisal workflow: "
                f"{exc}"
            ),
        ) from exc

    approval = resumed_state.get("approval") or {}

    resumed_action = approval.get("action")

    if resumed_action != action:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "LangGraph governance action did not match "
                "the requested action"
            ),
        )

    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "request_changes": "changes_requested",
    }

    status_value = status_map[action]

    graph_status = approval.get("status")

    if graph_status != status_value:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "LangGraph returned an unexpected governance "
                f"status: {graph_status}"
            ),
        )

    decided_at = datetime.now(timezone.utc)

    # ---------------------------------------------------------
    # Synchronize the durable database governance state with
    # the completed LangGraph governance decision.
    # ---------------------------------------------------------

    run.approval_status = status_value
    run.reviewer_id = reviewer.id
    run.approved_at = decided_at
    run.rejection_reason = (
        reason if action == "reject" else None
    )
    run.change_request_reason = (
        reason if action == "request_changes" else None
    )
    run.approval_comment = comment
    run.updated_at = decided_at

    update_report_approval(
        report,
        status=status_value,
        reviewer=reviewer.email,
        decided_at=decided_at,
        reason=reason,
        comment=comment,
    )

    db.add(
        ApprovalDecision(
            report_id=report.id,
            reviewer_id=reviewer.id,
            action=action,
            comments=reason or comment,
        )
    )

    db.add(
        AuditLog(
            actor_id=reviewer.id,
            action=f"appraisal_{action}",
            entity_type="faculty_appraisal_run",
            entity_id=str(run.id),
            before={
                "approval_status": current,
            },
            after={
                "approval_status": status_value,
                "report_id": str(report.id),
                "comment": reason or comment,
                "graph_thread_id": run.graph_thread_id,
            },
        )
    )

    db.commit()

    return {
        "status": status_value,
        "message": f"Appraisal {status_value}",
        "reviewer": reviewer.email,
        "decided_at": decided_at.isoformat(),
        "reason": reason,
        "comment": comment,
        "graph": {
            "resumed": True,
            "thread_id": run.graph_thread_id,
            "action": action,
        },
    }

@router.post("/faculty/{faculty_id}/approve")
def approve_appraisal(faculty_id: str, request: ApprovalRequest | None = None, db: Session = Depends(get_db), reviewer: User = Depends(REVIEWER)) -> dict:
    return _decide(db, faculty_id=faculty_id, action="approve", request=request or ApprovalRequest(), reviewer=reviewer)


@router.post("/faculty/{faculty_id}/reject")
def reject_appraisal(faculty_id: str, request: ApprovalRequest, db: Session = Depends(get_db), reviewer: User = Depends(REVIEWER)) -> dict:
    return _decide(db, faculty_id=faculty_id, action="reject", request=request, reviewer=reviewer)


@router.post("/faculty/{faculty_id}/request-changes")
def request_appraisal_changes(faculty_id: str, request: ApprovalRequest, db: Session = Depends(get_db), reviewer: User = Depends(REVIEWER)) -> dict:
    return _decide(db, faculty_id=faculty_id, action="request_changes", request=request, reviewer=reviewer)


@router.get("/faculty")
def list_faculty(db: Session = Depends(get_db), _user: User = Depends(REVIEWER)) -> list[dict]:
    rows = list(db.scalars(select(FacultyProfile).options(selectinload(FacultyProfile.user))))
    cycle = get_open_cycle(db)
    out = []
    for profile in rows:
        score = latest_score(db, faculty_id=profile.id, cycle_id=cycle.id) if cycle else None
        out.append(
            {
                "id": str(profile.id),
                "full_name": profile.full_name,
                "employee_code": profile.employee_code,
                "department": profile.department,
                "designation": profile.designation,
                "email": profile.user.email if profile.user else None,
                "has_score": score is not None,
                "total_score": score.total if score else None,
            }
        )
    return out


@router.get("/faculty/{faculty_id}")
def faculty_packet(faculty_id: str, db: Session = Depends(get_db), _user: User = Depends(REVIEWER)) -> dict:
    profile = db.scalar(select(FacultyProfile).options(selectinload(FacultyProfile.user)).where(FacultyProfile.id == faculty_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Faculty not found")
    cycle = get_open_cycle(db)
    activities = list(
        db.scalars(
            select(FacultyActivity)
            .options(selectinload(FacultyActivity.evidence), selectinload(FacultyActivity.teaching))
            .where(FacultyActivity.faculty_id == profile.id)
        )
    )
    evidence = list(db.scalars(select(Evidence).where(Evidence.faculty_id == profile.id)))
    score = latest_score(db, faculty_id=profile.id, cycle_id=cycle.id) if cycle else None
    report = None
    run = None
    reviewer = None
    if score is not None:
        report = latest_report(db, run_id=score.run_id)
        run = db.scalar(
            select(FacultyAppraisalRun).where(FacultyAppraisalRun.id == score.run_id)
        )
        reviewer = db.get(User, run.reviewer_id) if run and run.reviewer_id else None
    return {
        "profile": {
            "id": str(profile.id),
            "full_name": profile.full_name,
            "employee_code": profile.employee_code,
            "department": profile.department,
            "designation": profile.designation,
            "institution": profile.institution,
            "email": profile.user.email if profile.user else None,
        },
        "cycle": {"id": str(cycle.id), "name": cycle.name, "status": cycle.status, "academic_year": cycle.academic_year, "start_date": cycle.starts_on.isoformat() if cycle.starts_on else None, "end_date": cycle.ends_on.isoformat() if cycle.ends_on else None} if cycle else None,
        "activities": [activity_to_dict(item) for item in activities],
        "evidence": [evidence_to_dict(item) for item in evidence],
        "score": {
            "total_score": score.total,
            "score_breakdown": score.breakdown,
            "scoring_engine_version": score.engine_version,
            "disclaimer": "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC",
        }
        if score
        else None,
        "report": {"version_number": report.version_number, "rating_recommendation": report.rating_recommendation, "html": report.summary_md, "json": report.report_json, "status": report.status} if report else None,
        "report_history": [
            {"id": str(item.id), "version_number": item.version_number, "status": item.status, "rating_recommendation": item.rating_recommendation, "is_current": item.id == run.current_version_id}
            for item in db.scalars(select(AppraisalReport).where(AppraisalReport.run_id == run.id).order_by(AppraisalReport.version_number.desc())).all()
        ] if run else [],
        "appraisal": {
            "status": run.status if run else "not_generated",
            "approval_status": _approval_status(run) if run else "not_generated",
            "reviewer_id": str(run.reviewer_id) if run and run.reviewer_id else None,
            "reviewer_email": reviewer.email if reviewer else None,
            "approved_at": run.approved_at.isoformat() if run and run.approved_at else None,
            "rejection_reason": run.rejection_reason if run else None,
            "change_request_reason": run.change_request_reason if run else None,
            "approval_comment": run.approval_comment if run else None,
        } if run else {"status": "not_generated", "approval_status": "not_generated"},
    }
