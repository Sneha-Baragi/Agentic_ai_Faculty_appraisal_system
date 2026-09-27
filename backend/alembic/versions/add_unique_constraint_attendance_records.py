"""Add unique constraint to attendance_records table.

Revision ID: add_unique_constraint_attendance_records
Revises: 95278a8bd97f
Create Date: 2026-09-12 13:46:30.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_unique_attendance_constraint"
down_revision = "95278a8bd97f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add a unique constraint on (faculty_id, timetable_entry_id, attended_at date) to prevent duplicate attendance per day
    op.create_unique_constraint(
        "uq_attendance_facetimetable_date",
        "attendance_records",
        ["faculty_id", "timetable_entry_id", "attended_at"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_attendance_facetimetable_date",
        "attendance_records",
        type_="unique",
    )
