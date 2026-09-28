from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppraisalReport, AppraisalScore, FacultyProfile


def retrieve_faculty_memory(
    db: Session,
    *,
    faculty: FacultyProfile,
    current_cycle_id,
    limit: int = 5,
) -> dict[str, Any]:
    previous_scores = [
        {
            "id": str(score.id),
            "cycle_id": str(score.cycle_id) if score.cycle_id is not None else None,
            "total": score.total,
            "breakdown": score.breakdown,
            "computed_at": score.computed_at.isoformat() if score.computed_at is not None else None,
            "engine_version": score.engine_version,
        }
        for score in db.scalars(
            select(AppraisalScore)
            .where(AppraisalScore.faculty_id == faculty.id, AppraisalScore.cycle_id != current_cycle_id)
            .order_by(AppraisalScore.computed_at.desc())
            .limit(limit)
        )
    ]

    previous_reports = [
        {
            "id": str(report.id),
            "run_id": str(report.run_id),
            "version_number": report.version_number,
            "summary_md": report.summary_md,
            "rating_recommendation": report.rating_recommendation,
            "status": report.status,
            "published_at": report.published_at.isoformat() if report.published_at is not None else None,
        }
        for report in db.scalars(
            select(AppraisalReport)
            .join(AppraisalScore, AppraisalReport.score_id == AppraisalScore.id)
            .where(AppraisalScore.faculty_id == faculty.id, AppraisalScore.cycle_id != current_cycle_id)
            .order_by(AppraisalReport.published_at.desc(), AppraisalReport.version_number.desc(), AppraisalReport.id.desc())
            .limit(limit)
        )
    ]

    return {
        "faculty_profile": {
            "id": str(faculty.id),
            "employee_code": faculty.employee_code,
            "full_name": faculty.full_name,
            "department": faculty.department,
            "designation": faculty.designation,
            "institution": faculty.institution,
        },
        "previous_scores": previous_scores,
        "previous_reports": previous_reports,
    }
