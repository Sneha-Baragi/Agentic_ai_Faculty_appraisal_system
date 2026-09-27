from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_faculty_profile
from app.models import FacultyProfile, User
from app.schemas.phase2 import TimetableCreate, TimetableOut, TimetableUpdate
from app.services.timetable import (
    create_timetable_entry,
    delete_timetable_entry,
    list_timetable_entries,
    update_timetable_entry,
)

router = APIRouter(tags=["timetable"])


def _out(entry) -> TimetableOut:
    return TimetableOut(
        id=str(entry.id),
        faculty_id=str(entry.faculty_id),
        course_code=entry.course_code,
        section=entry.section,
        day_of_week=entry.day_of_week,
        start_time=entry.start_time.isoformat() if entry.start_time else "",
        end_time=entry.end_time.isoformat() if entry.end_time else "",
        room=entry.room,
        created_at=entry.created_at,
    )


@router.get("/api/v1/timetable/me", response_model=List[TimetableOut])
@router.get("/api/timetable/me", response_model=List[TimetableOut])
def read_timetable(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> List[TimetableOut]:
    entries = list_timetable_entries(db, profile.id)
    return [_out(e) for e in entries]


@router.post("/api/v1/timetable", response_model=TimetableOut, status_code=status.HTTP_201_CREATED)
@router.post("/api/timetable", response_model=TimetableOut, status_code=status.HTTP_201_CREATED)
def add_timetable(
    data: TimetableCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> TimetableOut:
    entry = create_timetable_entry(db, profile.id, data)
    return _out(entry)


@router.put("/api/v1/timetable/{entry_id}", response_model=TimetableOut)
@router.put("/api/timetable/{entry_id}", response_model=TimetableOut)
def edit_timetable(
    entry_id: UUID,
    data: TimetableUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> TimetableOut:
    entry = update_timetable_entry(db, profile.id, entry_id, data)
    return _out(entry)


@router.delete("/api/v1/timetable/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/api/timetable/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_timetable(
    entry_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
):
    delete_timetable_entry(db, profile.id, entry_id)
    return None
