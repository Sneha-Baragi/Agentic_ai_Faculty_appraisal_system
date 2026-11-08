from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_roles
from app.core.config import get_settings
from app.models import AppraisalCycle, FacultyProfile, User
from app.schemas.appraisal import CycleCreate
from app.services.cycles import (
    close_cycle_service,
    create_cycle_service,
    cycle_to_dict,
    open_cycle_service,
)
from app.services.audit import verify_audit_log_chain

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
    cycle = create_cycle_service(
        db,
        actor=_admin,
        name=body.name,
        academic_year=body.academic_year,
        start_date=body.start_date,
        end_date=body.end_date,
        status=body.status,
    )
    return cycle_to_dict(cycle)


@router.patch("/cycles/{cycle_id}/open")
def open_cycle(
    cycle_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(ADMIN),
) -> dict:
    cycle = open_cycle_service(db, actor=_admin, cycle_id=cycle_id)
    return cycle_to_dict(cycle)


@router.patch("/cycles/{cycle_id}/close")
def close_cycle(
    cycle_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(ADMIN),
) -> dict:
    cycle = close_cycle_service(db, actor=_admin, cycle_id=cycle_id)
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


@router.get("/audit/verify")
def verify_audit_logs(
    db: Session = Depends(get_db),
    _admin: User = Depends(ADMIN),
) -> dict:
    """Read-only verification of the audit log cryptographic hash chain."""
    return verify_audit_log_chain(db)
