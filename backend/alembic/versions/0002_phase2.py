"""Phase 2: profile fields, activity details, evidence pipeline, scoring snapshot.

Revision ID: 0002_phase2
Revises: 0001_phase1
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase2"
down_revision: Union[str, None] = "0001_phase1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("faculty_profiles", sa.Column("full_name", sa.String(length=200), nullable=True))
    op.add_column("faculty_profiles", sa.Column("institution", sa.String(length=200), nullable=True))
    op.add_column("faculty_profiles", sa.Column("joining_date", sa.Date(), nullable=True))

    op.add_column(
        "appraisal_cycles",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.add_column(
        "appraisal_cycles",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # faculty_activities.created_at already exists from 0001_phase1
    op.add_column("faculty_activities", sa.Column("faculty_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("faculty_activities", sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("faculty_activities", sa.Column("activity_type", sa.String(length=80), nullable=True))
    op.add_column("faculty_activities", sa.Column("title", sa.String(length=500), nullable=True))
    op.add_column("faculty_activities", sa.Column("description", sa.String(length=4000), nullable=True))
    op.add_column("faculty_activities", sa.Column("activity_date", sa.Date(), nullable=True))
    op.add_column(
        "faculty_activities",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_foreign_key("fk_activities_faculty", "faculty_activities", "faculty_profiles", ["faculty_id"], ["id"])
    op.create_foreign_key("fk_activities_cycle", "faculty_activities", "appraisal_cycles", ["cycle_id"], ["id"])
    op.create_index("ix_faculty_activities_faculty_id", "faculty_activities", ["faculty_id"])
    op.create_index("ix_faculty_activities_cycle_id", "faculty_activities", ["cycle_id"])

    op.add_column("evidence", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("evidence", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("evidence", sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "evidence",
        sa.Column("validation_status", sa.String(length=40), server_default="uploaded", nullable=False),
    )
    op.add_column(
        "evidence",
        sa.Column("extraction_status", sa.String(length=40), server_default="pending", nullable=False),
    )
    op.create_foreign_key("fk_evidence_cycle", "evidence", "appraisal_cycles", ["cycle_id"], ["id"])

    op.create_table(
        "evidence_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_status", sa.String(length=40), nullable=False),
        sa.Column("extraction_error", sa.String(length=2000), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_extractions_evidence_id", "evidence_extractions", ["evidence_id"])

    op.add_column("appraisal_scores", sa.Column("faculty_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("appraisal_scores", sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_scores_faculty", "appraisal_scores", "faculty_profiles", ["faculty_id"], ["id"])
    op.create_foreign_key("fk_scores_cycle", "appraisal_scores", "appraisal_cycles", ["cycle_id"], ["id"])
    op.create_index("ix_appraisal_scores_faculty_id", "appraisal_scores", ["faculty_id"])
    op.create_index("ix_appraisal_scores_cycle_id", "appraisal_scores", ["cycle_id"])

    op.add_column("appraisal_reports", sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("appraisal_reports", "report_json")
    op.drop_constraint("fk_scores_cycle", "appraisal_scores", type_="foreignkey")
    op.drop_constraint("fk_scores_faculty", "appraisal_scores", type_="foreignkey")
    op.drop_index("ix_appraisal_scores_cycle_id", table_name="appraisal_scores")
    op.drop_index("ix_appraisal_scores_faculty_id", table_name="appraisal_scores")
    op.drop_column("appraisal_scores", "cycle_id")
    op.drop_column("appraisal_scores", "faculty_id")
    op.drop_index("ix_evidence_extractions_evidence_id", table_name="evidence_extractions")
    op.drop_table("evidence_extractions")
    op.drop_constraint("fk_evidence_cycle", "evidence", type_="foreignkey")
    op.drop_column("evidence", "extraction_status")
    op.drop_column("evidence", "validation_status")
    op.drop_column("evidence", "cycle_id")
    op.drop_column("evidence", "file_size")
    op.drop_column("evidence", "original_filename")
    op.drop_constraint("fk_activities_cycle", "faculty_activities", type_="foreignkey")
    op.drop_constraint("fk_activities_faculty", "faculty_activities", type_="foreignkey")
    op.drop_index("ix_faculty_activities_cycle_id", table_name="faculty_activities")
    op.drop_index("ix_faculty_activities_faculty_id", table_name="faculty_activities")
    op.drop_column("faculty_activities", "updated_at")
    op.drop_column("faculty_activities", "activity_date")
    op.drop_column("faculty_activities", "description")
    op.drop_column("faculty_activities", "title")
    op.drop_column("faculty_activities", "activity_type")
    op.drop_column("faculty_activities", "cycle_id")
    op.drop_column("faculty_activities", "faculty_id")
    op.drop_column("appraisal_cycles", "updated_at")
    op.drop_column("appraisal_cycles", "created_at")
    op.drop_column("faculty_profiles", "joining_date")
    op.drop_column("faculty_profiles", "institution")
    op.drop_column("faculty_profiles", "full_name")
