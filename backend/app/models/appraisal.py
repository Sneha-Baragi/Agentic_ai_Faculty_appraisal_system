import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableUUID


class AppraisalCycle(Base):
    __tablename__ = "appraisal_cycles"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class FacultyAppraisalRun(Base):
    __tablename__ = "faculty_appraisal_runs"
    __table_args__ = (UniqueConstraint("faculty_id", "cycle_id"),)

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_profiles.id"), nullable=False, index=True
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), ForeignKey("appraisal_cycles.id"), nullable=False)
    graph_thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="collecting", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(PortableUUID(), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(30), default="not_generated", nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(PortableUUID(), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    change_request_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    approval_comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class FacultyActivity(Base):
    __tablename__ = "faculty_activities"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_appraisal_runs.id"), nullable=False, index=True
    )
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID(), ForeignKey("faculty_profiles.id"), nullable=True, index=True
    )
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID(), ForeignKey("appraisal_cycles.id"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    activity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="raw", nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="self_report", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    research: Mapped["ResearchActivity | None"] = relationship(back_populates="activity", uselist=False)
    teaching: Mapped["TeachingActivity | None"] = relationship(back_populates="activity", uselist=False)
    administrative: Mapped["AdministrativeActivity | None"] = relationship(
        back_populates="activity", uselist=False
    )
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="activity")


class ResearchActivity(Base):
    __tablename__ = "research_activities"

    activity_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_activities.id"), primary_key=True
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    authors: Mapped[Any] = mapped_column(JSON, default=list)
    extras: Mapped[Any] = mapped_column(JSON, default=dict)

    activity: Mapped[FacultyActivity] = relationship(back_populates="research")


class TeachingActivity(Base):
    __tablename__ = "teaching_activities"

    activity_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_activities.id"), primary_key=True
    )
    course_code: Mapped[str] = mapped_column(String(50), nullable=False)
    hours: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    pedagogy: Mapped[str | None] = mapped_column(String(200), nullable=True)
    outcomes: Mapped[Any] = mapped_column(JSON, default=dict)

    activity: Mapped[FacultyActivity] = relationship(back_populates="teaching")


class AdministrativeActivity(Base):
    __tablename__ = "administrative_activities"

    activity_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_activities.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(String(300), nullable=True)
    hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    extras: Mapped[Any] = mapped_column(JSON, default=dict)

    activity: Mapped[FacultyActivity] = relationship(back_populates="administrative")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_activities.id"), nullable=False, index=True
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_profiles.id"), nullable=False
    )
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID(), ForeignKey("appraisal_cycles.id"), nullable=True
    )
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    kind: Mapped[str] = mapped_column(String(40), default="pdf", nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(40), default="uploaded", nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)

    activity: Mapped["FacultyActivity"] = relationship(back_populates="evidence")
    extractions: Mapped[list["EvidenceExtraction"]] = relationship(back_populates="evidence")


class EvidenceValidation(Base):
    __tablename__ = "evidence_validations"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), ForeignKey("evidence.id"), nullable=False)
    activity_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_activities.id"), nullable=False
    )
    verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons: Mapped[Any] = mapped_column(JSON, default=list)
    agent_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class EvidenceExtraction(Base):
    __tablename__ = "evidence_extractions"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("evidence.id"), nullable=False, index=True
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(40), nullable=False)
    extraction_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_metadata: Mapped[Any] = mapped_column("metadata", JSON, default=dict)

    evidence: Mapped["Evidence"] = relationship(back_populates="extractions")


class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    json_definition: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PortableUUID(), ForeignKey("users.id"), nullable=True)


class AppraisalScore(Base):
    __tablename__ = "appraisal_scores"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_appraisal_runs.id"), nullable=False, index=True
    )
    rubric_id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), ForeignKey("rubrics.id"), nullable=False)
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID(), ForeignKey("faculty_profiles.id"), nullable=True, index=True
    )
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID(), ForeignKey("appraisal_cycles.id"), nullable=True, index=True
    )
    total: Mapped[float] = mapped_column(Float, nullable=False)
    breakdown: Mapped[Any] = mapped_column(JSON, default=dict)
    activity_score_refs: Mapped[Any] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)


class AppraisalReport(Base):
    __tablename__ = "appraisal_reports"
    __table_args__ = (UniqueConstraint("run_id", "version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_appraisal_runs.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID(), ForeignKey("appraisal_reports.id"), nullable=True
    )
    score_id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), ForeignKey("appraisal_scores.id"), nullable=False)
    summary_md: Mapped[str] = mapped_column(String, default="", nullable=False)
    rating_recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="generated", nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(PortableUUID(), ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
