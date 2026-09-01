from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models import AppraisalCycle, User
from app.schemas.appraisal import CycleCreate, CycleOut
from app.services.constants import CYCLE_STATUSES
from app.services.cycles import cycle_to_dict, get_open_cycle, new_cycle, touch_cycle

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
