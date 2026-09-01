from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_faculty_profile
from app.models import AuditLog, FacultyProfile, User
from app.services.appraisals import latest_report, latest_score, load_workflow_payload, run_appraisal
from app.services.cycles import get_or_create_run, get_open_cycle

router = APIRouter(prefix="/api/v1/appraisals", tags=["appraisals"])


def _score_out(score) -> dict:
    breakdown = score.breakdown or {}
    return {
        "id": str(score.id),
        "faculty_id": str(score.faculty_id) if score.faculty_id else None,
        "appraisal_cycle_id": str(score.cycle_id) if score.cycle_id else None,
        "total_score": score.total,
        "research_score": breakdown.get("research_score"),
        "teaching_score": breakdown.get("teaching_score"),
        "administrative_score": breakdown.get("administrative_score"),
        "score_breakdown": breakdown,
        "scoring_engine_version": score.engine_version,
        "generated_at": score.computed_at.isoformat() if score.computed_at else None,
        "disclaimer": breakdown.get("disclaimer") or "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC",
    }


@router.post("/run")
def compute_appraisal(
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    profile = db.merge(profile)
    if profile.user is None:
        db.refresh(profile)
    try:
        result = run_appraisal(db, faculty=profile)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "score": _score_out(result["score"]),
        "report_id": str(result["report"].id),
        "graph": result["graph"],
        "approval_status": "awaiting_review",
    }


@router.get("/current")
def current_appraisal(
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    cycle = get_open_cycle(db)
    if cycle is None:
        raise HTTPException(status_code=404, detail="No open appraisal cycle")
    score = latest_score(db, faculty_id=profile.id, cycle_id=cycle.id)
    if score is None:
        return {"score": None, "approval_status": "not_generated"}
    run = get_or_create_run(db, faculty=profile, cycle=cycle)
    return {
        "score": _score_out(score),
        "approval_status": run.approval_status if run.approval_status != "not_generated" else run.status,
    }


@router.post("/resubmit")
def resubmit_appraisal(
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    cycle = get_open_cycle(db)
    if cycle is None:
        raise HTTPException(status_code=404, detail="No open appraisal cycle")
    run = get_or_create_run(db, faculty=profile, cycle=cycle)
    if run.approval_status != "changes_requested":
        raise HTTPException(status_code=409, detail="Only appraisals with requested changes can be resubmitted")
    previous = run.approval_status
    run.approval_status = "awaiting_review"
    run.reviewer_id = None
    run.approved_at = None
    run.change_request_reason = None
    run.approval_comment = None
    db.add(AuditLog(actor_id=profile.user_id, action="appraisal_resubmit", entity_type="faculty_appraisal_run", entity_id=str(run.id), before={"approval_status": previous}, after={"approval_status": run.approval_status}))
    db.commit()
    return {"approval_status": run.approval_status, "message": "Appraisal resubmitted for HOD review", "resubmitted_at": datetime.now(timezone.utc).isoformat()}
