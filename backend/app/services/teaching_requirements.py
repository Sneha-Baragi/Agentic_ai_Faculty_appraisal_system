from datetime import datetime
from typing import Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AttendanceRecord, FacultyProfile, Role, TeachingRequirement, TimetableEntry, User


DEFAULT_TEACHING_REQUIREMENTS = {
    "hod": 180.0,
    "professor": 150.0,
    "assistant_professor": 120.0,
    "phd": 100.0,
}


def seed_default_teaching_requirements(db: Session) -> None:
    existing = {tr.role.lower(): tr for tr in db.scalars(select(TeachingRequirement)).all()}
    for role_key, req_hours in DEFAULT_TEACHING_REQUIREMENTS.items():
        if role_key not in existing:
            db.add(TeachingRequirement(role=role_key, required_hours=req_hours))
    db.commit()


def resolve_faculty_role(user: User, profile: FacultyProfile) -> str:
    user_roles = [r.name.lower() for r in user.roles] if user.roles else []
    for r in user_roles:
        r_norm = r.replace(" ", "_").replace("-", "_")
        if r_norm in DEFAULT_TEACHING_REQUIREMENTS:
            return r_norm
        if "hod" in r_norm or "head" in r_norm:
            return "hod"
        if "phd" in r_norm or "doctor" in r_norm:
            return "phd"
        if "assistant" in r_norm or "asst" in r_norm:
            return "assistant_professor"
        if "professor" in r_norm or "prof" in r_norm:
            return "professor"

    desig = (profile.designation or "").lower()
    if "hod" in desig or "head" in desig:
        return "hod"
    if "phd" in desig or "doctor" in desig or "dr." in desig or "dr " in desig:
        return "phd"
    if "assistant" in desig or "asst" in desig:
        return "assistant_professor"
    if "professor" in desig or "prof" in desig:
        return "professor"

    return "assistant_professor"


def calculate_attended_hours(db: Session, faculty_id: UUID) -> float:
    records = db.scalars(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.faculty_id == faculty_id,
            AttendanceRecord.status == "present",
        )
    ).all()

    total_seconds = 0.0
    for record in records:
        entry = db.get(TimetableEntry, record.timetable_entry_id)
        if entry and entry.start_time and entry.end_time:
            t1 = datetime.combine(datetime.today(), entry.start_time)
            t2 = datetime.combine(datetime.today(), entry.end_time)
            if t2 > t1:
                total_seconds += (t2 - t1).total_seconds()
            else:
                total_seconds += 3600.0  # default 1 hour fallback

    return round(total_seconds / 3600.0, 2)


def get_teaching_requirement_for_faculty(
    db: Session, user: User, profile: FacultyProfile
) -> dict:
    seed_default_teaching_requirements(db)
    role_key = resolve_faculty_role(user, profile)

    tr = db.scalar(
        select(TeachingRequirement).where(
            func.lower(TeachingRequirement.role) == role_key.lower()
        )
    )
    if tr is None:
        tr = db.scalar(
            select(TeachingRequirement).where(
                func.lower(TeachingRequirement.role) == "assistant_professor"
            )
        )

    req_hours = tr.required_hours if tr else 120.0
    actual_hours = calculate_attended_hours(db, profile.id)
    remaining_hours = max(0.0, round(req_hours - actual_hours, 2))
    completed = actual_hours >= req_hours

    display_role_map = {
        "hod": "HOD",
        "professor": "Professor",
        "assistant_professor": "Assistant Professor",
        "phd": "PhD / Doctor",
    }

    return {
        "role": display_role_map.get(role_key, role_key.title()),
        "required_hours": req_hours,
        "actual_hours": actual_hours,
        "remaining_hours": remaining_hours,
        "completed": completed,
    }
