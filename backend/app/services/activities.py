from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AdministrativeActivity,
    FacultyActivity,
    FacultyProfile,
    ResearchActivity,
    TeachingActivity,
)
from app.services.constants import ACTIVITY_TYPES, TYPE_TO_RUBRIC
from app.services.cycles import get_or_create_run, get_open_cycle


class ActivityError(ValueError):
    pass


def list_activities(db: Session, *, faculty_id, category: str | None = None, cycle_id=None) -> list[FacultyActivity]:
    stmt = (
        select(FacultyActivity)
        .options(
            selectinload(FacultyActivity.research),
            selectinload(FacultyActivity.teaching),
            selectinload(FacultyActivity.administrative),
            selectinload(FacultyActivity.evidence),
        )
        .where(FacultyActivity.faculty_id == faculty_id)
        .order_by(FacultyActivity.created_at.desc())
    )
    if category:
        stmt = stmt.where(FacultyActivity.category == category)
    if cycle_id:
        stmt = stmt.where(FacultyActivity.cycle_id == cycle_id)
    return list(db.scalars(stmt))


def get_owned_activity(db: Session, *, activity_id, faculty_id) -> FacultyActivity | None:
    return db.scalar(
        select(FacultyActivity)
        .options(selectinload(FacultyActivity.evidence))
        .where(FacultyActivity.id == activity_id, FacultyActivity.faculty_id == faculty_id)
    )


def create_activity(
    db: Session,
    *,
    faculty: FacultyProfile,
    category: str,
    activity_type: str,
    title: str,
    description: str | None,
    activity_date: date | None,
    extras: dict | None = None,
) -> FacultyActivity:
    if category not in ACTIVITY_TYPES:
        raise ActivityError("Unknown category")
    if activity_type not in ACTIVITY_TYPES[category]:
        raise ActivityError("Unknown activity type for category")
    cycle = get_open_cycle(db)
    if cycle is None:
        raise ActivityError("No open appraisal cycle")
    run = get_or_create_run(db, faculty=faculty, cycle=cycle)
    extras = extras or {}
    activity = FacultyActivity(
        run_id=run.id,
        faculty_id=faculty.id,
        cycle_id=cycle.id,
        category=category,
        activity_type=activity_type,
        title=title,
        description=description,
        activity_date=activity_date,
        status="raw",
        source="self_report",
    )
    db.add(activity)
    db.flush()
    _write_subtype(db, activity, extras)
    return activity


def update_activity(
    db: Session,
    *,
    activity: FacultyActivity,
    title: str | None = None,
    description: str | None = None,
    activity_date: date | None = None,
    activity_type: str | None = None,
    extras: dict | None = None,
) -> FacultyActivity:
    if title is not None:
        activity.title = title
    if description is not None:
        activity.description = description
    if activity_date is not None:
        activity.activity_date = activity_date
    if activity_type is not None:
        if activity_type not in ACTIVITY_TYPES.get(activity.category, []):
            raise ActivityError("Unknown activity type for category")
        activity.activity_type = activity_type
    activity.updated_at = datetime.utcnow()
    if extras:
        _write_subtype(db, activity, extras)
    return activity


def delete_activity(db: Session, *, activity: FacultyActivity) -> None:
    for item in list(activity.evidence or []):
        db.delete(item)
    if activity.research is not None:
        db.delete(activity.research)
    if activity.teaching is not None:
        db.delete(activity.teaching)
    if activity.administrative is not None:
        db.delete(activity.administrative)
    db.delete(activity)


def _write_subtype(db: Session, activity: FacultyActivity, extras: dict) -> None:
    if activity.category == "research":
        row = activity.research or ResearchActivity(activity_id=activity.id)
        row.type = activity.activity_type or "publications"
        row.title = activity.title or "Untitled"
        row.venue = extras.get("venue")
        row.year = extras.get("year")
        row.authors = extras.get("authors")
        row.extras = extras
        if activity.research is None:
            db.add(row)
    elif activity.category == "teaching":
        row = activity.teaching or TeachingActivity(activity_id=activity.id)
        row.course_code = extras.get("course_code") or activity.activity_type or "COURSE"
        row.hours = float(extras.get("hours") or 1)
        row.pedagogy = extras.get("pedagogy")
        row.outcomes = extras
        if activity.teaching is None:
            db.add(row)
    elif activity.category == "administrative":
        row = activity.administrative or AdministrativeActivity(activity_id=activity.id)
        row.role = extras.get("role") or activity.title or activity.activity_type or "role"
        row.body = extras.get("body")
        row.hours = float(extras.get("hours") or 0)
        row.extras = extras
        if activity.administrative is None:
            db.add(row)


def activity_to_dict(activity: FacultyActivity) -> dict:
    evidence = list(activity.evidence or [])
    quantity = 1.0
    if activity.teaching is not None:
        quantity = float(activity.teaching.hours or 1)
    mapping = TYPE_TO_RUBRIC.get(activity.activity_type or "")
    subtype = activity.research or activity.teaching or activity.administrative
    details = {}
    if activity.research is not None:
        details = {"venue": subtype.venue, "year": subtype.year, "authors": subtype.authors}
    elif activity.teaching is not None:
        details = {"course_code": subtype.course_code, "hours": subtype.hours, "pedagogy": subtype.pedagogy}
    elif activity.administrative is not None:
        details = {"role": subtype.role, "body": subtype.body, "hours": subtype.hours}
    return {
        "id": str(activity.id),
        "faculty_id": str(activity.faculty_id) if activity.faculty_id else None,
        "appraisal_cycle_id": str(activity.cycle_id) if activity.cycle_id else None,
        "category": activity.category,
        "activity_type": activity.activity_type,
        "title": activity.title,
        "description": activity.description,
        "date": activity.activity_date.isoformat() if activity.activity_date else None,
        "status": activity.status,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
        "updated_at": activity.updated_at.isoformat() if activity.updated_at else None,
        "quantity": quantity,
        "rubric_code": mapping[1] if mapping else None,
        "evidence_ids": [str(item.id) for item in evidence],
        "evidence_statuses": [item.validation_status for item in evidence],
        "evidence_count": len(evidence),
        "details": details,
    }
