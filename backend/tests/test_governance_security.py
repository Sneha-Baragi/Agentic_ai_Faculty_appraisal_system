from datetime import date
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditLog, FacultyProfile
from app.services.activities import create_activity
from app.services.reports import build_report
from app.services.audit import verify_audit_log_chain

from .conftest import auth_headers, login, make_cycle, make_faculty_profile, make_user
from .test_phase2 import _attach_valid_evidence


def _make_department_appraisal(db: Session, client, suffix: str, department: str = "CS"):
    faculty_user = make_user(db, f"faculty-{suffix}@demo.local", ["faculty"])
    profile = FacultyProfile(
        user_id=faculty_user.id,
        employee_code=f"F-{suffix}",
        full_name=f"Faculty {suffix}",
        department=department,
        designation="Asst Prof",
        confidentiality_scope="self",
    )
    db.add(profile)
    cycle = make_cycle(db)
    activity = create_activity(
        db,
        faculty=profile,
        category="research",
        activity_type="publications",
        title=f"Publication {suffix}",
        description="Evidence-backed activity",
        activity_date=date(2026, 1, 1),
        extras={"venue": "Journal", "year": 2026},
    )
    db.flush()
    _attach_valid_evidence(db, activity.id, profile.id, cycle.id, suffix)
    db.commit()
    faculty_token = login(client, faculty_user.email)
    run_resp = client.post("/api/v1/appraisals/run", headers=auth_headers(faculty_token))
    assert run_resp.status_code == 200, run_resp.text
    return profile, faculty_user


# ==============================================================================
# SEC-01: Reviewer authorization and departmental access boundaries
# ==============================================================================

def test_hod_cross_department_forbidden(client, db_session: Session):
    # Faculty in Electrical Engineering (EE)
    fac_ee_profile, _ = _make_department_appraisal(db_session, client, "sec01ee", department="EE")

    # HOD in Computer Science (CS)
    hod_cs_user = make_user(db_session, "hod-cs@demo.local", ["hod"])
    hod_cs_profile = FacultyProfile(
        user_id=hod_cs_user.id,
        employee_code="HOD-CS-01",
        full_name="CS Department Head",
        department="CS",
        designation="Professor & HOD",
        confidentiality_scope="self",
    )
    db_session.add(hod_cs_profile)
    db_session.commit()

    hod_token = login(client, "hod-cs@demo.local")

    # 1. HOD /faculty list should not include EE faculty
    list_resp = client.get("/api/v1/review/faculty", headers=auth_headers(hod_token))
    assert list_resp.status_code == 200
    listed_ids = [item["id"] for item in list_resp.json()]
    assert str(fac_ee_profile.id) not in listed_ids

    # 2. Packet access is denied with 403 Forbidden
    packet_resp = client.get(
        f"/api/v1/review/faculty/{fac_ee_profile.id}",
        headers=auth_headers(hod_token),
    )
    assert packet_resp.status_code == 403

    # 3. Report history access is denied with 403 Forbidden
    history_resp = client.get(
        f"/api/v1/review/faculty/{fac_ee_profile.id}/reports/history",
        headers=auth_headers(hod_token),
    )
    assert history_resp.status_code == 403

    # 4. Approval decision is denied with 403 Forbidden
    approve_resp = client.post(
        f"/api/v1/review/faculty/{fac_ee_profile.id}/approve",
        headers=auth_headers(hod_token),
        json={"reason": "Unauthorized cross-dept approval"},
    )
    assert approve_resp.status_code == 403

    # 5. Reject is denied with 403 Forbidden
    reject_resp = client.post(
        f"/api/v1/review/faculty/{fac_ee_profile.id}/reject",
        headers=auth_headers(hod_token),
        json={"reason": "Cross-dept reject"},
    )
    assert reject_resp.status_code == 403

    # 6. Request changes is denied with 403 Forbidden
    changes_resp = client.post(
        f"/api/v1/review/faculty/{fac_ee_profile.id}/request-changes",
        headers=auth_headers(hod_token),
        json={"reason": "Cross-dept changes"},
    )
    assert changes_resp.status_code == 403

    # 7. Report edit is denied with 403 Forbidden
    edit_resp = client.patch(
        f"/api/v1/review/faculty/{fac_ee_profile.id}/report/edit",
        headers=auth_headers(hod_token),
        json={"rating_recommendation": "B"},
    )
    assert edit_resp.status_code == 403

    # 8. Report override is denied with 403 Forbidden
    override_resp = client.post(
        f"/api/v1/review/faculty/{fac_ee_profile.id}/report/override",
        headers=auth_headers(hod_token),
        json={"reason": "Cross-dept override", "total_score": 75},
    )
    assert override_resp.status_code == 403

    # 9. Report rollback is denied with 403 Forbidden
    rollback_resp = client.post(
        f"/api/v1/review/faculty/{fac_ee_profile.id}/report/rollback",
        headers=auth_headers(hod_token),
        json={"version_id": "dummy", "reason": "Cross-dept rollback"},
    )
    assert rollback_resp.status_code == 403

    # 10. Report publish is denied with 403 Forbidden
    publish_resp = client.post(
        f"/api/v1/review/faculty/{fac_ee_profile.id}/report/publish",
        headers=auth_headers(hod_token),
    )
    assert publish_resp.status_code == 403


