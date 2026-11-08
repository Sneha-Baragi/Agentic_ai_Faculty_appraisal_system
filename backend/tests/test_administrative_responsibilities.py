from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import collect_admin
from app.models import Evidence, FacultyActivity
from app.services.activities import activity_to_dict
from app.services.administrative_responsibilities import list_administrative_responsibilities

from .conftest import auth_headers, login, make_cycle, make_faculty_profile, make_user


def test_responsibility_create_list_and_cycle_association(client, db_session: Session):
    user = make_user(db_session, "admin-responsibility@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    cycle = make_cycle(db_session)
    db_session.commit()
    token = login(client, user.email)

    created_ids = []
    for role, unit in [
        ("Department Association Coordinator", "Computer Science"),
        ("Sports Coordinator", "Institution"),
        ("Examination Coordinator", "Computer Science"),
    ]:
        response = client.post(
            "/api/v1/administrative-responsibilities",
            headers=auth_headers(token),
            json={
                "role": role,
                "organizational_unit": unit,
                "description": "Institutional coordination duties",
                "start_date": "2026-08-01",
                "end_date": "2027-05-31",
                "evidence_reference": "Annual activity report",
            },
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["id"])
        assert response.json()["academic_year"] == cycle.academic_year
        assert response.json()["appraisal_cycle_id"] == str(cycle.id)

    listed = client.get("/api/v1/administrative-responsibilities", headers=auth_headers(token))
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == set(created_ids)
    assert {item["role"] for item in listed.json()} == {
        "Department Association Coordinator",
        "Sports Coordinator",
        "Examination Coordinator",
    }
    assert all(item["start_date"] == date(2026, 8, 1).isoformat() for item in listed.json())

    records = list_administrative_responsibilities(db_session, faculty_id=profile.id, cycle_id=cycle.id)
    assert len(records) == 3
    assert all(item["appraisal_cycle_id"] == str(cycle.id) for item in records)


def test_responsibility_evidence_retrieval_and_admin_collection(client, db_session: Session):
    user = make_user(db_session, "admin-evidence@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    cycle = make_cycle(db_session)
    db_session.commit()
    token = login(client, user.email)
    response = client.post(
        "/api/v1/administrative-responsibilities",
        headers=auth_headers(token),
        json={"role": "Placement Coordinator", "description": "Placement support"},
    )
    assert response.status_code == 201, response.text
    activity_id = UUID(response.json()["id"])

    evidence = Evidence(
        activity_id=activity_id,
        faculty_id=profile.id,
        cycle_id=cycle.id,
        kind="pdf",
        original_filename="placement-report.pdf",
        validation_status="valid",
        extraction_status="extracted",
    )
    db_session.add(evidence)
    db_session.commit()

    evidence_response = client.get(
        f"/api/v1/administrative-responsibilities/{activity_id}/evidence",
        headers=auth_headers(token),
    )
    assert evidence_response.status_code == 200
    assert evidence_response.json()[0]["id"] == str(evidence.id)
    assert evidence_response.json()[0]["validation_status"] == "valid"

    activity = db_session.scalar(
        select(FacultyActivity).where(FacultyActivity.id == activity_id)
    )
    assert activity is not None
    collected = collect_admin({"all_activities": [activity_to_dict(activity)]})
    assert collected["raw_admin"][0]["id"] == str(activity_id)
    assert collected["raw_admin"][0]["evidence_statuses"] == ["valid"]


def test_responsibility_text_reference_does_not_create_evidence_record(client, db_session: Session):
    user = make_user(db_session, "admin-reference@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    make_cycle(db_session)
    db_session.commit()
    token = login(client, user.email)

    response = client.post(
        "/api/v1/administrative-responsibilities",
        headers=auth_headers(token),
        json={
            "role": "Appointment Coordinator",
            "description": "Coordination work",
            "evidence_reference": "Appointment letter",
        },
    )
    assert response.status_code == 201, response.text
    activity_id = UUID(response.json()["id"])

    evidence_rows = db_session.scalars(select(Evidence).where(Evidence.activity_id == activity_id)).all()
    assert evidence_rows == []

    activity = db_session.scalar(select(FacultyActivity).where(FacultyActivity.id == activity_id))
    assert activity is not None
    assert getattr(activity, "evidence", None) in ([], None)


def test_responsibility_file_upload_creates_evidence_record(client, db_session: Session):
    user = make_user(db_session, "admin-upload@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    make_cycle(db_session)
    db_session.commit()
    token = login(client, user.email)

    created = client.post(
        "/api/v1/administrative-responsibilities",
        headers=auth_headers(token),
        json={"role": "Exam Coordinator", "description": "Exam duty"},
    )
    assert created.status_code == 201, created.text
    activity_id = UUID(created.json()["id"])

    upload = client.post(
        f"/api/v1/evidence?activity_id={activity_id}",
        headers=auth_headers(token),
        files={"file": ("appointment-letter.pdf", b"%PDF-1.4\n%fake\n", "application/pdf")},
        data={"activity_id": str(activity_id)},
    )
    assert upload.status_code == 201, upload.text
    payload = upload.json()
    assert payload["activity_id"] == str(activity_id)
    assert payload["original_filename"] == "appointment-letter.pdf"

    evidence_rows = db_session.scalars(select(Evidence).where(Evidence.activity_id == activity_id)).all()
    assert len(evidence_rows) == 1
    assert evidence_rows[0].original_filename == "appointment-letter.pdf"

    activity = db_session.scalar(select(FacultyActivity).where(FacultyActivity.id == activity_id))
    assert activity is not None
    assert len(list(activity.evidence or [])) == 1


def test_responsibilities_are_scoped_to_authenticated_faculty(client, db_session: Session):
    owner = make_user(db_session, "admin-owner@demo.local", ["faculty"])
    make_faculty_profile(db_session, owner)
    other = make_user(db_session, "admin-other@demo.local", ["faculty"])
    make_faculty_profile(db_session, other)
    make_cycle(db_session)
    db_session.commit()

    owner_token = login(client, owner.email)
    other_token = login(client, other.email)
    created = client.post(
        "/api/v1/administrative-responsibilities",
        headers=auth_headers(owner_token),
        json={"role": "NSS Coordinator"},
    )
    assert created.status_code == 201

    other_list = client.get("/api/v1/administrative-responsibilities", headers=auth_headers(other_token))
    assert other_list.status_code == 200
    assert other_list.json() == []
    denied = client.get(
        f"/api/v1/administrative-responsibilities/{created.json()['id']}/evidence",
        headers=auth_headers(other_token),
    )
    assert denied.status_code == 404


def test_responsibility_requires_authentication_and_valid_dates(client, db_session: Session):
    unauthorized = client.get("/api/v1/administrative-responsibilities")
    assert unauthorized.status_code == 401

    user = make_user(db_session, "admin-dates@demo.local", ["faculty"])
    make_faculty_profile(db_session, user)
    make_cycle(db_session)
    db_session.commit()
    token = login(client, user.email)
    invalid_dates = client.post(
        "/api/v1/administrative-responsibilities",
        headers=auth_headers(token),
        json={"role": "Class Coordinator", "start_date": "2027-05-31", "end_date": "2026-08-01"},
    )
    assert invalid_dates.status_code == 422