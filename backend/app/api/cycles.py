from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models import AppraisalCycle, User
from app.schemas.appraisal import CycleCreate, CycleOut
from app.services.cycles import (
    create_cycle_service,
    cycle_to_dict,
    get_open_cycle,
)

router = APIRouter(prefix="/api/v1/cycles", tags=["cycles"])


@router.get("", response_model=list[CycleOut])
def list_cycles(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict]:
    rows = list(db.scalars(select(AppraisalCycle).order_by(AppraisalCycle.starts_on.desc())))
    return [cycle_to_dict(row) for row in rows]


@router.get("/current")
def current_cycle(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> dict:
    cycle = get_open_cycle(db)
    if cycle is None:
        raise HTTPException(status_code=404, detail="No open appraisal cycle")
    return cycle_to_dict(cycle)


@router.post("", response_model=CycleOut)
def create_cycle(
    body: CycleCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
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