def test_same_department_hod_and_dean_admin_allowed(client, db_session: Session):
    # Faculty in CS
    fac_cs_profile, _ = _make_department_appraisal(db_session, client, "sec01cs", department="CS")
    # Faculty in EE
    fac_ee_profile, _ = _make_department_appraisal(db_session, client, "sec01ee2", department="EE")

    # HOD in CS
    hod_cs_user = make_user(db_session, "hod-cs-allowed@demo.local", ["hod"])
    hod_cs_profile = FacultyProfile(
        user_id=hod_cs_user.id,
        employee_code="HOD-CS-02",
        full_name="CS Department Head 2",
        department="CS",
        designation="Professor & HOD",
        confidentiality_scope="self",
    )
    db_session.add(hod_cs_profile)

    # Dean (institutional scope)
    dean_user = make_user(db_session, "dean@demo.local", ["dean"])

    # Admin (institutional scope)
    admin_user = make_user(db_session, "admin-reviewer@demo.local", ["admin"])
    db_session.commit()

    hod_token = login(client, "hod-cs-allowed@demo.local")
    dean_token = login(client, "dean@demo.local")
    admin_token = login(client, "admin-reviewer@demo.local")

    # Same-department HOD succeeds
    assert client.get(f"/api/v1/review/faculty/{fac_cs_profile.id}", headers=auth_headers(hod_token)).status_code == 200

    # Institutional-scope Dean succeeds on both CS and EE
    assert client.get(f"/api/v1/review/faculty/{fac_cs_profile.id}", headers=auth_headers(dean_token)).status_code == 200
    assert client.get(f"/api/v1/review/faculty/{fac_ee_profile.id}", headers=auth_headers(dean_token)).status_code == 200

    # Institutional-scope Admin succeeds on EE
    assert client.get(f"/api/v1/review/faculty/{fac_ee_profile.id}", headers=auth_headers(admin_token)).status_code == 200


def test_unauthorized_role_access_returns_403(client, db_session: Session):
    faculty_user = make_user(db_session, "regular-faculty@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, faculty_user)
    db_session.commit()

    fac_token = login(client, "regular-faculty@demo.local")

    # Faculty cannot list reviewer faculty
    assert client.get("/api/v1/review/faculty", headers=auth_headers(fac_token)).status_code == 403
    # Faculty cannot access reviewer packet
    assert client.get(f"/api/v1/review/faculty/{profile.id}", headers=auth_headers(fac_token)).status_code == 403
    # Faculty cannot approve
    assert client.post(f"/api/v1/review/faculty/{profile.id}/approve", headers=auth_headers(fac_token)).status_code == 403


# ==============================================================================
# SEC-03: Audit logging for core data modifications
# ==============================================================================

def test_audit_logging_activity_lifecycle(client, db_session: Session):
    user = make_user(db_session, "audit-act@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    make_cycle(db_session)
    db_session.commit()
    token = login(client, "audit-act@demo.local")

    # 1. Create activity
    create_resp = client.post(
        "/api/v1/activities",
        headers=auth_headers(token),
        json={
            "category": "research",
            "activity_type": "publications",
            "title": "Audited Paper",
            "description": "Paper for audit test",
            "activity_date": "2026-03-01",
            "extras": {"venue": "IEEE"},
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    act_id = create_resp.json()["id"]

    audit_create = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "activity_created",
            AuditLog.entity_id == act_id,
        )
    )
    assert audit_create is not None
    assert audit_create.actor_id == user.id
    assert audit_create.after.get("title") == "Audited Paper"

    # 2. Patch activity
    patch_resp = client.patch(
        f"/api/v1/activities/{act_id}",
        headers=auth_headers(token),
        json={"title": "Updated Audited Paper"},
    )
    assert patch_resp.status_code == 200, patch_resp.text

    audit_update = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "activity_updated",
            AuditLog.entity_id == act_id,
        )
    )
    assert audit_update is not None
    assert audit_update.before.get("title") == "Audited Paper"
    assert audit_update.after.get("title") == "Updated Audited Paper"

    # 3. Delete activity
    del_resp = client.delete(
        f"/api/v1/activities/{act_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code in (200, 204), del_resp.text

    audit_del = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "activity_deleted",
            AuditLog.entity_id == act_id,
        )
    )
    assert audit_del is not None
    assert audit_del.before.get("title") == "Updated Audited Paper"


