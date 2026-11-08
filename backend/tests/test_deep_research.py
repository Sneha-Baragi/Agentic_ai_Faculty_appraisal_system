import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Evidence, FacultyActivity, FacultyAppraisalRun
from app.services.appraisals import run_appraisal
from app.services.cycles import get_or_create_run
from app.services.deep_research import run_deep_research_verification, verify_research_claim
from app.scoring.engine import calculate_score, load_demo_rubric
from .conftest import make_cycle, make_faculty_profile, make_user


def test_deep_research_matching_claim():
    claim = {
        "title": "Deep Learning for Genomic Sequences",
        "year": 2025,
        "venue": "IEEE Transactions on Pattern Analysis",
        "evidence_ids": ["ev-123"],
    }
    scholar_metrics = {
        "status": "retrieved",
        "scholar_id": "scholar123",
        "publications": [
            {
                "title": "Deep Learning for Genomic Sequences",
                "year": 2025,
                "publication": "IEEE Transactions on Pattern Analysis",
                "citation_count": 12,
            }
        ],
    }
    evidence_summary = [
        {
            "id": "ev-123",
            "filename": "paper_pdf.pdf",
            "validation_status": "valid",
        }
    ]

    result = verify_research_claim(
        claim=claim,
        scholar_metrics=scholar_metrics,
        evidence_summary=evidence_summary,
    )

    assert result["status"] == "verified"
    assert result["confidence"] == 1.0
    assert result["human_review_required"] is False
    assert len(result["discrepancies"]) == 0
    assert "google_scholar_author" in result["sources_consulted"]
    assert "paper_pdf.pdf" in result["supporting_evidence_references"]


def test_deep_research_title_mismatch():
    claim = {
        "title": "Quantum Computing Applications in Bio-Informatics",
        "year": 2025,
    }
    scholar_metrics = {
        "status": "retrieved",
        "publications": [
            {
                "title": "Deep Learning for Genomic Sequences",
                "year": 2025,
            }
        ],
    }

    result = verify_research_claim(
        claim=claim,
        scholar_metrics=scholar_metrics,
        evidence_summary=[{"id": "ev-1", "filename": "doc.pdf", "validation_status": "valid"}],
    )

    assert result["status"] == "unverified"
    assert result["confidence"] == 0.0
    assert result["human_review_required"] is True


def test_deep_research_year_mismatch():
    claim = {
        "title": "Deep Learning for Genomic Sequences",
        "year": 2026,
    }
    scholar_metrics = {
        "status": "retrieved",
        "publications": [
            {
                "title": "Deep Learning for Genomic Sequences",
                "year": 2024,
            }
        ],
    }
    evidence_summary = [{"id": "ev-1", "filename": "paper.pdf", "validation_status": "valid"}]

    result = verify_research_claim(
        claim=claim,
        scholar_metrics=scholar_metrics,
        evidence_summary=evidence_summary,
    )

    assert result["status"] == "discrepant"
    assert result["confidence"] == 0.5
    assert result["human_review_required"] is True
    assert len(result["discrepancies"]) > 0
    assert "2026" in result["discrepancies"][0]
    assert "2024" in result["discrepancies"][0]


def test_deep_research_missing_evidence():
    claim = {
        "title": "Deep Learning for Genomic Sequences",
        "year": 2025,
    }
    scholar_metrics = {
        "status": "retrieved",
        "publications": [
            {
                "title": "Deep Learning for Genomic Sequences",
                "year": 2025,
            }
        ],
    }

    # No valid evidence provided
    result = verify_research_claim(
        claim=claim,
        scholar_metrics=scholar_metrics,
        evidence_summary=[],
    )

    assert result["status"] == "unverified"
    assert result["confidence"] == 0.0
    assert result["human_review_required"] is True


def test_deep_research_failed_scholar_retrieval():
    claim = {
        "title": "Deep Learning for Genomic Sequences",
        "year": 2025,
    }
    scholar_metrics = {
        "status": "unavailable",
        "error_category": "provider_timeout",
        "publications": [],
    }
    evidence_summary = [{"id": "ev-1", "filename": "paper.pdf", "validation_status": "valid"}]

    result = verify_research_claim(
        claim=claim,
        scholar_metrics=scholar_metrics,
        evidence_summary=evidence_summary,
    )

    assert result["status"] == "unverified"
    assert result["confidence"] == 0.0
    assert result["human_review_required"] is True


def test_deep_research_scholar_identity_mismatch():
    claim = {
        "title": "Deep Learning for Genomic Sequences",
        "year": 2025,
    }
    scholar_metrics = {
        "status": "unavailable",
        "error_category": "identity_unverified",
        "publications": [],
    }

    result = verify_research_claim(
        claim=claim,
        scholar_metrics=scholar_metrics,
        evidence_summary=[{"id": "ev-1", "filename": "paper.pdf", "validation_status": "valid"}],
    )

    assert result["status"] == "unverified"
    assert result["human_review_required"] is True


def test_deep_research_ambiguous_venue():
    claim = {
        "title": "Deep Learning for Genomic Sequences",
        "year": 2025,
        "venue": "ACM Computing Surveys",
    }
    scholar_metrics = {
        "status": "retrieved",
        "publications": [
            {
                "title": "Deep Learning for Genomic Sequences",
                "year": 2025,
                "publication": "IEEE Transactions on Pattern Analysis",
            }
        ],
    }

    result = verify_research_claim(
        claim=claim,
        scholar_metrics=scholar_metrics,
        evidence_summary=[{"id": "ev-1", "filename": "paper.pdf", "validation_status": "valid"}],
    )

    assert result["status"] == "discrepant"
    assert result["human_review_required"] is True
    assert any("Venue mismatch" in d for d in result["discrepancies"])


