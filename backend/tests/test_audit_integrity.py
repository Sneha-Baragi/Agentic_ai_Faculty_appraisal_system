"""Focused tests for Lab 12 — SEC-06: Audit Log Integrity and Tamper Protection.

Verifies:
1. Automatic hash-chaining and sequencing on direct db.add(AuditLog(...)) and create_audit_entry.
2. Contiguous monotonic sequence numbering across multiple flushes and batches.
3. Chain verification algorithm detects untampered logs.
4. Detection of in-place payload alteration (ALTERED_RECORD_PAYLOAD).
5. Detection of deleted intermediate records (SEQUENCE_GAP).
6. Detection of broken predecessor linkages (BROKEN_PREDECESSOR_LINK).
7. Detection of missing record hash or sequence numbers.
8. Transaction rollback safety (uncommitted attempts leave no chain gaps).
9. Admin verification endpoint GET /api/v1/admin/audit/verify (RBAC and diagnostic payload).
10. Sensitive payload redaction in violation diagnostics.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.governance import AuditLog
from app.services.audit import (
    GENESIS_HASH,
    compute_audit_record_hash,
    create_audit_entry,
    verify_audit_log_chain,
)
from .conftest import auth_headers, login, make_user


def test_automatic_chain_sequencing_and_hashing(db_session: Session):
    """Test that audit records receive contiguous sequence numbers and valid SHA-256 links."""
    u1 = make_user(db_session, "audit-seq1@demo.local", ["faculty"])
    db_session.commit()

    # Insert 3 records in separate transactions
    log1 = create_audit_entry(
        db_session,
        actor_id=u1.id,
        action="profile_updated",
        entity_type="faculty_profile",
        entity_id=str(u1.id),
        before={"title": "Assistant"},
        after={"title": "Associate"},
    )
    db_session.commit()

    assert log1.sequence_number == 1
    assert log1.prev_hash == GENESIS_HASH
    assert len(log1.record_hash) == 64

    # Direct db.add should also be intercepted by before_flush hook
    log2 = AuditLog(
        actor_id=u1.id,
        action="activity_created",
        entity_type="faculty_activity",
        entity_id="act-123",
        before=None,
        after={"title": "Paper A"},
    )
    db_session.add(log2)
    db_session.commit()

    assert log2.sequence_number == 2
    assert log2.prev_hash == log1.record_hash
    assert len(log2.record_hash) == 64

    log3 = create_audit_entry(
        db_session,
        actor_id=u1.id,
        action="activity_updated",
        entity_type="faculty_activity",
        entity_id="act-123",
        before={"title": "Paper A"},
        after={"title": "Paper A Revised"},
    )
    db_session.commit()

    assert log3.sequence_number == 3
    assert log3.prev_hash == log2.record_hash

    # Verify entire chain is valid
    report = verify_audit_log_chain(db_session)
    assert report["is_valid"] is True
    assert report["total_records"] == 3
    assert report["verified_records"] == 3
    assert report["head_sequence"] == 3
    assert report["head_hash"] == log3.record_hash
    assert report["violation"] is None


def test_batch_inserts_in_single_flush_receive_ordered_chain(db_session: Session):
    """Test that multiple AuditLog records added in the same flush receive contiguous hashes."""
    u = make_user(db_session, "batch-audit@demo.local", ["reviewer"])
    db_session.commit()

    log_a = AuditLog(actor_id=u.id, action="batch_1", entity_type="test", entity_id="1")
    log_b = AuditLog(actor_id=u.id, action="batch_2", entity_type="test", entity_id="2")
    log_c = AuditLog(actor_id=u.id, action="batch_3", entity_type="test", entity_id="3")

    db_session.add_all([log_a, log_b, log_c])
    db_session.commit()

    assert log_a.sequence_number == 1
    assert log_b.sequence_number == 2
    assert log_c.sequence_number == 3

    assert log_a.prev_hash == GENESIS_HASH
    assert log_b.prev_hash == log_a.record_hash
    assert log_c.prev_hash == log_b.record_hash

    report = verify_audit_log_chain(db_session)
    assert report["is_valid"] is True
    assert report["total_records"] == 3


def test_tamper_detection_altered_payload(db_session: Session):
    """Test that modifying any field in a committed audit log is immediately detected."""
    u = make_user(db_session, "tamper-mod@demo.local", ["faculty"])
    db_session.commit()

    for i in range(1, 4):
        create_audit_entry(
            db_session,
            actor_id=u.id,
            action=f"action_{i}",
            entity_type="item",
            entity_id=str(i),
            after={"score": i * 10},
        )
        db_session.commit()

    # Pre-check: chain is valid
    assert verify_audit_log_chain(db_session)["is_valid"] is True

    # Malicious direct SQL update simulating tampering
    target_log = db_session.scalar(select(AuditLog).where(AuditLog.sequence_number == 2))
    assert target_log is not None

    db_session.execute(
        text("UPDATE audit_logs SET after = :tampered WHERE sequence_number = 2"),
        {"tampered": '{"score": 9999}'},
    )
    db_session.commit()
    db_session.expire_all()

    # Verification must fail with ALTERED_RECORD_PAYLOAD
    report = verify_audit_log_chain(db_session)
    assert report["is_valid"] is False
    assert report["violation"]["violation_type"] == "ALTERED_RECORD_PAYLOAD"
    assert report["violation"]["sequence_number"] == 2
    assert report["violation"]["record_id"] == str(target_log.id)
    assert "payload has been altered" in report["violation"]["details"]


def test_tamper_detection_deleted_record_gap(db_session: Session):
    """Test that deleting an intermediate record is detected as a sequence gap."""
    u = make_user(db_session, "tamper-del@demo.local", ["faculty"])
    db_session.commit()

    for i in range(1, 5):
        create_audit_entry(
            db_session,
            actor_id=u.id,
            action=f"event_{i}",
            entity_type="doc",
            entity_id=str(i),
        )
        db_session.commit()

    assert verify_audit_log_chain(db_session)["is_valid"] is True

    # Delete record #2 directly
    db_session.execute(text("DELETE FROM audit_logs WHERE sequence_number = 2"))
    db_session.commit()
    db_session.expire_all()

    report = verify_audit_log_chain(db_session)
    assert report["is_valid"] is False
    assert report["violation"]["violation_type"] == "SEQUENCE_GAP"
    assert report["violation"]["expected_sequence"] == 2
    assert report["violation"]["actual_sequence"] == 3


def test_tamper_detection_broken_predecessor_link(db_session: Session):
    """Test that tampering with prev_hash is detected as BROKEN_PREDECESSOR_LINK."""
    u = make_user(db_session, "tamper-link@demo.local", ["admin"])
    db_session.commit()

    for i in range(1, 4):
        create_audit_entry(db_session, actor_id=u.id, action=f"step_{i}", entity_type="ops")
        db_session.commit()

    # Tamper with prev_hash of record #3, recomputing its record_hash to match the fake prev_hash
    rec3 = db_session.scalar(select(AuditLog).where(AuditLog.sequence_number == 3))
    fake_prev = "f" * 64
    fake_hash = compute_audit_record_hash(
        sequence_number=3,
        prev_hash=fake_prev,
        created_at=rec3.created_at,
        actor_id=rec3.actor_id,
        action=rec3.action,
        entity_type=rec3.entity_type,
        entity_id=rec3.entity_id,
        before=rec3.before,
        after=rec3.after,
        ip=rec3.ip,
    )

    db_session.execute(
        text("UPDATE audit_logs SET prev_hash = :p, record_hash = :h WHERE sequence_number = 3"),
        {"p": fake_prev, "h": fake_hash},
    )
    db_session.commit()
    db_session.expire_all()

    report = verify_audit_log_chain(db_session)
    assert report["is_valid"] is False
    assert report["violation"]["violation_type"] == "BROKEN_PREDECESSOR_LINK"
    assert report["violation"]["sequence_number"] == 3


def test_tamper_detection_missing_hash_or_sequence(db_session: Session):
    """Test that records missing sequence_number or record_hash are flagged."""
    u = make_user(db_session, "tamper-missing@demo.local", ["admin"])
    db_session.commit()

    rec1 = create_audit_entry(db_session, actor_id=u.id, action="valid_first", entity_type="test")
    db_session.commit()

    # Insert a record with _skip_auto_hash to simulate a corrupted/unhashed row
    rogue = AuditLog(
        id=uuid.uuid4(),
        actor_id=u.id,
        action="unhashed_rogue",
        entity_type="test",
        sequence_number=2,
        prev_hash=rec1.record_hash,
        record_hash=None,
    )
    rogue._skip_auto_hash = True
    db_session.add(rogue)
    db_session.commit()

    report = verify_audit_log_chain(db_session)
    assert report["is_valid"] is False
    assert report["violation"]["violation_type"] == "MISSING_RECORD_HASH"
    assert report["violation"]["sequence_number"] == 2


def test_transaction_rollback_preserves_chain_integrity(db_session: Session):
    """Test that failed/rolled-back transactions do not produce sequence number gaps."""
    u = make_user(db_session, "rollback-user@demo.local", ["faculty"])
    db_session.commit()

    # 1. Successful commit
    create_audit_entry(db_session, actor_id=u.id, action="tx_success_1", entity_type="test")
    db_session.commit()

    # 2. Failed transaction with rollback
    try:
        create_audit_entry(db_session, actor_id=u.id, action="tx_aborted", entity_type="test")
        db_session.flush()
        # Simulate business logic failure
        raise RuntimeError("Simulated transaction abort")
    except RuntimeError:
        db_session.rollback()

    # 3. Subsequent successful commit
    create_audit_entry(db_session, actor_id=u.id, action="tx_success_2", entity_type="test")
    db_session.commit()

    rows = list(db_session.scalars(select(AuditLog).order_by(AuditLog.sequence_number.asc())))
    assert len(rows) == 2
    assert rows[0].sequence_number == 1
    assert rows[0].action == "tx_success_1"
    assert rows[1].sequence_number == 2
    assert rows[1].action == "tx_success_2"
    assert rows[1].prev_hash == rows[0].record_hash

    # Entire chain is valid with no gaps
    assert verify_audit_log_chain(db_session)["is_valid"] is True


def test_admin_verification_endpoint_rbac_and_output(client, db_session: Session):
    """Test GET /api/v1/admin/audit/verify endpoint authorization and response format."""
    admin_user = make_user(db_session, "admin-audit@demo.local", ["admin"])
    faculty_user = make_user(db_session, "faculty-audit@demo.local", ["faculty"])
    reviewer_user = make_user(db_session, "reviewer-audit@demo.local", ["reviewer"])
    db_session.commit()

    # Create several audit logs
    create_audit_entry(db_session, actor_id=faculty_user.id, action="login", entity_type="auth")
    create_audit_entry(db_session, actor_id=reviewer_user.id, action="review", entity_type="appraisal")
    db_session.commit()

    admin_token = login(client, "admin-audit@demo.local")
    faculty_token = login(client, "faculty-audit@demo.local")
    reviewer_token = login(client, "reviewer-audit@demo.local")

    # 1. Non-admin roles must be rejected with 403 Forbidden
    fac_resp = client.get("/api/v1/admin/audit/verify", headers=auth_headers(faculty_token))
    assert fac_resp.status_code == 403

    rev_resp = client.get("/api/v1/admin/audit/verify", headers=auth_headers(reviewer_token))
    assert rev_resp.status_code == 403

    # 2. Admin role gets 200 OK with verification report
    adm_resp = client.get("/api/v1/admin/audit/verify", headers=auth_headers(admin_token))
    assert adm_resp.status_code == 200
    data = adm_resp.json()
    assert data["is_valid"] is True
    assert data["total_records"] >= 2
    assert data["violation"] is None
    assert "verified successfully" in data["message"]


def test_admin_verification_endpoint_reports_tampering_without_leaking_payload(client, db_session: Session):
    """Test that admin endpoint identifies tampering without exposing sensitive payload data."""
    admin_user = make_user(db_session, "admin-diag@demo.local", ["admin"])
    secret_payload = {"ssn_or_private_note": "CONFIDENTIAL_DATA_12345"}
    create_audit_entry(
        db_session,
        actor_id=admin_user.id,
        action="sensitive_op",
        entity_type="payroll",
        after=secret_payload,
    )
    db_session.commit()

    # Tamper with the record directly
    db_session.execute(text("UPDATE audit_logs SET action = 'forged_op' WHERE sequence_number = 1"))
    db_session.commit()

    admin_token = login(client, "admin-diag@demo.local")
    resp = client.get("/api/v1/admin/audit/verify", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is False
    assert data["violation"]["violation_type"] == "ALTERED_RECORD_PAYLOAD"
    assert data["violation"]["sequence_number"] == 1

    # Ensure sensitive payload data is NOT leaked into the diagnostic response
    response_text = resp.text
    assert "CONFIDENTIAL_DATA_12345" not in response_text


def test_reject_caller_supplied_integrity_fields(db_session: Session):
    """Test that callers cannot manually supply sequence_number, prev_hash, or record_hash."""
    u = make_user(db_session, "reject-integrity@demo.local", ["faculty"])
    db_session.commit()

    # 1. Caller supplies sequence_number
    log_seq = AuditLog(actor_id=u.id, action="forged_seq", entity_type="test", sequence_number=42)
    db_session.add(log_seq)
    with pytest.raises(ValueError, match="Direct assignment of audit integrity fields"):
        db_session.flush()
    db_session.rollback()

    # 2. Caller supplies prev_hash
    log_prev = AuditLog(actor_id=u.id, action="forged_prev", entity_type="test", prev_hash="a" * 64)
    db_session.add(log_prev)
    with pytest.raises(ValueError, match="Direct assignment of audit integrity fields"):
        db_session.flush()
    db_session.rollback()

    # 3. Caller supplies record_hash
    log_hash = AuditLog(actor_id=u.id, action="forged_hash", entity_type="test", record_hash="b" * 64)
    db_session.add(log_hash)
    with pytest.raises(ValueError, match="Direct assignment of audit integrity fields"):
        db_session.flush()
    db_session.rollback()

    # 4. Caller supplies all three fields
    log_all = AuditLog(
        actor_id=u.id,
        action="forged_all",
        entity_type="test",
        sequence_number=100,
        prev_hash="a" * 64,
        record_hash="b" * 64,
    )
    db_session.add(log_all)
    with pytest.raises(ValueError, match="Direct assignment of audit integrity fields"):
        db_session.flush()
    db_session.rollback()

    # Verify no forged records were inserted
    assert db_session.scalar(select(AuditLog).where(AuditLog.action.like("forged_%"))) is None


def test_ordinary_audit_entries_auto_sequenced_after_rejected_forgery(db_session: Session):
    """Test that ordinary audit entries are sequenced correctly, even after a rejected attempt."""
    u = make_user(db_session, "clean-audit@demo.local", ["faculty"])
    db_session.commit()

    # Attempt forged insert that gets rejected
    forged = AuditLog(actor_id=u.id, action="forged_attempt", entity_type="test", sequence_number=999)
    db_session.add(forged)
    with pytest.raises(ValueError, match="Direct assignment of audit integrity fields"):
        db_session.flush()
    db_session.rollback()

    # Ordinary insert via create_audit_entry
    valid1 = create_audit_entry(db_session, actor_id=u.id, action="clean_1", entity_type="test")
    db_session.commit()

    # Ordinary direct db.add(AuditLog(...))
    valid2 = AuditLog(actor_id=u.id, action="clean_2", entity_type="test")
    db_session.add(valid2)
    db_session.commit()

    assert valid1.sequence_number == 1
    assert valid1.prev_hash == GENESIS_HASH
    assert valid2.sequence_number == 2
    assert valid2.prev_hash == valid1.record_hash

    # Verification must be completely valid
    report = verify_audit_log_chain(db_session)
    assert report["is_valid"] is True
    assert report["total_records"] == 2


def test_postgresql_advisory_lock_failure_aborts_transaction(db_session: Session, monkeypatch):
    """Test that failure to acquire PostgreSQL advisory lock fails closed and aborts flush."""
    u = make_user(db_session, "pg-fail@demo.local", ["admin"])
    db_session.commit()

    user_id = u.id
    real_get_bind = db_session.get_bind

    class MockDialect:
        name = "postgresql"

    class MockBind:
        dialect = MockDialect()

    def fake_get_bind(*args, **kwargs):
        mapper = kwargs.get("mapper") if "mapper" in kwargs else (args[0] if len(args) > 0 else None)
        if mapper is AuditLog:
            return MockBind()
        return real_get_bind(*args, **kwargs)

    monkeypatch.setattr(db_session, "get_bind", fake_get_bind)

    real_execute = db_session.execute

    def fake_execute(statement, *args, **kwargs):
        if "pg_advisory_xact_lock" in str(statement):
            raise RuntimeError("PostgreSQL connection severed during advisory lock acquisition")
        return real_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", fake_execute)

    # Adding an AuditLog must fail closed
    log = AuditLog(actor_id=user_id, action="test_action", entity_type="test")
    db_session.add(log)

    with pytest.raises(RuntimeError, match="PostgreSQL connection severed"):
        db_session.flush()

    db_session.rollback()

    # Verify no unsequenced or partially committed record exists
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "test_action")) is None