def test_audit_logging_evidence_upload(client, db_session: Session):
    user = make_user(db_session, "audit-ev@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    make_cycle(db_session)
    act = create_activity(
        db_session,
        faculty=profile,
        category="research",
        activity_type="publications",
        title="Evidence Audit Act",
        description="",
        activity_date=date(2026, 1, 1),
        extras={},
    )
    db_session.commit()
    token = login(client, "audit-ev@demo.local")

    upload_resp = client.post(
        f"/api/v1/evidence?activity_id={act.id}",
        headers=auth_headers(token),
        files={"file": ("cert.pdf", b"%PDF-1.4 sample content", "application/pdf")},
        data={"activity_id": str(act.id)},
    )
    assert upload_resp.status_code == 201, upload_resp.text
    ev_id = upload_resp.json()["id"]

    audit_ev = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "evidence_uploaded",
            AuditLog.entity_id == ev_id,
        )
    )
    assert audit_ev is not None
    assert audit_ev.actor_id == user.id
    assert audit_ev.after.get("filename") == "cert.pdf"


def test_audit_logging_profile_update(client, db_session: Session):
    user = make_user(db_session, "audit-profile@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    db_session.commit()
    token = login(client, "audit-profile@demo.local")

    patch_resp = client.patch(
        "/api/v1/profile/me",
        headers=auth_headers(token),
        json={"full_name": "Audited Name Change", "institution": "Tech Institute"},
    )
    assert patch_resp.status_code == 200, patch_resp.text

    audit_prof = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "profile_updated",
            AuditLog.entity_id == str(profile.id),
        )
    )
    assert audit_prof is not None
    assert audit_prof.actor_id == user.id
    assert audit_prof.after.get("full_name") == "Audited Name Change"


def test_audit_logging_appraisal_run(client, db_session: Session):
    profile, faculty_user = _make_department_appraisal(db_session, client, "auditrun", department="CS")

    audit_run = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "appraisal_computed",
            AuditLog.actor_id == faculty_user.id,
        )
    )
    assert audit_run is not None
    assert audit_run.entity_type == "faculty_appraisal_run"
    assert "total_score" in audit_run.after


# ==============================================================================
# SEC-04: JWT secret configuration validation
# ==============================================================================

def test_jwt_secret_validation_in_production():
    # Production with default dev secret must be rejected
    with pytest.raises(ValueError, match="Default development JWT secret cannot be used in production"):
        Settings(
            app_env="production",
            jwt_secret="insecure-phase2-dev-secret-change-in-env",
            _env_file=None,
        )

    # Production with short secret (< 32 bytes) must be rejected
    with pytest.raises(ValueError, match="must be at least 32 bytes"):
        Settings(
            app_env="production",
            jwt_secret="too-short-secret-key",
            _env_file=None,
        )

    # Production with valid 32+ char secret succeeds
    valid_prod = Settings(
        app_env="production",
        jwt_secret="a" * 32,
        _env_file=None,
    )
    assert valid_prod.jwt_secret == "a" * 32

    # Development environment allows default secret for smooth developer workflow
    dev_settings = Settings(
        app_env="development",
        jwt_secret="insecure-phase2-dev-secret-change-in-env",
        _env_file=None,
    )
    assert dev_settings.app_env == "development"


