from datetime import datetime, time
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.timetable import TimetableEntry
from app.schemas.phase2 import TimetableCreate, TimetableUpdate


def parse_time(time_str: str) -> time:
    try:
        if len(time_str) == 5:  # HH:MM
            return datetime.strptime(time_str, "%H:%M").time()
        elif len(time_str) == 8:  # HH:MM:SS
            return datetime.strptime(time_str, "%H:%M:%S").time()
        else:
            return time.fromisoformat(time_str)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time format: {time_str}. Use HH:MM or HH:MM:SS",
        ) from exc


def list_timetable_entries(db: Session, faculty_id: UUID) -> List[TimetableEntry]:
    return db.scalars(
        select(TimetableEntry)
        .where(TimetableEntry.faculty_id == faculty_id)
        .order_by(TimetableEntry.day_of_week, TimetableEntry.start_time)
    ).all()


def create_timetable_entry(
    db: Session, faculty_id: UUID, data: TimetableCreate
) -> TimetableEntry:
    start_t = parse_time(data.start_time)
    end_t = parse_time(data.end_time)
    if start_t >= end_t:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be earlier than end time",
        )

    entry = TimetableEntry(
        faculty_id=faculty_id,
        course_code=data.course_code.strip(),
        section=data.section.strip(),
        day_of_week=data.day_of_week.strip(),
        start_time=start_t,
        end_time=end_t,
        room=data.room.strip() if data.room else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def update_timetable_entry(
    db: Session, faculty_id: UUID, entry_id: UUID, data: TimetableUpdate
) -> TimetableEntry:
    entry = db.get(TimetableEntry, entry_id)
    if entry is None or entry.faculty_id != faculty_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable entry not found",
        )

    if data.course_code is not None:
        entry.course_code = data.course_code.strip()
    if data.section is not None:
        entry.section = data.section.strip()
    if data.day_of_week is not None:
        entry.day_of_week = data.day_of_week.strip()
    if data.start_time is not None:
        entry.start_time = parse_time(data.start_time)
    if data.end_time is not None:
        entry.end_time = parse_time(data.end_time)
    if data.room is not None:
        entry.room = data.room.strip() if data.room else None

    if entry.start_time >= entry.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be earlier than end time",
        )

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def delete_timetable_entry(db: Session, faculty_id: UUID, entry_id: UUID) -> None:
    entry = db.get(TimetableEntry, entry_id)
    if entry is None or entry.faculty_id != faculty_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable entry not found",
        )
    db.delete(entry)
    db.commit()
