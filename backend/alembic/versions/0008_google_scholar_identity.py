"""Add Google Scholar identity fields to faculty profiles.

Revision ID: 0008_google_scholar_identity
Revises: add_unique_attendance_constraint
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008_google_scholar_identity"
down_revision: Union[str, None] = "add_unique_attendance_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("faculty_profiles", sa.Column("google_scholar_id", sa.String(length=100), nullable=True))
    op.add_column("faculty_profiles", sa.Column("google_scholar_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("faculty_profiles", "google_scholar_url")
    op.drop_column("faculty_profiles", "google_scholar_id")