import pytest
from datetime import datetime, date
from uuid import uuid4

from app.models import Evidence, FacultyActivity, User
from app.services.research_papers import get_research_paper_status
from app.services.teaching_requirements import get_teaching_requirement_for_faculty
from tests.conftest import auth_headers, login, make_faculty_profile, make_user, make_cycle


def test_role_based_teaching_requirements(client, db_session):
    user_hod = make_user(db_session, "hod@example.com", ["hod"])
    prof_hod = make_faculty_profile(db_session, user_hod)
    prof_hod.designation = "HOD"
    db_session.commit()

    token = login(client, "hod@example.com")
    res = client.get("/api/v1/teaching-requirements/me", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "HOD"
    assert data["required_hours"] == 180.0
    assert data["actual_hours"] == 0.0
    assert data["remaining_hours"] == 180.0
    assert data["completed"] is False


def test_timetable_crud_and_ownership(client, db_session):
    u1 = make_user(db_session, "f1@example.com", ["faculty"])
    f1 = make_faculty_profile(db_session, u1)
    u2 = make_user(db_session, "f2@example.com", ["faculty"])
    f2 = make_faculty_profile(db_session, u2)
    db_session.commit()

    t1 = login(client, "f1@example.com")
    t2 = login(client, "f2@example.com")

    # Create timetable entry for f1
    res = client.post(
        "/api/v1/timetable",
        json={
            "course_code": "CS101",
            "section": "Sec-A",
            "day_of_week": "Monday",
            "start_time": "09:00",
            "end_time": "10:30",
            "room": "Room 101",
        },
        headers=auth_headers(t1),
    )
    assert res.status_code == 201, res.text
    entry_id = res.json()["id"]

    # f1 can list own timetable
    res_list = client.get("/api/v1/timetable/me", headers=auth_headers(t1))
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1
    assert res_list.json()[0]["course_code"] == "CS101"

    # f2 sees empty timetable
    res_f2 = client.get("/api/v1/timetable/me", headers=auth_headers(t2))
    assert res_f2.status_code == 200
    assert len(res_f2.json()) == 0

    # f2 cannot update f1's timetable entry
    res_up = client.put(
        f"/api/v1/timetable/{entry_id}",
        json={"course_code": "CS999"},
        headers=auth_headers(t2),
    )
    assert res_up.status_code == 404

    # f1 updates timetable entry
    res_up_ok = client.put(
        f"/api/v1/timetable/{entry_id}",
        json={"course_code": "CS102"},
        headers=auth_headers(t1),
    )
    assert res_up_ok.status_code == 200
    assert res_up_ok.json()["course_code"] == "CS102"

    # f1 deletes entry
    res_del = client.delete(f"/api/v1/timetable/{entry_id}", headers=auth_headers(t1))
    assert res_del.status_code == 204

    res_list_after = client.get("/api/v1/timetable/me", headers=auth_headers(t1))
    assert len(res_list_after.json()) == 0


def test_attendance_marking_duplicate_prevention_and_hours(client, db_session):
    u = make_user(db_session, "att@example.com", ["faculty"])
    f = make_faculty_profile(db_session, u)
    db_session.commit()

    token = login(client, "att@example.com")

    # Add timetable entry: 2 hours (09:00 - 11:00)
    res_tt = client.post(
        "/api/v1/timetable",
        json={
            "course_code": "CS201",
            "section": "Sec-B",
            "day_of_week": "Tuesday",
            "start_time": "09:00",
            "end_time": "11:00",
            "room": "Lab 1",
        },
        headers=auth_headers(token),
    )
    entry_id = res_tt.json()["id"]

    # Mark attendance for today
    today_str = datetime.utcnow().isoformat()
    res_att = client.post(
        "/api/v1/attendance/mark",
        json={
            "timetable_entry_id": entry_id,
            "attended_at": today_str,
            "status": "present",
        },
        headers=auth_headers(token),
    )
    assert res_att.status_code == 201
    assert res_att.json()["status"] == "present"

    # Duplicate marking attempt on same date should fail
    res_dup = client.post(
        "/api/v1/attendance/mark",
        json={
            "timetable_entry_id": entry_id,
            "attended_at": today_str,
            "status": "present",
        },
        headers=auth_headers(token),
    )
    assert res_dup.status_code == 400
    assert "Attendance already marked" in res_dup.json()["detail"]

    # Check teaching requirement updated actual attended hours to 2.0
    res_req = client.get("/api/v1/teaching-requirements/me", headers=auth_headers(token))
    assert res_req.status_code == 200
    assert res_req.json()["actual_hours"] == 2.0


def test_research_paper_requirement_validation(client, db_session):
    from app.models import FacultyAppraisalRun
    u = make_user(db_session, "paper@example.com", ["faculty"])
    f = make_faculty_profile(db_session, u)
    c = make_cycle(db_session)
    run = FacultyAppraisalRun(faculty_id=f.id, cycle_id=c.id, status="collecting")
    db_session.add(run)
    db_session.commit()

    token = login(client, "paper@example.com")

    # Check initially 0 research papers
    res0 = client.get("/api/v1/research-papers/me", headers=auth_headers(token))
    assert res0.status_code == 200
    assert res0.json()["submitted_count"] == 0
    assert res0.json()["is_satisfied"] is False

    # Create dummy faculty activity for evidence
    act = FacultyActivity(run_id=run.id, faculty_id=f.id, cycle_id=c.id, category="research", activity_type="journal_paper", title="AI Paper")
    db_session.add(act)
    db_session.flush()

    # Add 2 research paper evidences
    e1 = Evidence(activity_id=act.id, faculty_id=f.id, cycle_id=c.id, kind="research_paper", storage_key="p1.pdf")
    e2 = Evidence(activity_id=act.id, faculty_id=f.id, cycle_id=c.id, kind="research_paper", storage_key="p2.pdf")
    db_session.add_all([e1, e2])
    db_session.commit()

    res2 = client.get("/api/v1/research-papers/me", headers=auth_headers(token))
    assert res2.status_code == 200
    assert res2.json()["submitted_count"] == 2
    assert res2.json()["is_satisfied"] is True


def test_project_teams_crud_and_scoping(client, db_session):
    u1 = make_user(db_session, "team1@example.com", ["faculty"])
    f1 = make_faculty_profile(db_session, u1)
    u2 = make_user(db_session, "team2@example.com", ["faculty"])
    f2 = make_faculty_profile(db_session, u2)
    db_session.commit()

    t1 = login(client, "team1@example.com")
    t2 = login(client, "team2@example.com")

    # Create project team for f1
    res = client.post(
        "/api/v1/project-teams",
        json={
            "title": "Smart Farming IoT",
            "status": "active",
            "members": [
                {"name": "Alice Smith", "email": "alice@student.edu"},
                {"name": "Bob Jones", "email": "bob@student.edu"},
            ],
        },
        headers=auth_headers(t1),
    )
    assert res.status_code == 201, res.text
    team_id = res.json()["id"]
    assert len(res.json()["members"]) == 2

    # f1 lists project teams
    res_l1 = client.get("/api/v1/project-teams/me", headers=auth_headers(t1))
    assert res_l1.status_code == 200
    assert len(res_l1.json()) == 1

    # f2 lists project teams (should be empty)
    res_l2 = client.get("/api/v1/project-teams/me", headers=auth_headers(t2))
    assert res_l2.status_code == 200
    assert len(res_l2.json()) == 0

    # f2 cannot delete f1's team
    res_d2 = client.delete(f"/api/v1/project-teams/{team_id}", headers=auth_headers(t2))
    assert res_d2.status_code == 404

    # f1 deletes team
    res_d1 = client.delete(f"/api/v1/project-teams/{team_id}", headers=auth_headers(t1))
    assert res_d1.status_code == 204


def test_phase2_typed_tools(client, db_session):
    from app.agents.tools import (
        TOOL_REGISTRY,
        FacultyInput,
        TimetableCreateInput,
        TimetableDeleteInput,
        ProjectTeamCreateInput,
        ProjectTeamDeleteInput,
    )
    u = make_user(db_session, "tooluser@example.com", ["faculty"])
    f = make_faculty_profile(db_session, u)
    db_session.commit()

    # Call get_teaching_requirement tool
    res_req = TOOL_REGISTRY["get_teaching_requirement"](db_session, u, FacultyInput(faculty_id=f.id))
    assert res_req.tool == "get_teaching_requirement"
    assert "required_hours" in res_req.data

    # Call create_timetable tool
    res_tt = TOOL_REGISTRY["create_timetable"](
        db_session,
        u,
        TimetableCreateInput(
            faculty_id=f.id,
            course_code="CS301",
            section="A",
            day_of_week="Wednesday",
            start_time="14:00",
            end_time="15:00",
        ),
    )
    assert res_tt.tool == "create_timetable"
    assert res_tt.data["course_code"] == "CS301"

    # Call list_timetable tool
    res_list = TOOL_REGISTRY["list_timetable"](db_session, u, FacultyInput(faculty_id=f.id))
    assert len(res_list.data["timetable"]) == 1

    # Call create_project_team tool
    res_pt = TOOL_REGISTRY["create_project_team"](
        db_session,
        u,
        ProjectTeamCreateInput(
            faculty_id=f.id,
            title="NLP Chatbot Team",
            members=[{"name": "Charlie", "email": "charlie@student.edu"}],
        ),
    )
    assert res_pt.tool == "create_project_team"
    assert res_pt.data["title"] == "NLP Chatbot Team"

    # Call list_project_teams tool
    res_pt_list = TOOL_REGISTRY["list_project_teams"](db_session, u, FacultyInput(faculty_id=f.id))
    assert len(res_pt_list.data["teams"]) == 1
