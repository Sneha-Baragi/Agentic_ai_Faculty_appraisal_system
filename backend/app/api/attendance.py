from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_faculty_profile
from app.models import FacultyProfile, User
from app.schemas.phase2 import AttendanceCreate, AttendanceOut
from app.services.attendance import list_attendance_records, mark_attendance

router = APIRouter(tags=["attendance"])


@router.get("/api/v1/attendance/me", response_model=List[AttendanceOut])
@router.get("/api/attendance/me", response_model=List[AttendanceOut])
@router.get("/api/v1/attendance", response_model=List[AttendanceOut])
@router.get("/api/attendance", response_model=List[AttendanceOut])
def read_attendance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> List[AttendanceOut]:
    records = list_attendance_records(db, profile.id)
    return [AttendanceOut(**r) for r in records]


@router.post("/api/v1/attendance/mark", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
@router.post("/api/attendance/mark", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
@router.post("/api/v1/attendance", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
@router.post("/api/attendance", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def record_attendance(
    data: AttendanceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> AttendanceOut:
    res = mark_attendance(db, profile.id, data)
    return AttendanceOut(**res)
