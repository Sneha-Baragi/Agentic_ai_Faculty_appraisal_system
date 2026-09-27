from typing import Optional
from uuid import UUID

from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from app.models import Evidence


def get_research_paper_status(
    db: Session, faculty_id: UUID, cycle_id: Optional[UUID] = None
) -> dict:
    query = select(func.count(Evidence.id)).where(
        Evidence.faculty_id == faculty_id,
        or_(
            Evidence.kind == "research_paper",
            Evidence.kind == "publication",
            Evidence.kind.ilike("%paper%"),
        ),
    )
    if cycle_id is not None:
        query = query.where(Evidence.cycle_id == cycle_id)

    count = db.scalar(query) or 0
    required = 2
    return {
        "submitted_count": count,
        "required_count": required,
        "is_satisfied": count >= required,
    }
