"""SEC-06: Audit log integrity and tamper protection (hash chain).

Revision ID: 0009_audit_log_integrity
Revises: 0008_google_scholar_identity
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

try:
    from app.services.audit import GENESIS_HASH, compute_audit_record_hash
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.services.audit import GENESIS_HASH, compute_audit_record_hash


revision: str = "0009_audit_log_integrity"
down_revision: Union[str, None] = "0008_google_scholar_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add integrity columns as nullable to permit data backfill
    op.add_column("audit_logs", sa.Column("sequence_number", sa.BigInteger(), nullable=True))
    op.add_column("audit_logs", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("record_hash", sa.String(length=64), nullable=True))

    # 2. Backfill existing historical records deterministically (created_at ASC, id ASC)
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, created_at, actor_id, action, entity_type, entity_id, before, after, ip "
            "FROM audit_logs ORDER BY created_at ASC, id ASC"
        )
    ).fetchall()

    current_seq = 0
    current_hash = GENESIS_HASH
    for row in rows:
        current_seq += 1
        rec_hash = compute_audit_record_hash(
            sequence_number=current_seq,
            prev_hash=current_hash,
            created_at=row.created_at,
            actor_id=row.actor_id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            before=row.before,
            after=row.after,
            ip=row.ip,
        )
        bind.execute(
            sa.text(
                "UPDATE audit_logs SET sequence_number = :seq, prev_hash = :prev, record_hash = :hash "
                "WHERE id = :id"
            ),
            {"seq": current_seq, "prev": current_hash, "hash": rec_hash, "id": row.id},
        )
        current_hash = rec_hash

    # 3. Create unique index on sequence_number to guarantee strict monotonic ordering
    op.create_index("ix_audit_logs_sequence_number", "audit_logs", ["sequence_number"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_sequence_number", table_name="audit_logs")
    op.drop_column("audit_logs", "record_hash")
    op.drop_column("audit_logs", "prev_hash")
    op.drop_column("audit_logs", "sequence_number")
