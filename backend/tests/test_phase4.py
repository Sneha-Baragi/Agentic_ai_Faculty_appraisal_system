from app.models import AppraisalReport, AuditLog, FacultyAppraisalRun
from sqlalchemy import select

from .conftest import auth_headers, login
from .test_phase3 import _make_generated_appraisal


def test_governance_versions_rollback_publish_and_immutability(client, db_session):
    profile, hod_user = _make_generated_appraisal(db_session, client, "governance")
    token = login(client, hod_user.email)
    base = f"/api/v1/review/faculty/{profile.id}"

    edit = client.patch(f"{base}/report/edit", headers=auth_headers(token), json={"rating_recommendation": "B"})
    assert edit.status_code == 200, edit.text
    version_two = edit.json()["id"]
    assert edit.json()["version_number"] == 2
    approve = client.post(f"{base}/approve", headers=auth_headers(token))
    assert approve.status_code == 200, approve.text
    published = client.post(f"{base}/report/publish", headers=auth_headers(token))
    assert published.status_code == 200, published.text
    assert client.post(f"{base}/report/publish", headers=auth_headers(token)).json()["status"] == "published"
    assert client.post(f"{base}/report/override", headers=auth_headers(token), json={"reason": "Late change", "total_score": 80}).status_code == 409

    history = client.get(f"{base}/reports/history", headers=auth_headers(token))
    assert history.status_code == 200
    assert len(history.json()) == 2
    assert any(item["id"] == version_two and item["status"] == "published" for item in history.json())


def test_override_rollback_and_publish_restrictions_are_audited(client, db_session):
    profile, hod_user = _make_generated_appraisal(db_session, client, "rollback")
    token = login(client, hod_user.email)
    base = f"/api/v1/review/faculty/{profile.id}"
    assert client.post(f"{base}/report/publish", headers=auth_headers(token)).status_code == 409
    assert client.post(f"{base}/report/override", headers=auth_headers(token), json={"reason": "", "total_score": 90}).status_code == 422
    override = client.post(f"{base}/report/override", headers=auth_headers(token), json={"reason": "Corrected committee score", "total_score": 90})
    assert override.status_code == 200, override.text
    assert override.json()["version_number"] == 2
    rollback = client.post(f"{base}/report/rollback", headers=auth_headers(token), json={"version_id": str(db_session.scalar(select(FacultyAppraisalRun).where(FacultyAppraisalRun.faculty_id == profile.id)).current_version_id), "reason": "Use the prior reviewed report"})
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["version_number"] == 3
    run = db_session.scalar(select(FacultyAppraisalRun).where(FacultyAppraisalRun.faculty_id == profile.id))
    assert db_session.scalar(select(AppraisalReport).where(AppraisalReport.id == run.current_version_id)).status == "generated"
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "report_rollback")) is not None


def test_faculty_can_resubmit_after_requested_changes(client, db_session):
    profile, hod_user = _make_generated_appraisal(db_session, client, "resubmit")
    hod_token = login(client, hod_user.email)
    faculty_token = login(client, "faculty-resubmit@demo.local")
    base = f"/api/v1/review/faculty/{profile.id}"
    requested = client.post(f"{base}/request-changes", headers=auth_headers(hod_token), json={"reason": "Provide clearer evidence"})
    assert requested.status_code == 200
    resubmitted = client.post("/api/v1/appraisals/resubmit", headers=auth_headers(faculty_token))
    assert resubmitted.status_code == 200
    assert resubmitted.json()["approval_status"] == "awaiting_review"
    assert client.post("/api/v1/appraisals/resubmit", headers=auth_headers(faculty_token)).status_code == 409
