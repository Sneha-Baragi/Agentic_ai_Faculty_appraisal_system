import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PortableUUID


class AppraisalPlan(Base):
    __tablename__ = "appraisal_plans"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    faculty_id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(PortableUUID(), ForeignKey("appraisal_cycles.id"), nullable=True, index=True)
    request: Mapped[str] = mapped_column(String(4000), nullable=False)
    appraisal_cycle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    requested_sources: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    activities_to_collect: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    evidence_requirements: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    scoring_requirements: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    report_requirements: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    clarification_questions: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    clarification_answers: Mapped[Any] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="NEEDS_CLARIFICATION", nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
