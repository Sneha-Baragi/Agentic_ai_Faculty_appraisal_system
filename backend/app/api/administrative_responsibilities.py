from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_faculty_profile
from app.models import FacultyProfile
from app.schemas.phase2 import AdministrativeResponsibilityCreate
from app.services.activities import ActivityError
from app.services.administrative_responsibilities import (
    create_administrative_responsibility,
    get_administrative_responsibility_evidence,
    list_administrative_responsibilities,
)

router = APIRouter(prefix="/api/v1/administrative-responsibilities", tags=["administrative-responsibilities"])


@router.get("")
def read_administrative_responsibilities(
    cycle_id: UUID | None = None,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> list[dict]:
    return list_administrative_responsibilities(db, faculty_id=profile.id, cycle_id=cycle_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_administrative_responsibility(
    body: AdministrativeResponsibilityCreate,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    try:
        result = create_administrative_responsibility(db, faculty=profile, data=body)
        db.commit()
        return result
    except ActivityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{responsibility_id}/evidence")
def read_administrative_responsibility_evidence(
    responsibility_id: UUID,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> list[dict]:
    evidence = get_administrative_responsibility_evidence(
        db,
        faculty_id=profile.id,
        responsibility_id=responsibility_id,
    )
    if evidence is None:
        raise HTTPException(status_code=404, detail="Administrative responsibility not found")
    return evidence