from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppraisalCycle, FacultyAppraisalRun, FacultyProfile


def get_open_cycle(db: Session) -> AppraisalCycle | None:
    return db.scalar(
        select(AppraisalCycle)
        .where(AppraisalCycle.status == "open")
        .order_by(AppraisalCycle.starts_on.desc())
    )


def get_or_create_run(db: Session, *, faculty: FacultyProfile, cycle: AppraisalCycle) -> FacultyAppraisalRun:
    run = db.scalar(
        select(FacultyAppraisalRun).where(
            FacultyAppraisalRun.faculty_id == faculty.id,
            FacultyAppraisalRun.cycle_id == cycle.id,
        )
    )
    if run is None:
        run = FacultyAppraisalRun(faculty_id=faculty.id, cycle_id=cycle.id, status="collecting")
        db.add(run)
        db.flush()
    return run


def cycle_to_dict(cycle: AppraisalCycle) -> dict:
    return {
        "id": str(cycle.id),
        "name": cycle.name,
        "academic_year": cycle.academic_year,
        "start_date": cycle.starts_on.isoformat() if cycle.starts_on else None,
        "end_date": cycle.ends_on.isoformat() if cycle.ends_on else None,
        "status": cycle.status,
        "created_at": cycle.created_at.isoformat() if cycle.created_at else None,
        "updated_at": cycle.updated_at.isoformat() if cycle.updated_at else None,
    }


def touch_cycle(cycle: AppraisalCycle) -> None:
    cycle.updated_at = datetime.utcnow()


def new_cycle(*, name: str, academic_year: str, start_date: date, end_date: date, status: str) -> AppraisalCycle:
    return AppraisalCycle(
        name=name,
        academic_year=academic_year,
        starts_on=start_date,
        ends_on=end_date,
        status=status,
    )
