"""add new models for teaching requirement, timetable, attendance, project team

Revision ID: 95278a8bd97f
Revises: 0007_phase5b_lab2_tool_data
Create Date: 2026-09-12 13:16:17.816464

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '95278a8bd97f'
down_revision: Union[str, Sequence[str], None] = '0007_phase5b_lab2_tool_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create teaching_requirements table
    op.create_table(
        "teaching_requirements",
        sa.Column("role", sa.String(50), primary_key=True),
        sa.Column("required_hours", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create timetable_entries table
    op.create_table(
        "timetable_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("faculty_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("course_code", sa.String(64), nullable=False),
        sa.Column("section", sa.String(64), nullable=False),
        sa.Column("day_of_week", sa.String(20), nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("room", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create attendance_records table
    op.create_table(
        "attendance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("faculty_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("timetable_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("timetable_entries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="present"),
        sa.Column("attended_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create project_teams table
    op.create_table(
        "project_teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("faculty_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create project_team_members table
    op.create_table(
        "project_team_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_teams.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("project_team_members")
    op.drop_table("project_teams")
    op.drop_table("attendance_records")
    op.drop_table("timetable_entries")
    op.drop_table("teaching_requirements")