def test_deep_research_confidence_and_status_consistency():
    # Verified -> 1.0 confidence, human_review_required False
    v_res = verify_research_claim(
        claim={"title": "Test Paper", "year": 2025},
        scholar_metrics={"status": "retrieved", "publications": [{"title": "Test Paper", "year": 2025}]},
        evidence_summary=[{"id": "ev1", "filename": "test.pdf", "validation_status": "valid"}],
    )
    assert v_res["status"] == "verified"
    assert v_res["confidence"] == 1.0
    assert v_res["human_review_required"] is False

    # Discrepant -> 0.5 confidence, human_review_required True
    d_res = verify_research_claim(
        claim={"title": "Test Paper", "year": 2025},
        scholar_metrics={"status": "retrieved", "publications": [{"title": "Test Paper", "year": 2024}]},
        evidence_summary=[{"id": "ev1", "filename": "test.pdf", "validation_status": "valid"}],
    )
    assert d_res["status"] == "discrepant"
    assert d_res["confidence"] == 0.5
    assert d_res["human_review_required"] is True

    # Unverified -> 0.0 confidence, human_review_required True
    u_res = verify_research_claim(
        claim={"title": "Test Paper", "year": 2025},
        scholar_metrics={"status": "unavailable"},
        evidence_summary=[],
    )
    assert u_res["status"] == "unverified"
    assert u_res["confidence"] == 0.0
    assert u_res["human_review_required"] is True


def test_deep_research_provenance_preservation():
    result = verify_research_claim(
        claim={"title": "Sample Title", "year": 2025},
        scholar_metrics={"status": "retrieved", "publications": [{"title": "Sample Title", "year": 2025}]},
        evidence_summary=[{"id": "ev1", "filename": "proof.pdf", "validation_status": "valid"}],
    )
    assert "sources_consulted" in result
    assert "activity_record" in result["sources_consulted"]
    assert "google_scholar_author" in result["sources_consulted"]
    assert "activity_evidence_vault" in result["sources_consulted"]
    assert "supporting_evidence_references" in result
    assert "proof.pdf" in result["supporting_evidence_references"]
    assert "retrieved_at" in result
    assert isinstance(result["retrieved_at"], str)


def test_deep_research_audit_logging(client, db_session: Session):
    user = make_user(db_session, "audit_deep@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    make_cycle(db_session)
    db_session.commit()

    run_appraisal(db_session, faculty=profile)
    db_session.commit()

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "appraisal_deep_research_verification")
    ).all()
    assert len(logs) >= 1
    log = logs[0]
    assert log.actor_id == user.id
    assert log.entity_id == str(profile.id)
    assert "analyzed_claims" in log.after


def test_deep_research_faculty_data_isolation(client, db_session: Session):
    user1 = make_user(db_session, "faculty1@demo.local", ["faculty"])
    profile1 = make_faculty_profile(db_session, user1, employee_code="F-ISO-1")
    user2 = make_user(db_session, "faculty2@demo.local", ["faculty"])
    profile2 = make_faculty_profile(db_session, user2, employee_code="F-ISO-2")
    cycle = make_cycle(db_session)

    run1 = get_or_create_run(db_session, faculty=profile1, cycle=cycle)
    # Add activity for faculty 1
    act1 = FacultyActivity(
        run_id=run1.id,
        faculty_id=profile1.id,
        cycle_id=cycle.id,
        category="research",
        activity_type="publications",
        title="Faculty 1 Secret Research",
    )
    db_session.add(act1)
    db_session.commit()

    # Run for faculty 2
    res2 = run_appraisal(db_session, faculty=profile2)
    report2 = res2["report"]

    deep_res = report2.report_json.get("deep_research_verification", {})
    claims = deep_res.get("claim_verifications", [])
    for claim in claims:
        assert "Faculty 1 Secret Research" not in claim["claim"]["title"]


def test_deep_research_no_duplicate_records(client, db_session: Session):
    user = make_user(db_session, "nodup@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    cycle = make_cycle(db_session)

    act_count_before = len(db_session.scalars(select(FacultyActivity)).all())
    ev_count_before = len(db_session.scalars(select(Evidence)).all())

    run_appraisal(db_session, faculty=profile)

    act_count_after = len(db_session.scalars(select(FacultyActivity)).all())
    ev_count_after = len(db_session.scalars(select(Evidence)).all())

    assert act_count_before == act_count_after
    assert ev_count_before == ev_count_after


def test_deep_research_no_direct_score_mutation(client, db_session: Session):
    user = make_user(db_session, "noscore_mut@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    make_cycle(db_session)
    db_session.commit()

    res = run_appraisal(db_session, faculty=profile)
    score = res["score"]

    # Total score remains pure deterministic calculation (0.0 when no activities)
    assert score.total == 0.0


def test_existing_scholar_scoring_unchanged():
    rubric = load_demo_rubric()
    assert "journal_paper" in rubric["categories"]["research"]["items"]
    assert rubric["categories"]["research"]["items"]["journal_paper"]["points"] == 10


def test_existing_teaching_and_admin_scoring_unchanged():
    rubric = load_demo_rubric()
    assert "course_delivery" in rubric["categories"]["teaching"]["items"]
    assert "committee_role" in rubric["categories"]["administrative"]["items"]


def test_mcp_and_hitl_tests_preserved(client, db_session: Session):
    user = make_user(db_session, "hitl_preserve@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    make_cycle(db_session)
    db_session.commit()

    res = run_appraisal(db_session, faculty=profile)
    assert res["graph"]["awaiting_human"] is True
    assert res["score"].run_id is not None
