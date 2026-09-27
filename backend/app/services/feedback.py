from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudentFeedback


def list_student_feedback(db: Session, *, faculty_id, cycle_id=None) -> list[StudentFeedback]:
    statement = select(StudentFeedback).where(StudentFeedback.faculty_id == faculty_id)
    if cycle_id:
        statement = statement.where(StudentFeedback.cycle_id == cycle_id)
    return list(db.scalars(statement.order_by(StudentFeedback.submitted_at.desc())))


def feedback_to_dict(feedback: StudentFeedback) -> dict:
    return {
        "id": str(feedback.id),
        "faculty_id": str(feedback.faculty_id),
        "cycle_id": str(feedback.cycle_id) if feedback.cycle_id else None,
        "rating": float(feedback.rating),
        "response_count": feedback.response_count,
        "comments": feedback.comments,
        "source": feedback.source,
        "submitted_at": feedback.submitted_at.isoformat() if feedback.submitted_at else None,
    }