# ==============================================================================
# SEC-07: HTML escaping in generated appraisal reports
# ==============================================================================

def test_html_report_escaping_xss():
    malicious_faculty = {
        "full_name": "<script>alert('xss-name')</script>",
        "email": 'user" onfocus="alert(1)"@demo.local',
    }
    malicious_cycle = {
        "name": "<img src=x onerror=alert('xss-cycle')>",
        "academic_year": "2026-2027",
    }
    malicious_approval = {
        "status": "rejected",
        "reviewer": "<svg/onload=alert('xss-reviewer')>",
        "decided_at": "2026-10-12T10:00:00Z",
        "reason": "<b>Malicious Reason</b><script>fetch('//attacker.com')</script>",
        "comment": "<iframe src='javascript:alert(1)'></iframe>",
    }
    malicious_research_metrics = {
        "status": "unavailable",
        "error_category": "<script>alert('scholar-xss')</script>",
    }

    result = build_report(
        profile=malicious_faculty,
        cycle=malicious_cycle,
        activities=[],
        evidence=[],
        score={
            "total": 50,
            "rating_recommendation": "B",
            "category_totals": {},
            "line_items": [
                {
                    "label": "<b onmouseover=alert('item')>Bad Item</b>",
                    "value": "<script>bad()</script>",
                    "points": 10,
                }
            ],
        },
        approval=malicious_approval,
        research_metrics=malicious_research_metrics,
    )

    html = result["html"]

    # Verify no raw unescaped HTML tags from malicious input
    assert "<script>" not in html
    assert "</script>" not in html
    assert "<img src=x" not in html
    assert "<svg/onload" not in html
    assert "<iframe" not in html
    assert "<b onmouseover" not in html

    # Verify HTML entities are escaped properly into safe text representation
    assert "&lt;script&gt;alert(&#x27;xss-name&#x27;)&lt;/script&gt;" in html or "&lt;script&gt;" in html
    assert "&lt;img src=x" in html
    assert "&lt;b&gt;Malicious Reason&lt;/b&gt;" in html or "&lt;b&gt;" in html
    assert "&lt;iframe" in html
    assert "&lt;b onmouseover=" in html


# ==============================================================================
# SEC-08: Separation of Duties — Reviewer Self-Review Prohibitions
# ==============================================================================

def _make_reviewer_with_appraisal(db: Session, client, suffix: str, roles: list[str], department: str = "CS"):
    reviewer_user = make_user(db, f"rev-{suffix}@demo.local", roles)
    profile = FacultyProfile(
        user_id=reviewer_user.id,
        employee_code=f"REV-{suffix}",
        full_name=f"Reviewer {suffix}",
        department=department,
        designation="Professor & HOD" if "hod" in roles else "Professor",
        confidentiality_scope="self",
    )
    db.add(profile)
    cycle = make_cycle(db)
    activity = create_activity(
        db,
        faculty=profile,
        category="research",
        activity_type="publications",
        title=f"Publication {suffix}",
        description="Evidence-backed activity",
        activity_date=date(2026, 1, 1),
        extras={"venue": "Journal", "year": 2026},
    )
    db.flush()
    _attach_valid_evidence(db, activity.id, profile.id, cycle.id, suffix)
    db.commit()
    token = login(client, reviewer_user.email)
    run_resp = client.post("/api/v1/appraisals/run", headers=auth_headers(token))
    assert run_resp.status_code == 200, run_resp.text
    return profile, reviewer_user, token


