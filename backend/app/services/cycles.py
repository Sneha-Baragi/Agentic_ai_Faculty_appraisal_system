from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppraisalCycle, AuditLog, FacultyAppraisalRun, FacultyProfile, User
from app.services.constants import CYCLE_STATUSES


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


def create_cycle_service(
    db: Session,
    *,
    actor: User,
    name: str,
    academic_year: str,
    start_date: date,
    end_date: date,
    status: str,
) -> AppraisalCycle:
    if status not in CYCLE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid cycle status")

    existing_open: AppraisalCycle | None = None
    if status == "open":
        existing_open = get_open_cycle(db)

    cycle = new_cycle(
        name=name,
        academic_year=academic_year,
        start_date=start_date,
        end_date=end_date,
        status=status,
    )
    db.add(cycle)
    db.flush()

    if existing_open is not None and existing_open.id != cycle.id:
        prev_status = existing_open.status
        existing_open.status = "closed"
        touch_cycle(existing_open)
        db.add(
            AuditLog(
                actor_id=actor.id,
                action="cycle_closed",
                entity_type="appraisal_cycle",
                entity_id=str(existing_open.id),
                before={"status": prev_status},
                after={"status": "closed", "superseded_by": str(cycle.id)},
            )
        )

    db.add(
        AuditLog(
            actor_id=actor.id,
            action="cycle_created",
            entity_type="appraisal_cycle",
            entity_id=str(cycle.id),
            before=None,
            after={
                "name": cycle.name,
                "academic_year": cycle.academic_year,
                "status": cycle.status,
                "starts_on": cycle.starts_on.isoformat() if cycle.starts_on else None,
                "ends_on": cycle.ends_on.isoformat() if cycle.ends_on else None,
            },
        )
    )
    db.commit()
    db.refresh(cycle)
    return cycle


def open_cycle_service(
    db: Session,
    *,
    actor: User,
    cycle_id: str,
) -> AppraisalCycle:
    cycle = db.scalar(select(AppraisalCycle).where(AppraisalCycle.id == cycle_id))
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")
    prev_status = cycle.status
    if prev_status == "open":
        return cycle

    existing = get_open_cycle(db)
    if existing is not None and existing.id != cycle.id:
        existing_prev = existing.status
        existing.status = "closed"
        touch_cycle(existing)
        db.add(
            AuditLog(
                actor_id=actor.id,
                action="cycle_closed",
                entity_type="appraisal_cycle",
                entity_id=str(existing.id),
                before={"status": existing_prev},
                after={"status": "closed", "superseded_by": str(cycle.id)},
            )
        )

    cycle.status = "open"
    touch_cycle(cycle)
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="cycle_opened",
            entity_type="appraisal_cycle",
            entity_id=str(cycle.id),
            before={"status": prev_status},
            after={"status": "open"},
        )
    )
    db.commit()
    db.refresh(cycle)
    return cycle


def close_cycle_service(
    db: Session,
    *,
    actor: User,
    cycle_id: str,
) -> AppraisalCycle:
    cycle = db.scalar(select(AppraisalCycle).where(AppraisalCycle.id == cycle_id))
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")
    prev_status = cycle.status
    if prev_status == "closed":
        return cycle

    cycle.status = "closed"
    touch_cycle(cycle)
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="cycle_closed",
            entity_type="appraisal_cycle",
            entity_id=str(cycle.id),
            before={"status": prev_status},
            after={"status": "closed"},
        )
    )
    db.commit()
    db.refresh(cycle)
    return cycle
