"""Phase 5A: structured appraisal planning.

Revision ID: 0006_phase5a_plans
Revises: 0005_phase4_governance
Create Date: 2026-08-24
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase5a_plans"
down_revision: Union[str, None] = "0005_phase4_governance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appraisal_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("faculty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request", sa.String(length=4000), nullable=False),
        sa.Column("appraisal_cycle", sa.String(length=200), nullable=True),
        sa.Column("scope", sa.String(length=1000), nullable=True),
        sa.Column("requested_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("activities_to_collect", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scoring_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("clarification_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("clarification_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["appraisal_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appraisal_plans_faculty_id", "appraisal_plans", ["faculty_id"])
    op.create_index("ix_appraisal_plans_cycle_id", "appraisal_plans", ["cycle_id"])


def downgrade() -> None:
    op.drop_index("ix_appraisal_plans_cycle_id", table_name="appraisal_plans")
    op.drop_index("ix_appraisal_plans_faculty_id", table_name="appraisal_plans")
    op.drop_table("appraisal_plans")