def test_hod_cannot_self_review_approve_or_modify_own_appraisal(client, db_session: Session):
    hod_profile, hod_user, hod_token = _make_reviewer_with_appraisal(
        db_session, client, "sec08hod", roles=["hod"], department="CS"
    )

    # 1. Self-approval is denied with 403 Forbidden
    approve_resp = client.post(
        f"/api/v1/review/faculty/{hod_profile.id}/approve",
        headers=auth_headers(hod_token),
        json={"reason": "Self approval attempt"},
    )
    assert approve_resp.status_code == 403
    assert "Separation of duties violation" in approve_resp.json()["detail"]

    # 2. Self-rejection is denied with 403 Forbidden
    reject_resp = client.post(
        f"/api/v1/review/faculty/{hod_profile.id}/reject",
        headers=auth_headers(hod_token),
        json={"reason": "Self reject attempt"},
    )
    assert reject_resp.status_code == 403
    assert "Separation of duties violation" in reject_resp.json()["detail"]

    # 3. Self-request-changes is denied with 403 Forbidden
    changes_resp = client.post(
        f"/api/v1/review/faculty/{hod_profile.id}/request-changes",
        headers=auth_headers(hod_token),
        json={"reason": "Self changes attempt"},
    )
    assert changes_resp.status_code == 403
    assert "Separation of duties violation" in changes_resp.json()["detail"]

    # 4. Self-edit is denied with 403 Forbidden
    edit_resp = client.patch(
        f"/api/v1/review/faculty/{hod_profile.id}/report/edit",
        headers=auth_headers(hod_token),
        json={"rating_recommendation": "A+"},
    )
    assert edit_resp.status_code == 403
    assert "Separation of duties violation" in edit_resp.json()["detail"]

    # 5. Self-override is denied with 403 Forbidden
    override_resp = client.post(
        f"/api/v1/review/faculty/{hod_profile.id}/report/override",
        headers=auth_headers(hod_token),
        json={"reason": "Self override attempt", "total_score": 99.0},
    )
    assert override_resp.status_code == 403
    assert "Separation of duties violation" in override_resp.json()["detail"]

    # 6. Self-rollback is denied with 403 Forbidden
    rollback_resp = client.post(
        f"/api/v1/review/faculty/{hod_profile.id}/report/rollback",
        headers=auth_headers(hod_token),
        json={"version_id": "dummy-version", "reason": "Self rollback attempt"},
    )
    assert rollback_resp.status_code == 403
    assert "Separation of duties violation" in rollback_resp.json()["detail"]

    # 7. Self-publish is denied with 403 Forbidden
    publish_resp = client.post(
        f"/api/v1/review/faculty/{hod_profile.id}/report/publish",
        headers=auth_headers(hod_token),
    )
    assert publish_resp.status_code == 403
    assert "Separation of duties violation" in publish_resp.json()["detail"]


def test_admin_and_dean_cannot_self_review_approve_override_or_publish_own_appraisal(client, db_session: Session):
    admin_profile, admin_user, admin_token = _make_reviewer_with_appraisal(
        db_session, client, "sec08admin", roles=["admin"], department="EE"
    )
    dean_profile, dean_user, dean_token = _make_reviewer_with_appraisal(
        db_session, client, "sec08dean", roles=["dean"], department="ME"
    )

    # Admin self-actions fail with 403
    admin_approve = client.post(
        f"/api/v1/review/faculty/{admin_profile.id}/approve",
        headers=auth_headers(admin_token),
    )
    assert admin_approve.status_code == 403
    assert "Separation of duties violation" in admin_approve.json()["detail"]

    admin_override = client.post(
        f"/api/v1/review/faculty/{admin_profile.id}/report/override",
        headers=auth_headers(admin_token),
        json={"reason": "Admin self override", "total_score": 100},
    )
    assert admin_override.status_code == 403
    assert "Separation of duties violation" in admin_override.json()["detail"]

    admin_publish = client.post(
        f"/api/v1/review/faculty/{admin_profile.id}/report/publish",
        headers=auth_headers(admin_token),
    )
    assert admin_publish.status_code == 403
    assert "Separation of duties violation" in admin_publish.json()["detail"]

    admin_edit = client.patch(
        f"/api/v1/review/faculty/{admin_profile.id}/report/edit",
        headers=auth_headers(admin_token),
        json={"rating_recommendation": "A+"},
    )
    assert admin_edit.status_code == 403
    assert "Separation of duties violation" in admin_edit.json()["detail"]

    # Dean self-actions fail with 403
    dean_approve = client.post(
        f"/api/v1/review/faculty/{dean_profile.id}/approve",
        headers=auth_headers(dean_token),
    )
    assert dean_approve.status_code == 403
    assert "Separation of duties violation" in dean_approve.json()["detail"]

    dean_override = client.post(
        f"/api/v1/review/faculty/{dean_profile.id}/report/override",
        headers=auth_headers(dean_token),
        json={"reason": "Dean self override", "total_score": 95},
    )
    assert dean_override.status_code == 403
    assert "Separation of duties violation" in dean_override.json()["detail"]

    dean_publish = client.post(
        f"/api/v1/review/faculty/{dean_profile.id}/report/publish",
        headers=auth_headers(dean_token),
    )
    assert dean_publish.status_code == 403
    assert "Separation of duties violation" in dean_publish.json()["detail"]


