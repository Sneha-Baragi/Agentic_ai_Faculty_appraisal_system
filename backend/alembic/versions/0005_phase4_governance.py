"""Phase 4: report governance, publishing, and immutable versions.

Revision ID: 0005_phase4_governance
Revises: 0004_phase3_approval_workflow
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase4_governance"
down_revision: Union[str, None] = "0004_phase3_approval_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appraisal_reports", sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("appraisal_reports", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_reports_published_by", "appraisal_reports", "users", ["published_by"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_reports_published_by", "appraisal_reports", type_="foreignkey")
    op.drop_column("appraisal_reports", "published_at")
    op.drop_column("appraisal_reports", "published_by")