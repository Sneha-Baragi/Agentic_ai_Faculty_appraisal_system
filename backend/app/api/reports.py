from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_faculty_profile
from app.models import FacultyProfile
from app.services.appraisals import latest_report
from app.services.cycles import get_or_create_run, get_open_cycle

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/current")
def current_report(
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    cycle = get_open_cycle(db)
    if cycle is None:
        raise HTTPException(status_code=404, detail="No open appraisal cycle")
    run = get_or_create_run(db, faculty=profile, cycle=cycle)
    report = latest_report(db, run_id=run.id)
    if report is None:
        raise HTTPException(status_code=404, detail="No report generated yet")
    return {
        "id": str(report.id),
        "version_number": report.version_number,
        "status": report.status,
        "rating_recommendation": report.rating_recommendation,
        "html": report.summary_md,
        "json": report.report_json,
        "disclaimer": (report.report_json or {}).get("disclaimer") or "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC",
        "approval_status": (report.report_json or {}).get("approval_status"),
        "approval": (report.report_json or {}).get("approval"),
    }