def test_authorized_reviewer_can_review_and_publish_another_faculty_member(client, db_session: Session):
    # Faculty in CS
    fac_profile, fac_user, fac_token = _make_reviewer_with_appraisal(
        db_session, client, "sec08fac", roles=["faculty"], department="CS"
    )

    # Independent HOD in CS
    hod_user = make_user(db_session, "hod-second@demo.local", ["hod"])
    hod_profile = FacultyProfile(
        user_id=hod_user.id,
        employee_code="HOD-SEC-02",
        full_name="Second HOD CS",
        department="CS",
        designation="Professor & HOD",
        confidentiality_scope="self",
    )
    db_session.add(hod_profile)

    # Independent Dean
    dean_user = make_user(db_session, "dean-second@demo.local", ["dean"])
    db_session.commit()

    hod_token = login(client, "hod-second@demo.local")
    dean_token = login(client, "dean-second@demo.local")

    # 1. Independent HOD can approve another faculty member's appraisal
    approve_resp = client.post(
        f"/api/v1/review/faculty/{fac_profile.id}/approve",
        headers=auth_headers(hod_token),
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # 2. The faculty member themselves cannot publish their now-approved appraisal
    self_publish_resp = client.post(
        f"/api/v1/review/faculty/{fac_profile.id}/report/publish",
        headers=auth_headers(fac_token),
    )
    assert self_publish_resp.status_code == 403

    # 3. Independent Dean can publish the approved appraisal
    publish_resp = client.post(
        f"/api/v1/review/faculty/{fac_profile.id}/report/publish",
        headers=auth_headers(dean_token),
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["status"] == "published"


# ==============================================================================
# SEC-09: Admin Audit Logging — Appraisal Cycle Operations
# ==============================================================================

def test_admin_cycle_lifecycle_audit_logging(client, db_session: Session):
    admin_user = make_user(db_session, "admin-sec09@demo.local", ["admin"])
    db_session.commit()
    token = login(client, admin_user.email)

    # 1. Admin creates cycle with status='draft'
    create_resp = client.post(
        "/api/v1/admin/cycles",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "name": "Audit Test Cycle 2026",
            "academic_year": "2026-2027",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "draft",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    cycle_id = create_resp.json()["id"]

    logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == cycle_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(logs) == 1
    log1 = logs[0]
    assert log1.action == "cycle_created"
    assert log1.entity_type == "appraisal_cycle"
    assert log1.actor_id == admin_user.id
    assert log1.before is None
    assert log1.after == {
        "name": "Audit Test Cycle 2026",
        "academic_year": "2026-2027",
        "status": "draft",
        "starts_on": "2026-01-01",
        "ends_on": "2026-12-31",
    }

    # 2. Admin opens the draft cycle
    open_resp = client.patch(
        f"/api/v1/admin/cycles/{cycle_id}/open",
        headers=auth_headers(token),
    )
    assert open_resp.status_code == 200, open_resp.text
    assert open_resp.json()["status"] == "open"

    logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == cycle_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(logs) == 2
    log2 = logs[1]
    assert log2.action == "cycle_opened"
    assert log2.entity_type == "appraisal_cycle"
    assert log2.actor_id == admin_user.id
    assert log2.before == {"status": "draft"}
    assert log2.after == {"status": "open"}

    # 3. Admin closes the open cycle
    close_resp = client.patch(
        f"/api/v1/admin/cycles/{cycle_id}/close",
        headers=auth_headers(token),
    )
    assert close_resp.status_code == 200, close_resp.text
    assert close_resp.json()["status"] == "closed"

    logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == cycle_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(logs) == 3
    log3 = logs[2]
    assert log3.action == "cycle_closed"
    assert log3.entity_type == "appraisal_cycle"
    assert log3.actor_id == admin_user.id
    assert log3.before == {"status": "open"}
    assert log3.after == {"status": "closed"}

    # 4. Admin reopens the closed cycle
    reopen_resp = client.patch(
        f"/api/v1/admin/cycles/{cycle_id}/open",
        headers=auth_headers(token),
    )
    assert reopen_resp.status_code == 200, reopen_resp.text
    assert reopen_resp.json()["status"] == "open"

    logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == cycle_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(logs) == 4
    log4 = logs[3]
    assert log4.action == "cycle_opened"
    assert log4.entity_type == "appraisal_cycle"
    assert log4.actor_id == admin_user.id
    assert log4.before == {"status": "closed"}
    assert log4.after == {"status": "open"}

    # 5. Idempotent open on already-open cycle produces zero duplicate audit logs
    open_repeat = client.patch(
        f"/api/v1/admin/cycles/{cycle_id}/open",
        headers=auth_headers(token),
    )
    assert open_repeat.status_code == 200
    logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == cycle_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(logs) == 4

    # 6. Close and idempotent close produce exactly 1 additional audit log (5 total)
    close_repeat1 = client.patch(
        f"/api/v1/admin/cycles/{cycle_id}/close",
        headers=auth_headers(token),
    )
    assert close_repeat1.status_code == 200
    logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == cycle_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(logs) == 5

    close_repeat2 = client.patch(
        f"/api/v1/admin/cycles/{cycle_id}/close",
        headers=auth_headers(token),
    )
    assert close_repeat2.status_code == 200
    logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == cycle_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(logs) == 5

    # 7. Verify cryptographic audit chain integrity
    chain_result = verify_audit_log_chain(db_session)
    assert chain_result["is_valid"] is True
    assert chain_result["violation"] is None
    assert chain_result["total_records"] >= 5


def test_admin_open_cycle_auto_closes_existing_audit_logging(client, db_session: Session):
    admin_user = make_user(db_session, "admin-autoclose@demo.local", ["admin"])
    db_session.commit()
    token = login(client, admin_user.email)

    # 1. Admin creates Cycle 1 as open
    r1 = client.post(
        "/api/v1/admin/cycles",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "name": "Cycle 1 Open",
            "academic_year": "2025-2026",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "status": "open",
        },
    )
    assert r1.status_code == 200, r1.text
    c1_id = r1.json()["id"]

    # 2. Admin creates Cycle 2 as draft
    r2 = client.post(
        "/api/v1/admin/cycles",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "name": "Cycle 2 Draft",
            "academic_year": "2026-2027",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "draft",
        },
    )
    assert r2.status_code == 200, r2.text
    c2_id = r2.json()["id"]

    # 3. Admin opens Cycle 2 -> Cycle 1 must auto-close with superseded_by recorded
    r_open2 = client.patch(
        f"/api/v1/admin/cycles/{c2_id}/open",
        headers=auth_headers(token),
    )
    assert r_open2.status_code == 200, r_open2.text
    assert r_open2.json()["status"] == "open"

    # Predecessor Cycle 1 logs
    c1_logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == c1_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(c1_logs) == 2
    assert c1_logs[0].action == "cycle_created"
    assert c1_logs[1].action == "cycle_closed"
    assert c1_logs[1].actor_id == admin_user.id
    assert c1_logs[1].before == {"status": "open"}
    assert c1_logs[1].after == {"status": "closed", "superseded_by": c2_id}

    # Cycle 2 logs
    c2_logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == c2_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(c2_logs) == 2
    assert c2_logs[0].action == "cycle_created"
    assert c2_logs[1].action == "cycle_opened"
    assert c2_logs[1].actor_id == admin_user.id
    assert c2_logs[1].before == {"status": "draft"}
    assert c2_logs[1].after == {"status": "open"}

    # 4. Admin creates Cycle 3 directly as open -> Cycle 2 must auto-close with superseded_by recorded
    r3 = client.post(
        "/api/v1/admin/cycles",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "name": "Cycle 3 Direct Open",
            "academic_year": "2027-2028",
            "start_date": "2027-01-01",
            "end_date": "2027-12-31",
            "status": "open",
        },
    )
    assert r3.status_code == 200, r3.text
    c3_id = r3.json()["id"]

    c2_logs_updated = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == c2_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(c2_logs_updated) == 3
    assert c2_logs_updated[2].action == "cycle_closed"
    assert c2_logs_updated[2].actor_id == admin_user.id
    assert c2_logs_updated[2].before == {"status": "open"}
    assert c2_logs_updated[2].after == {"status": "closed", "superseded_by": c3_id}

    c3_logs = list(
        db_session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == c3_id)
            .order_by(AuditLog.sequence_number.asc())
        )
    )
    assert len(c3_logs) == 1
    assert c3_logs[0].action == "cycle_created"
    assert c3_logs[0].actor_id == admin_user.id
    assert c3_logs[0].after["status"] == "open"

    # Verify chain
    chain_result = verify_audit_log_chain(db_session)
    assert chain_result["is_valid"] is True


