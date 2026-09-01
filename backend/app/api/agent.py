from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_faculty_profile
from app.models import AppraisalPlan, AuditLog, FacultyProfile, User
from app.schemas.agent import ClarificationInput, PlanInput, PlanOut, PlanPatch
from app.services.cycles import get_open_cycle
from app.services.planning import answer_clarifications, create_plan, lock_plan, plan_to_dict, revise_plan

router = APIRouter(prefix="/api/v1/agent/plans", tags=["agent-plans"])


def _owned_plan(db: Session, plan_id: UUID, profile: FacultyProfile) -> AppraisalPlan:
    plan = db.scalar(select(AppraisalPlan).where(AppraisalPlan.id == plan_id, AppraisalPlan.faculty_id == profile.id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("", response_model=PlanOut)
def create_agent_plan(body: PlanInput, db: Session = Depends(get_db), user: User = Depends(get_current_user), profile: FacultyProfile = Depends(get_faculty_profile)) -> dict:
    plan = create_plan(db, profile=profile, user=user, data=body, cycle=get_open_cycle(db))
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan)


@router.get("/{plan_id}", response_model=PlanOut)
def get_agent_plan(plan_id: UUID, db: Session = Depends(get_db), profile: FacultyProfile = Depends(get_faculty_profile)) -> dict:
    return plan_to_dict(_owned_plan(db, plan_id, profile))


@router.post("/{plan_id}/clarify", response_model=PlanOut)
def clarify_agent_plan(plan_id: UUID, body: ClarificationInput, db: Session = Depends(get_db), user: User = Depends(get_current_user), profile: FacultyProfile = Depends(get_faculty_profile)) -> dict:
    plan = _owned_plan(db, plan_id, profile)
    answer_clarifications(db, plan=plan, user=user, answers=body.answers)
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan)


@router.patch("/{plan_id}", response_model=PlanOut)
def revise_agent_plan(plan_id: UUID, body: PlanPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user), profile: FacultyProfile = Depends(get_faculty_profile)) -> dict:
    plan = _owned_plan(db, plan_id, profile)
    revise_plan(db, plan=plan, user=user, changes=body.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan)


@router.post("/{plan_id}/lock", response_model=PlanOut)
def lock_agent_plan(plan_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user), profile: FacultyProfile = Depends(get_faculty_profile)) -> dict:
    plan = _owned_plan(db, plan_id, profile)
    lock_plan(db, plan=plan, user=user)
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan)
