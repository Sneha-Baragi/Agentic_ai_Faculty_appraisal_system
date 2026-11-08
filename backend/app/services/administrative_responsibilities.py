from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AppraisalCycle, FacultyActivity, FacultyProfile
from app.schemas.phase2 import AdministrativeResponsibilityCreate
from app.services.activities import ActivityError, activity_to_dict, create_activity
from app.services.evidence import evidence_to_dict


def list_administrative_responsibilities(
    db: Session,
    *,
    faculty_id: UUID,
    cycle_id: UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(FacultyActivity)
        .options(
            selectinload(FacultyActivity.administrative),
            selectinload(FacultyActivity.evidence),
        )
        .where(
            FacultyActivity.faculty_id == faculty_id,
            FacultyActivity.category == "administrative",
        )
        .order_by(FacultyActivity.created_at.desc())
    )
    if cycle_id is not None:
        stmt = stmt.where(FacultyActivity.cycle_id == cycle_id)
    return [_responsibility_to_dict(db, activity) for activity in db.scalars(stmt)]


def create_administrative_responsibility(
    db: Session,
    *,
    faculty: FacultyProfile,
    data: AdministrativeResponsibilityCreate,
) -> dict[str, Any]:
    extras = {
        "role": data.role,
        "body": data.organizational_unit,
        "organizational_unit": data.organizational_unit,
        "start_date": data.start_date.isoformat() if data.start_date else None,
        "end_date": data.end_date.isoformat() if data.end_date else None,
        "evidence_reference": data.evidence_reference,
    }
    activity = create_activity(
        db,
        faculty=faculty,
        category="administrative",
        activity_type="institutional_responsibilities",
        title=data.role,
        description=data.description,
        activity_date=data.start_date,
        extras=extras,
    )
    return _responsibility_to_dict(db, activity)


def get_administrative_responsibility_evidence(
    db: Session,
    *,
    faculty_id: UUID,
    responsibility_id: UUID,
) -> list[dict[str, Any]] | None:
    activity = db.scalar(
        select(FacultyActivity)
        .options(selectinload(FacultyActivity.evidence))
        .where(
            FacultyActivity.id == responsibility_id,
            FacultyActivity.faculty_id == faculty_id,
            FacultyActivity.category == "administrative",
        )
    )
    if activity is None:
        return None
    return [evidence_to_dict(item) for item in activity.evidence]


def _responsibility_to_dict(db: Session, activity: FacultyActivity) -> dict[str, Any]:
    result = activity_to_dict(activity)
    subtype = activity.administrative
    extras = (subtype.extras or {}) if subtype else {}
    cycle = db.get(AppraisalCycle, activity.cycle_id) if activity.cycle_id else None
    result.update(
        {
            "role": subtype.role if subtype else activity.title,
            "organizational_unit": extras.get("organizational_unit") or (subtype.body if subtype else None),
            "academic_year": cycle.academic_year if cycle else None,
            "start_date": extras.get("start_date"),
            "end_date": extras.get("end_date"),
            "evidence_reference": extras.get("evidence_reference"),
            "evidence": [evidence_to_dict(item) for item in activity.evidence],
        }
    )
    return result