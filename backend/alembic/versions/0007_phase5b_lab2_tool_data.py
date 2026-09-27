"""Phase 5B Lab 2: optional student feedback records.

Revision ID: 0007_phase5b_lab2_tool_data
Revises: 0006_phase5a_plans
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0007_phase5b_lab2_tool_data"
down_revision: Union[str, None] = "0006_phase5a_plans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("faculty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("response_count", sa.Integer(), nullable=False),
        sa.Column("comments", sa.String(length=4000), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty_profiles.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["appraisal_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_feedback_faculty_id", "student_feedback", ["faculty_id"])
    op.create_index("ix_student_feedback_cycle_id", "student_feedback", ["cycle_id"])


def downgrade() -> None:
    op.drop_index("ix_student_feedback_cycle_id", table_name="student_feedback")
    op.drop_index("ix_student_feedback_faculty_id", table_name="student_feedback")
    op.drop_table("student_feedback")