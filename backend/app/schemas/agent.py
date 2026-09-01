from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PlanInput(BaseModel):
    request: str = Field(min_length=3, max_length=4000)
    appraisal_cycle: str | None = None
    scope: str | None = None
    requested_sources: list[str] = Field(default_factory=list)
    activities_to_collect: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    scoring_requirements: list[str] = Field(default_factory=list)
    report_requirements: list[str] = Field(default_factory=list)


class ClarificationInput(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class PlanPatch(BaseModel):
    scope: str | None = None
    requested_sources: list[str] | None = None
    activities_to_collect: list[str] | None = None
    evidence_requirements: list[str] | None = None
    scoring_requirements: list[str] | None = None
    report_requirements: list[str] | None = None


class PlanOut(BaseModel):
    plan_id: UUID
    faculty_id: UUID
    request: str
    appraisal_cycle: str | None
    scope: str | None
    requested_sources: list[Any]
    activities_to_collect: list[Any]
    evidence_requirements: list[Any]
    scoring_requirements: list[Any]
    report_requirements: list[Any]
    clarification_questions: list[str]
    clarification_answers: dict[str, str]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    locked_at: datetime | None