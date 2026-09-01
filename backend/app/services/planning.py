from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppraisalCycle, AppraisalPlan, AuditLog, FacultyProfile, User
from app.schemas.agent import PlanInput

PLAN_STATUSES = {"DRAFT", "NEEDS_CLARIFICATION", "READY_FOR_REVIEW", "LOCKED"}


def _questions(data: PlanInput) -> list[str]:
    questions = []
    if not data.appraisal_cycle:
        questions.append("Which academic appraisal cycle or reporting period should this plan cover?")
    if not data.scope:
        questions.append("What is the appraisal scope: research, teaching, administrative work, or all three?")
    if not data.requested_sources:
        questions.append("Which evidence sources should be included, such as uploaded PDFs or existing records?")
    return questions


def plan_to_dict(plan: AppraisalPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.id, "faculty_id": plan.faculty_id, "appraisal_cycle": plan.appraisal_cycle,
        "request": plan.request,
        "scope": plan.scope, "requested_sources": plan.requested_sources or [],
        "activities_to_collect": plan.activities_to_collect or [], "evidence_requirements": plan.evidence_requirements or [],
        "scoring_requirements": plan.scoring_requirements or [], "report_requirements": plan.report_requirements or [],
        "clarification_questions": plan.clarification_questions or [], "clarification_answers": plan.clarification_answers or {},
        "status": plan.status, "version": plan.version, "created_at": plan.created_at,
        "updated_at": plan.updated_at, "locked_at": plan.locked_at,
    }


def _audit(db: Session, user: User, action: str, plan: AppraisalPlan, before: dict, after: dict) -> None:
    db.add(AuditLog(actor_id=user.id, action=action, entity_type="appraisal_plan", entity_id=str(plan.id), before=before, after=after))


def create_plan(db: Session, *, profile: FacultyProfile, user: User, data: PlanInput, cycle: AppraisalCycle | None) -> AppraisalPlan:
    questions = _questions(data)
    if len(questions) == 1:
        questions.append("Which activities and evidence should be treated as required for this appraisal?")
    plan = AppraisalPlan(
        faculty_id=profile.id, cycle_id=cycle.id if cycle else None, request=data.request,
        appraisal_cycle=data.appraisal_cycle or (cycle.name if cycle else None), scope=data.scope,
        requested_sources=data.requested_sources, activities_to_collect=data.activities_to_collect,
        evidence_requirements=data.evidence_requirements, scoring_requirements=data.scoring_requirements,
        report_requirements=data.report_requirements, clarification_questions=questions,
        clarification_answers={}, status="NEEDS_CLARIFICATION" if questions else "READY_FOR_REVIEW",
    )
    db.add(plan)
    db.flush()
    _audit(db, user, "plan_created", plan, {}, {"status": plan.status, "version": plan.version})
    if questions:
        _audit(db, user, "clarification_requested", plan, {"status": plan.status}, {"questions": questions})
    return plan


def answer_clarifications(db: Session, *, plan: AppraisalPlan, user: User, answers: dict[str, str]) -> AppraisalPlan:
    if plan.status == "LOCKED":
        raise HTTPException(status_code=409, detail="Locked plans cannot be modified")
    merged = dict(plan.clarification_answers or {})
    merged.update({key: value.strip() for key, value in answers.items() if value.strip()})
    plan.clarification_answers = merged
    for question, answer in merged.items():
        lowered = question.lower()
        if not plan.appraisal_cycle and ("cycle" in lowered or "reporting period" in lowered):
            plan.appraisal_cycle = answer
        elif not plan.scope and "scope" in lowered:
            plan.scope = answer
        elif not plan.requested_sources and "source" in lowered:
            plan.requested_sources = [answer]
    plan.status = "READY_FOR_REVIEW" if len(merged) >= len(plan.clarification_questions or []) else "NEEDS_CLARIFICATION"
    plan.updated_at = datetime.now(timezone.utc)
    _audit(db, user, "plan_clarification_answered", plan, {"status": "NEEDS_CLARIFICATION"}, {"status": plan.status, "answers": merged})
    return plan


def revise_plan(db: Session, *, plan: AppraisalPlan, user: User, changes: dict[str, Any]) -> AppraisalPlan:
    if plan.status == "LOCKED":
        raise HTTPException(status_code=409, detail="Locked plans cannot be modified; create a new plan revision")
    before = {"status": plan.status, "version": plan.version}
    for key, value in changes.items():
        if value is not None and hasattr(plan, key):
            setattr(plan, key, value)
    plan.version += 1
    plan.status = "READY_FOR_REVIEW"
    plan.updated_at = datetime.now(timezone.utc)
    _audit(db, user, "plan_revised", plan, before, {"status": plan.status, "version": plan.version})
    return plan


def lock_plan(db: Session, *, plan: AppraisalPlan, user: User) -> AppraisalPlan:
    if plan.status == "LOCKED":
        return plan
    if plan.status not in {"READY_FOR_REVIEW", "DRAFT"}:
        raise HTTPException(status_code=409, detail="Answer clarification questions before locking")
    plan.status = "LOCKED"
    plan.locked_at = datetime.now(timezone.utc)
    plan.updated_at = plan.locked_at
    _audit(db, user, "plan_locked", plan, {"status": "READY_FOR_REVIEW"}, {"status": plan.status, "locked_at": plan.locked_at.isoformat()})
    return plan
