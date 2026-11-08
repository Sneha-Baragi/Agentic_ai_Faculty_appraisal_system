"""SEC-06: Audit Log Integrity and Tamper Protection.

Provides canonical serialization, SHA-256 hash chaining, sequence generation,
and tamper detection verification for the audit log.

SECURITY NOTICE & LIMITATION:
This cryptographic hash chain provides verifiable detection against unauthorized
row modification, deletion, reordering, and injection by application users, SQL
injection vectors, or partial database tampering.
However, a privileged database administrator (DBA) or superuser with unrestricted
raw database write access could theoretically rewrite the entire table and recompute
all subsequent hashes. Complete protection against full-chain DBA rewriting requires
an independent external trust anchor (such as remote immutable WORM storage, RFC 3161
Timestamp Authorities, or external key management/ledger services), which remains
future work.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.models.governance import AuditLog

logger = logging.getLogger(__name__)

GENESIS_HASH: str = "0" * 64
_sqlite_chain_lock = threading.Lock()
_PG_ADVISORY_LOCK_ID: int = 0x41554449  # 'AUDI' in ASCII


def canonical_datetime(dt: datetime | str | None) -> str:
    """Format datetime into a deterministic UTC ISO 8601 string.

    Ensures identical string representation regardless of whether the datetime
    object is timezone-aware, naive (from SQLite), or an existing ISO string.
    """
    if dt is None:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_json_value(val: Any) -> Any:
    """Normalize JSON values to ensure deterministic serialization."""
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


def compute_audit_record_hash(
    *,
    sequence_number: int,
    prev_hash: str,
    created_at: datetime | str | None,
    actor_id: Any,
    action: str,
    entity_type: str,
    entity_id: Any,
    before: Any,
    after: Any,
    ip: Any,
) -> str:
    """Compute deterministic SHA-256 hash for an audit record.

    Includes every integrity-relevant field with strict canonical serialization.
    """
    payload = {
        "sequence_number": int(sequence_number),
        "prev_hash": str(prev_hash),
        "created_at": canonical_datetime(created_at),
        "actor_id": str(actor_id) if actor_id else None,
        "action": str(action),
        "entity_type": str(entity_type),
        "entity_id": str(entity_id) if entity_id else None,
        "before": canonical_json_value(before),
        "after": canonical_json_value(after),
        "ip": str(ip) if ip else None,
    }
    canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def _acquire_lock(session: Session) -> None:
    """Acquire transaction-level lock on PostgreSQL if available.

    Fails closed: when the dialect is PostgreSQL, any failure to acquire
    the advisory lock propagates and aborts the transaction.
    """
    bind = session.get_bind(AuditLog)
    if bind and bind.dialect.name == "postgresql":
        try:
            session.execute(text(f"SELECT pg_advisory_xact_lock({_PG_ADVISORY_LOCK_ID})"))
        except Exception as exc:
            logger.error("Failed to acquire PostgreSQL advisory lock for audit log chaining: %s", exc)
            raise


@event.listens_for(Session, "before_flush")
def _auto_chain_audit_logs(session: Session, flush_context: Any, instances: Any) -> None:
    """SQLAlchemy hook ensuring any AuditLog added to the session is sequenced and hashed.

    Maintains 100% backward compatibility with all direct `db.add(AuditLog(...))` call sites.
    Rejects caller-supplied integrity fields (sequence_number, prev_hash, record_hash)
    unless the internal test flag `_skip_auto_hash` is explicitly set.
    """
    # 1. Enforce fail-closed rejection on caller-supplied integrity fields
    for obj in session.new:
        if isinstance(obj, AuditLog) and not getattr(obj, "_skip_auto_hash", False):
            if (
                obj.sequence_number is not None
                or obj.prev_hash is not None
                or obj.record_hash is not None
            ):
                raise ValueError(
                    "Direct assignment of audit integrity fields (sequence_number, prev_hash, record_hash) "
                    "is forbidden on AuditLog."
                )

    # 2. Gather pending audit logs to chain
    pending = [
        obj for obj in session.new
        if isinstance(obj, AuditLog)
        and not getattr(obj, "_skip_auto_hash", False)
    ]
    if not pending:
        return

    bind = session.get_bind(AuditLog)
    is_sqlite = bind and bind.dialect.name == "sqlite"

    if is_sqlite:
        _sqlite_chain_lock.acquire()
    try:
        _acquire_lock(session)

        # Query latest committed record in database
        latest = session.scalar(
            select(AuditLog)
            .where(AuditLog.sequence_number.is_not(None))
            .order_by(AuditLog.sequence_number.desc())
            .limit(1)
        )
        current_seq = latest.sequence_number if (latest and latest.sequence_number is not None) else 0
        current_hash = latest.record_hash if (latest and latest.record_hash is not None) else GENESIS_HASH

        for log in pending:
            current_seq += 1
            log.sequence_number = current_seq
            log.prev_hash = current_hash
            if log.created_at is None:
                log.created_at = datetime.now(timezone.utc)
            log.record_hash = compute_audit_record_hash(
                sequence_number=log.sequence_number,
                prev_hash=log.prev_hash,
                created_at=log.created_at,
                actor_id=log.actor_id,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                before=log.before,
                after=log.after,
                ip=log.ip,
            )
            current_hash = log.record_hash
    finally:
        if is_sqlite:
            _sqlite_chain_lock.release()


def create_audit_entry(
    db: Session,
    *,
    actor_id: Any = None,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    before: Any = None,
    after: Any = None,
    ip: Any = None,
    created_at: datetime | None = None,
) -> AuditLog:
    """Create and stage a new AuditLog entry.

    The entry will be automatically sequenced and chained during session flush.
    """
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        before=before,
        after=after,
        ip=ip,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(log)
    return log


def verify_audit_log_chain(
    db: Session,
    *,
    start_sequence: int = 1,
    end_sequence: int | None = None,
) -> dict[str, Any]:
    """Verify integrity of the audit log hash chain.

    Validates:
    1. Presence of sequence numbers
    2. Strict monotonic progression with no gaps or duplicates
    3. Correct linkage to previous record hashes
    4. Exact match of recalculated SHA-256 payload digests

    Never modifies records. Returns diagnostic error if tampering is detected.
    """
    stmt = select(AuditLog).order_by(AuditLog.sequence_number.asc(), AuditLog.created_at.asc(), AuditLog.id.asc())
    if start_sequence > 1:
        stmt = stmt.where(AuditLog.sequence_number >= start_sequence)
    if end_sequence is not None:
        stmt = stmt.where(AuditLog.sequence_number <= end_sequence)

    records = list(db.scalars(stmt))
    if not records:
        return {
            "is_valid": True,
            "total_records": 0,
            "verified_records": 0,
            "head_sequence": None,
            "head_hash": None,
            "violation": None,
            "message": "Audit log is empty; chain is valid.",
        }

    expected_seq = start_sequence
    if start_sequence > 1:
        prior_record = db.scalar(select(AuditLog).where(AuditLog.sequence_number == start_sequence - 1))
        expected_prev_hash = prior_record.record_hash if prior_record else None
    else:
        expected_prev_hash = GENESIS_HASH

    for idx, record in enumerate(records):
        # 1. Check sequence number exists
        if record.sequence_number is None:
            return {
                "is_valid": False,
                "total_records": len(records),
                "verified_records": idx,
                "head_sequence": records[idx - 1].sequence_number if idx > 0 else None,
                "head_hash": records[idx - 1].record_hash if idx > 0 else None,
                "violation": {
                    "violation_type": "MISSING_SEQUENCE_NUMBER",
                    "record_id": str(record.id),
                    "action": record.action,
                    "entity_type": record.entity_type,
                    "details": f"Record {record.id} has no sequence number.",
                },
                "message": "Integrity violation: unsequenced audit record detected.",
            }

        # 2. Check sequence continuity (no gaps or duplicates)
        if record.sequence_number != expected_seq:
            return {
                "is_valid": False,
                "total_records": len(records),
                "verified_records": idx,
                "head_sequence": records[idx - 1].sequence_number if idx > 0 else None,
                "head_hash": records[idx - 1].record_hash if idx > 0 else None,
                "violation": {
                    "violation_type": "SEQUENCE_GAP",
                    "record_id": str(record.id),
                    "expected_sequence": expected_seq,
                    "actual_sequence": record.sequence_number,
                    "details": f"Sequence gap detected: expected {expected_seq}, found {record.sequence_number}.",
                },
                "message": f"Integrity violation: sequence gap or missing record detected at sequence {expected_seq}.",
            }

        # 3. Check predecessor link
        if expected_prev_hash is not None and record.prev_hash != expected_prev_hash:
            return {
                "is_valid": False,
                "total_records": len(records),
                "verified_records": idx,
                "head_sequence": records[idx - 1].sequence_number if idx > 0 else None,
                "head_hash": records[idx - 1].record_hash if idx > 0 else None,
                "violation": {
                    "violation_type": "BROKEN_PREDECESSOR_LINK",
                    "sequence_number": record.sequence_number,
                    "record_id": str(record.id),
                    "expected_prev_hash": expected_prev_hash,
                    "actual_prev_hash": record.prev_hash,
                    "details": f"Record at sequence {record.sequence_number} does not link to predecessor hash.",
                },
                "message": f"Integrity violation: broken chain link detected at sequence {record.sequence_number}.",
            }

        # 4. Check record hash exists
        if not record.record_hash:
            return {
                "is_valid": False,
                "total_records": len(records),
                "verified_records": idx,
                "head_sequence": records[idx - 1].sequence_number if idx > 0 else None,
                "head_hash": records[idx - 1].record_hash if idx > 0 else None,
                "violation": {
                    "violation_type": "MISSING_RECORD_HASH",
                    "sequence_number": record.sequence_number,
                    "record_id": str(record.id),
                    "details": f"Record at sequence {record.sequence_number} has no record_hash.",
                },
                "message": f"Integrity violation: missing record hash at sequence {record.sequence_number}.",
            }

        # 5. Recompute and verify payload hash
        computed_hash = compute_audit_record_hash(
            sequence_number=record.sequence_number,
            prev_hash=record.prev_hash,
            created_at=record.created_at,
            actor_id=record.actor_id,
            action=record.action,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            before=record.before,
            after=record.after,
            ip=record.ip,
        )
        if record.record_hash != computed_hash:
            return {
                "is_valid": False,
                "total_records": len(records),
                "verified_records": idx,
                "head_sequence": records[idx - 1].sequence_number if idx > 0 else None,
                "head_hash": records[idx - 1].record_hash if idx > 0 else None,
                "violation": {
                    "violation_type": "ALTERED_RECORD_PAYLOAD",
                    "sequence_number": record.sequence_number,
                    "record_id": str(record.id),
                    "details": f"Record at sequence {record.sequence_number} payload has been altered (hash mismatch).",
                },
                "message": f"Integrity violation: altered payload detected at sequence {record.sequence_number}.",
            }

        expected_prev_hash = record.record_hash
        expected_seq += 1

    return {
        "is_valid": True,
        "total_records": len(records),
        "verified_records": len(records),
        "head_sequence": records[-1].sequence_number,
        "head_hash": records[-1].record_hash,
        "violation": None,
        "message": f"Audit chain verified successfully ({len(records)} records).",
    }