def test_both_cycle_creation_endpoints_produce_audit_logs(client, db_session: Session):
    admin_user = make_user(db_session, "admin-dualendpoints@demo.local", ["admin"])
    db_session.commit()
    token = login(client, admin_user.email)

    # Endpoint 1: POST /api/v1/admin/cycles
    resp_admin = client.post(
        "/api/v1/admin/cycles",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "name": "From Admin Route",
            "academic_year": "2026-2027",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "draft",
        },
    )
    assert resp_admin.status_code == 200, resp_admin.text
    admin_cycle_id = resp_admin.json()["id"]

    # Endpoint 2: POST /api/v1/cycles
    resp_cycles = client.post(
        "/api/v1/cycles",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "name": "From Cycles Route",
            "academic_year": "2026-2027",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "draft",
        },
    )
    assert resp_cycles.status_code == 200, resp_cycles.text
    cycles_cycle_id = resp_cycles.json()["id"]

    # Verify both endpoints produced audited cycle_created records with identical actor attribution
    log_admin = db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == admin_cycle_id,
            AuditLog.action == "cycle_created",
        )
    )
    assert log_admin is not None
    assert log_admin.actor_id == admin_user.id
    assert log_admin.after["name"] == "From Admin Route"

    log_cycles = db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == cycles_cycle_id,
            AuditLog.action == "cycle_created",
        )
    )
    assert log_cycles is not None
    assert log_cycles.actor_id == admin_user.id
    assert log_cycles.after["name"] == "From Cycles Route"


