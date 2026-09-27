from datetime import datetime, date
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.timetable import TimetableEntry
from app.schemas.phase2 import AttendanceCreate, AttendanceOut


def list_attendance_records(
    db: Session, faculty_id: UUID
) -> List[dict]:
    records = db.scalars(
        select(AttendanceRecord)
        .where(AttendanceRecord.faculty_id == faculty_id)
        .order_by(AttendanceRecord.attended_at.desc())
    ).all()

    result = []
    for r in records:
        entry = db.get(TimetableEntry, r.timetable_entry_id)
        result.append({
            "id": str(r.id),
            "faculty_id": str(r.faculty_id),
            "timetable_entry_id": str(r.timetable_entry_id),
            "status": r.status,
            "attended_at": r.attended_at,
            "course_code": entry.course_code if entry else None,
            "section": entry.section if entry else None,
            "day_of_week": entry.day_of_week if entry else None,
            "start_time": entry.start_time.isoformat() if entry and entry.start_time else None,
            "end_time": entry.end_time.isoformat() if entry and entry.end_time else None,
            "room": entry.room if entry else None,
        })
    return result


def mark_attendance(
    db: Session, faculty_id: UUID, data: AttendanceCreate
) -> dict:
    entry = db.get(TimetableEntry, data.timetable_entry_id)
    if entry is None or entry.faculty_id != faculty_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable entry not found for this faculty",
        )

    attended_dt = data.attended_at or datetime.utcnow()
    target_date = attended_dt.date()

    # Check for duplicate attendance on the same date for this timetable entry & faculty
    existing = db.scalars(
        select(AttendanceRecord).where(
            AttendanceRecord.faculty_id == faculty_id,
            AttendanceRecord.timetable_entry_id == data.timetable_entry_id,
            func.date(AttendanceRecord.attended_at) == target_date,
        )
    ).first()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance already marked for this class on this date",
        )

    record = AttendanceRecord(
        faculty_id=faculty_id,
        timetable_entry_id=data.timetable_entry_id,
        status=data.status,
        attended_at=attended_dt,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": str(record.id),
        "faculty_id": str(record.faculty_id),
        "timetable_entry_id": str(record.timetable_entry_id),
        "status": record.status,
        "attended_at": record.attended_at,
        "course_code": entry.course_code,
        "section": entry.section,
        "day_of_week": entry.day_of_week,
        "start_time": entry.start_time.isoformat(),
        "end_time": entry.end_time.isoformat(),
        "room": entry.room,
    }
