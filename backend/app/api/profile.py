from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, get_faculty_profile
from app.models import FacultyProfile, User
from app.schemas.appraisal import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def _out(profile: FacultyProfile, email: str) -> ProfileOut:
    return ProfileOut(
        id=str(profile.id),
        user_id=str(profile.user_id),
        email=email,
        employee_code=profile.employee_code,
        full_name=profile.full_name,
        department=profile.department,
        designation=profile.designation,
        institution=profile.institution,
        joining_date=profile.joining_date,
    )


@router.get("/me", response_model=ProfileOut)
def read_profile(
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> ProfileOut:
    return _out(profile, user.email)


@router.patch("/me", response_model=ProfileOut)
def update_profile(
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> ProfileOut:
    ALLOWED_FIELDS = {"full_name", "institution", "joining_date", "department", "designation"}
    for field, value in body.model_dump(exclude_unset=True).items():
        if field in ALLOWED_FIELDS:
            setattr(profile, field, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _out(profile, user.email)
