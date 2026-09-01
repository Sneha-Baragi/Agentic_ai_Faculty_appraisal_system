from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.skills import PlanningSkillInput, ReportFormattingInput, format_appraisal_report, planning_skill
from app.agents.tools import FacultyInput, RunInput, ToolError, calculate_appraisal_score_tool, get_faculty_profile_tool
from app.models import AppraisalPlan, AuditLog, FacultyAppraisalRun
from app.services.activities import create_activity

from .conftest import auth_headers, login, make_cycle, make_faculty_profile, make_user
from .test_phase2 import _attach_valid_evidence


def test_planner_clarification_revision_lock_and_ownership(client, db_session: Session):
    user = make_user(db_session, "planner-owner@demo.local", ["faculty"])
    other = make_user(db_session, "planner-other@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    other_profile = make_faculty_profile(db_session, other, employee_code="OTHER-PLAN")
    make_cycle(db_session)
    db_session.commit()
    token = login(client, user.email)
    response = client.post("/api/v1/agent/plans", headers=auth_headers(token), json={"request": "Prepare my appraisal"})
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["status"] == "NEEDS_CLARIFICATION"
    assert len(plan["clarification_questions"]) >= 2
    answers = {question: "All appraisal categories and uploaded evidence" for question in plan["clarification_questions"]}
    response = client.post(f"/api/v1/agent/plans/{plan['plan_id']}/clarify", headers=auth_headers(token), json={"answers": answers})
    assert response.status_code == 200
    assert response.json()["status"] == "READY_FOR_REVIEW"
    response = client.patch(f"/api/v1/agent/plans/{plan['plan_id']}", headers=auth_headers(token), json={"scope": "research and teaching"})
    assert response.status_code == 200
    assert response.json()["version"] == 2
    locked = client.post(f"/api/v1/agent/plans/{plan['plan_id']}/lock", headers=auth_headers(token))
    assert locked.status_code == 200
    assert locked.json()["status"] == "LOCKED"
    assert client.patch(f"/api/v1/agent/plans/{plan['plan_id']}", headers=auth_headers(token), json={"scope": "changed"}).status_code == 409
    other_token = login(client, other.email)
    assert client.get(f"/api/v1/agent/plans/{plan['plan_id']}", headers=auth_headers(other_token)).status_code == 404
    assert db_session.scalar(select(AppraisalPlan).where(AppraisalPlan.id == UUID(plan["plan_id"]))).status == "LOCKED"
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "plan_locked")) is not None


def test_planning_and_formatting_skills_are_reusable():
    first = planning_skill(PlanningSkillInput(request="Review research", appraisal_cycle="2026", scope="research", requested_sources=["uploaded PDFs"]))
    second = planning_skill(PlanningSkillInput(request="Review teaching", appraisal_cycle="2027", scope="teaching", requested_sources=["records"]))
    assert first.status == "READY_FOR_REVIEW"
    assert second.status == "READY_FOR_REVIEW"
    for plan in (first, second):
        document = format_appraisal_report(ReportFormattingInput(profile={"full_name": "Case"}, cycle={"name": "Cycle"}, score={"total": 10, "rating_recommendation": "C", "category_totals": {}}))
        assert document.json["score"]["total"] == 10
        assert document.html and document.markdown


def test_tools_enforce_ownership_and_use_persisted_score(client, db_session: Session):
    faculty = make_user(db_session, "tool-faculty@demo.local", ["faculty"])
    other = make_user(db_session, "tool-other@demo.local", ["faculty"])
    hod = make_user(db_session, "tool-hod@demo.local", ["hod"])
    profile = make_faculty_profile(db_session, faculty)
    other_profile = make_faculty_profile(db_session, other, employee_code="TOOL-OTHER")
    cycle = make_cycle(db_session)
    activity = create_activity(db_session, faculty=profile, category="research", activity_type="publications", title="Tool paper", description="", activity_date=date(2026, 1, 1), extras={"venue": "Journal", "year": 2026})
    db_session.flush()
    _attach_valid_evidence(db_session, activity.id, profile.id, cycle.id, "TOOL")
    db_session.commit()
    faculty_token = login(client, faculty.email)
    assert get_faculty_profile_tool(db_session, faculty, FacultyInput(faculty_id=profile.id)).data["id"] == str(profile.id)
    with pytest.raises(ToolError):
        get_faculty_profile_tool(db_session, other, FacultyInput(faculty_id=profile.id))
    hod_token = login(client, hod.email)
    assert hod_token
    run_response = client.post("/api/v1/appraisals/run", headers=auth_headers(faculty_token))
    assert run_response.status_code == 200
    run = db_session.scalar(select(FacultyAppraisalRun).where(FacultyAppraisalRun.faculty_id == profile.id))
    result = calculate_appraisal_score_tool(db_session, faculty, RunInput(run_id=run.id))
    assert result.data["engine_version"]
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "tool_calculate_appraisal_score_success")) is not None