def test_unauthorized_user_cannot_mutate_cycles_or_generate_audit_logs(client, db_session: Session):
    faculty_user = make_user(db_session, "faculty-unauth-sec09@demo.local", ["faculty"])
    draft_cycle = make_cycle(db_session, status="draft")
    db_session.commit()
    token = login(client, faculty_user.email)

    # 1. Faculty cannot create cycle via /admin/cycles
    r1 = client.post(
        "/api/v1/admin/cycles",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "name": "Unauthorized Cycle",
            "academic_year": "2026-2027",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "draft",
        },
    )
    assert r1.status_code in (401, 403)

    # 2. Faculty cannot create cycle via /cycles
    r2 = client.post(
        "/api/v1/cycles",
        headers={**auth_headers(token), "Content-Type": "application/json"},
        json={
            "name": "Unauthorized Cycle 2",
            "academic_year": "2026-2027",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "draft",
        },
    )
    assert r2.status_code in (401, 403)

    # 3. Faculty cannot open cycle
    r3 = client.patch(
        f"/api/v1/admin/cycles/{draft_cycle.id}/open",
        headers=auth_headers(token),
    )
    assert r3.status_code in (401, 403)

    # 4. Faculty cannot close cycle
    r4 = client.patch(
        f"/api/v1/admin/cycles/{draft_cycle.id}/close",
        headers=auth_headers(token),
    )
    assert r4.status_code in (401, 403)

    # Verify no audit logs were generated by this faculty user or for draft_cycle
    user_cycle_logs = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.actor_id == faculty_user.id,
                AuditLog.entity_type == "appraisal_cycle",
            )
        )
    )
    assert len(user_cycle_logs) == 0

    draft_cycle_logs = list(
        db_session.scalars(
            select(AuditLog).where(AuditLog.entity_id == str(draft_cycle.id))
        )
    )
    assert len(draft_cycle_logs) == 0
