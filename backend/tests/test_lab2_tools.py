from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tools import (
    ComputeInput,
    ComputeParameters,
    CoordinatorInput,
    FeedbackInput,
    RecordsInput,
    ToolError,
    compute_appraisal_tool,
    coordinate_appraisal_tools,
    read_research_records_tool,
    read_service_records_tool,
    read_student_feedback_tool,
    read_teaching_records_tool,
)
from app.models import AuditLog, StudentFeedback
from app.services.activities import create_activity

from .conftest import make_cycle, make_faculty_profile, make_user
from .test_phase2 import _attach_valid_evidence


def _make_records(db: Session, user_email: str = "lab2@demo.local"):
    user = make_user(db, user_email, ["faculty"])
    profile = make_faculty_profile(db, user, employee_code="LAB2")
    cycle = make_cycle(db)
    activities = [
        create_activity(db, faculty=profile, category="teaching", activity_type="courses_taught", title="Algorithms", description="", activity_date=date(2026, 1, 1), extras={"course_code": "CS101", "hours": 4}),
        create_activity(db, faculty=profile, category="research", activity_type="publications", title="Tool paper", description="", activity_date=date(2026, 1, 2), extras={"venue": "Journal", "year": 2026}),
        create_activity(db, faculty=profile, category="administrative", activity_type="committee_work", title="Board", description="", activity_date=date(2026, 1, 3), extras={"role": "Member", "hours": 2}),
    ]
    for activity in activities:
        db.flush()
        _attach_valid_evidence(db, activity.id, profile.id, cycle.id, "LAB2")
    db.add(StudentFeedback(faculty_id=profile.id, cycle_id=cycle.id, rating=4.5, response_count=20, comments="Clear and useful"))
    db.commit()
    return user, profile, cycle


def test_lab2_read_tools_return_structured_records_and_coordinator_uses_them(db_session: Session):
    user, profile, cycle = _make_records(db_session)
    request = RecordsInput(faculty_id=profile.id, cycle_id=cycle.id)

    teaching = read_teaching_records_tool(db_session, user, request)
    research = read_research_records_tool(db_session, user, request)
    service = read_service_records_tool(db_session, user, request)
    feedback = read_student_feedback_tool(db_session, user, FeedbackInput(**request.model_dump()))
    assert teaching.data["count"] == len(teaching.data["records"]) == 1
    assert research.data["records"][0]["category"] == "research"
    assert service.data["records"][0]["category"] == "administrative"
    assert feedback.data["records"][0]["rating"] == 4.5

    result = coordinate_appraisal_tools(
        db_session,
        user,
        CoordinatorInput(faculty_id=profile.id, cycle_id=cycle.id, request="Compute my appraisal", parameters=ComputeParameters()),
    )
    validated = result["validated_result"]
    assert validated["valid"] is True
    assert validated["computed_values"]["score"]["total"] > 0
    assert {"read_teaching_records", "read_research_records", "read_service_records", "read_student_feedback", "compute_appraisal"}.issubset(
        {call["tool"] for call in result["tool_calls"]}
    )
    assert "score" not in result["request"]
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "tool_compute_appraisal_success")) is not None


def test_lab2_checker_returns_structured_invalid_result(db_session: Session):
    user, profile, _cycle = _make_records(db_session, "lab2-invalid@demo.local")
    result = compute_appraisal_tool(
        db_session,
        user,
        ComputeInput(teaching={"records": [{"id": "bad", "evidence_ids": []}]}, research={"records": []}, service={"records": []}, feedback={"records": []}, parameters=ComputeParameters()),
    )
    assert result.data["valid"] is False
    assert result.data["validation_errors"]
    assert "computed_values" in result.data and "parsed_inputs" in result.data


def test_lab2_read_tools_enforce_faculty_ownership(db_session: Session):
    _owner, profile, cycle = _make_records(db_session, "lab2-owner@demo.local")
    stranger = make_user(db_session, "lab2-stranger@demo.local", ["faculty"])
    db_session.commit()
    with pytest.raises(ToolError):
        read_teaching_records_tool(db_session, stranger, RecordsInput(faculty_id=profile.id, cycle_id=cycle.id))