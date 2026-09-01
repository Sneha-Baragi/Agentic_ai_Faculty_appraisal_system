"""Phase 3: human HOD approval workflow.

Revision ID: 0004_phase3_approval_workflow
Revises: 0003_faculty_activity_timestamps
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase3_approval_workflow"
down_revision: Union[str, None] = "0003_activity_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("faculty_appraisal_runs", sa.Column("approval_status", sa.String(length=30), server_default="not_generated", nullable=False))
    op.add_column("faculty_appraisal_runs", sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("faculty_appraisal_runs", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("faculty_appraisal_runs", sa.Column("rejection_reason", sa.String(length=2000), nullable=True))
    op.add_column("faculty_appraisal_runs", sa.Column("change_request_reason", sa.String(length=2000), nullable=True))
    op.add_column("faculty_appraisal_runs", sa.Column("approval_comment", sa.String(length=2000), nullable=True))
    op.add_column("faculty_appraisal_runs", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))
    op.create_foreign_key("fk_runs_reviewer", "faculty_appraisal_runs", "users", ["reviewer_id"], ["id"])
    op.create_index("ix_runs_approval_status", "faculty_appraisal_runs", ["approval_status"])
    op.execute("UPDATE faculty_appraisal_runs SET approval_status = 'awaiting_review' WHERE status = 'awaiting_review'")


def downgrade() -> None:
    op.drop_index("ix_runs_approval_status", table_name="faculty_appraisal_runs")
    op.drop_constraint("fk_runs_reviewer", "faculty_appraisal_runs", type_="foreignkey")
    op.drop_column("faculty_appraisal_runs", "updated_at")
    op.drop_column("faculty_appraisal_runs", "approval_comment")
    op.drop_column("faculty_appraisal_runs", "change_request_reason")
    op.drop_column("faculty_appraisal_runs", "rejection_reason")
    op.drop_column("faculty_appraisal_runs", "approved_at")
    op.drop_column("faculty_appraisal_runs", "reviewer_id")
    op.drop_column("faculty_appraisal_runs", "approval_status")
