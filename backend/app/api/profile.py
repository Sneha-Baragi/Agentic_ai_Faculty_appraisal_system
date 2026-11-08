from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, get_faculty_profile
from app.models import AuditLog, FacultyProfile, User
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
        google_scholar_id=profile.google_scholar_id,
        google_scholar_url=profile.google_scholar_url,
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
    ALLOWED_FIELDS = {
        "full_name",
        "institution",
        "joining_date",
        "department",
        "designation",
        "google_scholar_id",
        "google_scholar_url",
    }
    dumped = body.model_dump(exclude_unset=True)
    before_snapshot = {}
    after_snapshot = {}
    for field, value in dumped.items():
        if field in ALLOWED_FIELDS:
            old_val = getattr(profile, field, None)
            before_snapshot[field] = old_val.isoformat() if hasattr(old_val, "isoformat") else old_val
            if field == "google_scholar_url" and value is not None:
                value = str(value)
            setattr(profile, field, value)
            after_snapshot[field] = value.isoformat() if hasattr(value, "isoformat") else value
    db.add(profile)
    db.add(
        AuditLog(
            actor_id=user.id,
            action="profile_updated",
            entity_type="faculty_profile",
            entity_id=str(profile.id),
            before=before_snapshot,
            after=after_snapshot,
        )
    )
    db.commit()
    db.refresh(profile)
    return _out(profile, user.email)
