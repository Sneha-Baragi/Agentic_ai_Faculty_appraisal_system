from typing import Any

from pydantic import BaseModel, Field

from app.services.planning import PLAN_STATUSES
from app.services.reports import build_report


class PlanningSkillInput(BaseModel):
    request: str = Field(min_length=3)
    appraisal_cycle: str | None = None
    scope: str | None = None
    requested_sources: list[str] = Field(default_factory=list)
    activities_to_collect: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    scoring_requirements: list[str] = Field(default_factory=list)
    report_requirements: list[str] = Field(default_factory=list)


class PlanSkillOutput(BaseModel):
    appraisal_cycle: str | None
    scope: str | None
    requested_sources: list[str]
    activities_to_collect: list[str]
    evidence_requirements: list[str]
    scoring_requirements: list[str]
    report_requirements: list[str]
    clarification_questions: list[str]
    status: str
    version: int = 1


class ReportFormattingInput(BaseModel):
    profile: dict[str, Any]
    cycle: dict[str, Any]
    activities: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    score: dict[str, Any]
    approval: dict[str, Any] | None = None


class ReportDocument(BaseModel):
    json: dict[str, Any]
    html: str
    markdown: str


def planning_skill(inputs: PlanningSkillInput) -> PlanSkillOutput:
    questions = []
    if not inputs.appraisal_cycle:
        questions.append("Which academic appraisal cycle or reporting period should this plan cover?")
    if not inputs.scope:
        questions.append("What is the appraisal scope: research, teaching, administrative work, or all three?")
    if not inputs.requested_sources:
        questions.append("Which evidence sources should be included, such as uploaded PDFs or existing records?")
    if len(questions) == 1:
        questions.append("Which activities and evidence should be treated as required for this appraisal?")
    return PlanSkillOutput(
        appraisal_cycle=inputs.appraisal_cycle, scope=inputs.scope, requested_sources=inputs.requested_sources,
        activities_to_collect=inputs.activities_to_collect, evidence_requirements=inputs.evidence_requirements,
        scoring_requirements=inputs.scoring_requirements, report_requirements=inputs.report_requirements,
        clarification_questions=questions, status="NEEDS_CLARIFICATION" if questions else "READY_FOR_REVIEW",
    )


def format_appraisal_report(inputs: ReportFormattingInput) -> ReportDocument:
    built = build_report(profile=inputs.profile, cycle=inputs.cycle, activities=inputs.activities, evidence=inputs.evidence, score=inputs.score, approval=inputs.approval)
    return ReportDocument(json=built["json"], html=built["html"], markdown=built["markdown"])
