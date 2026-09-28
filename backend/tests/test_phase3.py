from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApprovalDecision, AuditLog, FacultyAppraisalRun
from app.services.activities import create_activity

from .conftest import auth_headers, login, make_cycle, make_faculty_profile, make_user
from .test_phase2 import _attach_valid_evidence


def _make_generated_appraisal(db: Session, client, suffix: str):
    faculty_user = make_user(db, f"faculty-{suffix}@demo.local", ["faculty"])
    hod_user = make_user(db, f"hod-{suffix}@demo.local", ["hod"])
    profile = make_faculty_profile(db, faculty_user)
    cycle = make_cycle(db)
    activity = create_activity(
        db, faculty=profile, category="research", activity_type="publications", title="Publication",
        description="Evidence-backed activity", activity_date=date(2026, 1, 1), extras={"venue": "Journal", "year": 2026},
    )
    db.flush()
    _attach_valid_evidence(db, activity.id, profile.id, cycle.id, suffix)
    db.commit()
    faculty_token = login(client, faculty_user.email)
    assert client.post("/api/v1/appraisals/run", headers=auth_headers(faculty_token)).status_code == 200
    return profile, hod_user


def test_hod_approval_is_authorized_idempotent_and_audited(client, db_session: Session):
    profile, hod_user = _make_generated_appraisal(db_session, client, "approve")
    faculty_token = login(client, "faculty-approve@demo.local")
    hod_token = login(client, hod_user.email)
    endpoint = f"/api/v1/review/faculty/{profile.id}/approve"
    assert client.post(endpoint, headers=auth_headers(faculty_token)).status_code == 403
    assert client.post(endpoint).status_code == 401
    first = client.post(endpoint, headers=auth_headers(hod_token))
    second = client.post(endpoint, headers=auth_headers(hod_token))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "approved"
    run = db_session.scalar(select(FacultyAppraisalRun).where(FacultyAppraisalRun.faculty_id == profile.id))
    assert run.approval_status == "approved"
    assert db_session.scalar(select(ApprovalDecision).where(ApprovalDecision.report_id == run.current_version_id)) is not None
    assert db_session.scalar(select(AuditLog).where(AuditLog.entity_id == str(run.id))) is not None


def test_review_resume_uses_same_thread_and_action(client, db_session: Session, monkeypatch):
    profile, hod_user = _make_generated_appraisal(db_session, client, "resume")
    tok = login(client, hod_user.email)
    run = db_session.scalar(select(FacultyAppraisalRun).where(FacultyAppraisalRun.faculty_id == profile.id))
    original_thread = run.graph_thread_id
    assert original_thread is not None

    captured = {}

    def fake_invoke(command, config=None):
        captured["command"] = command
        captured["config"] = config
        return {"approval": {"action": "approve", "status": "approved"}, "next_action": "approved"}

    import app.api.review as review_module

    monkeypatch.setattr(review_module.checkpointed_graph, "invoke", fake_invoke)

    response = client.post(
        f"/api/v1/review/faculty/{profile.id}/approve",
        headers=auth_headers(tok),
    )

    assert response.status_code == 200
    assert captured["config"]["configurable"]["thread_id"] == original_thread
    assert captured["command"].resume["action"] == "approve"
    assert captured["command"].resume["reason"] is None
    assert response.json()["status"] == "approved"


def test_reject_and_request_changes_require_reason_and_block_invalid_transition(client, db_session: Session):
    profile, hod_user = _make_generated_appraisal(db_session, client, "reject")
    token = login(client, hod_user.email)
    endpoint = f"/api/v1/review/faculty/{profile.id}/reject"
    assert client.post(endpoint, headers=auth_headers(token), json={}).status_code == 422
    response = client.post(endpoint, headers=auth_headers(token), json={"reason": "Evidence is incomplete"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert client.post(f"/api/v1/review/faculty/{profile.id}/request-changes", headers=auth_headers(token), json={"reason": "Fix"}).status_code == 409
    assert client.get("/api/v1/reports/current", headers=auth_headers(login(client, "faculty-reject@demo.local"))).status_code == 200
