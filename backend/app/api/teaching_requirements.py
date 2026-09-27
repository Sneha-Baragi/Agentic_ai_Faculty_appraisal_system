from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_faculty_profile
from app.models import FacultyProfile, User
from app.schemas.phase2 import TeachingRequirementOut
from app.services.teaching_requirements import get_teaching_requirement_for_faculty

router = APIRouter(tags=["teaching-requirements"])


@router.get("/api/v1/teaching-requirements/me", response_model=TeachingRequirementOut)
@router.get("/api/teaching-requirements/me", response_model=TeachingRequirementOut)
def read_teaching_requirement(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> TeachingRequirementOut:
    data = get_teaching_requirement_for_faculty(db, user, profile)
    return TeachingRequirementOut(**data)
