from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_faculty_profile
from app.models import FacultyProfile, User
from app.schemas.phase2 import AttendanceCreate, AttendanceOut
from app.services.attendance import list_attendance_records, mark_attendance, sync_attendance_to_course_delivery
from fastapi import HTTPException

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


from pydantic import BaseModel

class AttendanceSyncRequest(BaseModel):
    cycle_id: UUID | None = None

@router.post("/api/v1/attendance/sync")
@router.post("/api/attendance/sync")
def sync_attendance(
    payload: AttendanceSyncRequest | None = None,
    cycle_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    target_cycle_id = payload.cycle_id if payload and payload.cycle_id else cycle_id
    try:
        return sync_attendance_to_course_delivery(db, faculty_id=profile.id, cycle_id=target_cycle_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
