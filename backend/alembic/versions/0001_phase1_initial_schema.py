"""Initial schema.

Revision ID: 0001_phase1
Revises:
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_phase1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )

    op.create_table(
        "faculty_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_code", sa.String(64), nullable=False),
        sa.Column("department", sa.String(128), nullable=False),
        sa.Column("designation", sa.String(128), nullable=False),
        sa.Column("confidentiality_scope", sa.String(64), nullable=False, server_default="self"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("employee_code"),
    )
    op.create_index("ix_faculty_profiles_employee_code", "faculty_profiles", ["employee_code"], unique=True)

    op.create_table(
        "appraisal_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("academic_year", sa.String(16), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rubrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("json_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "faculty_appraisal_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("faculty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_thread_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(64), nullable=False, server_default="collecting"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["appraisal_cycles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("faculty_id", "cycle_id", name="uq_runs_faculty_cycle"),
    )
    op.create_index("ix_runs_status", "faculty_appraisal_runs", ["status"])
    op.create_index("ix_runs_faculty_cycle", "faculty_appraisal_runs", ["faculty_id", "cycle_id"])

    op.create_table(
        "faculty_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="raw"),
        sa.Column("source", sa.String(32), nullable=False, server_default="self_report"),
        sa.ForeignKeyConstraint(["run_id"], ["faculty_appraisal_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_faculty_activities_run_id", "faculty_activities", ["run_id"])

    op.create_table(
        "research_activities",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("venue", sa.String(255), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("authors", sa.String(512), nullable=True),
        sa.Column("extras", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["faculty_activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("activity_id"),
    )

    op.create_table(
        "teaching_activities",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_code", sa.String(64), nullable=False),
        sa.Column("hours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pedagogy", sa.String(255), nullable=True),
        sa.Column("outcomes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["faculty_activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("activity_id"),
    )

    op.create_table(
        "administrative_activities",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(128), nullable=False),
        sa.Column("body", sa.String(255), nullable=True),
        sa.Column("hours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extras", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["faculty_activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("activity_id"),
    )

    op.create_table(
        "validated_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["faculty_appraisal_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_activity_id"], ["faculty_activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_activity_id"),
    )
    op.create_index("ix_validated_activities_run_id", "validated_activities", ["run_id"])

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("faculty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("mime", sa.String(128), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["faculty_activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_activity_id", "evidence", ["activity_id"])
    op.create_index("ix_evidence_faculty_id", "evidence", ["faculty_id"])

    op.create_table(
        "evidence_validations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("agent_run_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activity_id"], ["faculty_activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_validations_evidence_id", "evidence_validations", ["evidence_id"])

    op.create_table(
        "appraisal_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rubric_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("activity_score_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["faculty_appraisal_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rubric_id"], ["rubrics.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appraisal_scores_run_id", "appraisal_scores", ["run_id"])

    op.create_table(
        "appraisal_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("score_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("rating_recommendation", sa.String(8), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="generated"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["faculty_appraisal_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_version_id"], ["appraisal_reports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["score_id"], ["appraisal_scores.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "version_number", name="uq_reports_run_version"),
    )
    op.create_index("ix_appraisal_reports_run_id", "appraisal_reports", ["run_id"])

    op.create_foreign_key(
        "fk_runs_current_version",
        "faculty_appraisal_runs",
        "appraisal_reports",
        ["current_version_id"],
        ["id"],
    )

    op.create_table(
        "approval_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("override_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["appraisal_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_decisions_report_id", "approval_decisions", ["report_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("approval_decisions")
    op.drop_constraint("fk_runs_current_version", "faculty_appraisal_runs", type_="foreignkey")
    op.drop_table("appraisal_reports")
    op.drop_table("appraisal_scores")
    op.drop_table("evidence_validations")
    op.drop_table("evidence")
    op.drop_table("validated_activities")
    op.drop_table("administrative_activities")
    op.drop_table("teaching_activities")
    op.drop_table("research_activities")
    op.drop_table("faculty_activities")
    op.drop_table("faculty_appraisal_runs")
    op.drop_table("rubrics")
    op.drop_table("appraisal_cycles")
    op.drop_table("faculty_profiles")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
