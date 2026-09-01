from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_roles
from app.core.config import get_settings
from app.models import AppraisalCycle, FacultyProfile, User
from app.schemas.appraisal import CycleCreate
from app.services.constants import CYCLE_STATUSES
from app.services.cycles import cycle_to_dict, get_open_cycle, new_cycle, touch_cycle

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
ADMIN = require_roles("admin")


@router.get("/users")
def list_users(db: Session = Depends(get_db), _admin: User = Depends(ADMIN)) -> list[dict]:
    rows = list(db.scalars(select(User).options(selectinload(User.roles))))
    return [
        {
            "id": str(user.id),
            "email": user.email,
            "is_active": user.is_active,
            "roles": [role.name for role in user.roles],
        }
        for user in rows
    ]


@router.get("/cycles")
def list_cycles(db: Session = Depends(get_db), _admin: User = Depends(ADMIN)) -> list[dict]:
    rows = list(db.scalars(select(AppraisalCycle).order_by(AppraisalCycle.starts_on.desc())))
    return [cycle_to_dict(row) for row in rows]


@router.post("/cycles")
def create_cycle(
    body: CycleCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(ADMIN),
) -> dict:
    if body.status not in CYCLE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid cycle status")
    if body.status == "open":
        existing = get_open_cycle(db)
        if existing is not None:
            existing.status = "closed"
            touch_cycle(existing)
    cycle = new_cycle(
        name=body.name,
        academic_year=body.academic_year,
        start_date=body.start_date,
        end_date=body.end_date,
        status=body.status,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle_to_dict(cycle)


@router.patch("/cycles/{cycle_id}/open")
def open_cycle(
    cycle_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(ADMIN),
) -> dict:
    cycle = db.scalar(select(AppraisalCycle).where(AppraisalCycle.id == cycle_id))
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")
    existing = get_open_cycle(db)
    if existing is not None and existing.id != cycle.id:
        existing.status = "closed"
        touch_cycle(existing)
    cycle.status = "open"
    touch_cycle(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle_to_dict(cycle)


@router.patch("/cycles/{cycle_id}/close")
def close_cycle(
    cycle_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(ADMIN),
) -> dict:
    cycle = db.scalar(select(AppraisalCycle).where(AppraisalCycle.id == cycle_id))
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")
    cycle.status = "closed"
    touch_cycle(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle_to_dict(cycle)


@router.get("/status")
def system_status(db: Session = Depends(get_db), _admin: User = Depends(ADMIN)) -> dict:
    settings = get_settings()
    users = db.scalar(select(func.count()).select_from(User))
    faculty = db.scalar(select(func.count()).select_from(FacultyProfile))
    cycles = db.scalar(select(func.count()).select_from(AppraisalCycle))
    return {
        "phase": 2,
        "users": users,
        "faculty_profiles": faculty,
        "cycles": cycles,
        "storage_backend": settings.storage_backend,
        "minio_endpoint": settings.minio_endpoint,
        "llm_provider": settings.llm_provider,
        "disclaimer": "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC",
    }
