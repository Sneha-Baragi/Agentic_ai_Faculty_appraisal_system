from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models import User
from app.services.sdlc_factory import (
    approve_sdlc_task,
    create_sdlc_task,
    execute_sdlc_task,
    get_sdlc_task,
    regenerate_sdlc_plan,
)

router = APIRouter(prefix="/api/v1/sdlc", tags=["sdlc-factory"])
AUTHORIZED_USER = require_roles("admin", "faculty")
ADMIN_USER = require_roles("admin")


class SDLCCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=4000)
    target_files: list[str] = Field(default_factory=list)
    task_type: str | None = Field(default=None, pattern="^(verification|development)$")


class SDLCApprovalRequest(BaseModel):
    plan_hash: str
    action: str = Field(pattern="^(approve|reject)$")
    rejection_reason: str | None = None


class SDLCRegenerateRequest(BaseModel):
    task_type: str | None = Field(default=None, pattern="^(verification|development)$")
    title: str | None = None
    description: str | None = None
    target_files: list[str] | None = None


class SDLCExecuteRequest(BaseModel):
    verification_command_key: str = "pytest_quick"


@router.post("/tasks")
def create_task_endpoint(
    body: SDLCCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(AUTHORIZED_USER),
) -> dict[str, Any]:
    try:
        task = create_sdlc_task(
            db=db,
            user=user,
            title=body.title,
            description=body.description,
            target_files=body.target_files,
            task_type=body.task_type,
        )
        return task
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tasks/{task_id}")
def get_task_endpoint(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(AUTHORIZED_USER),
) -> dict[str, Any]:
    try:
        task = get_sdlc_task(db, task_id, user=user)
        if not task:
            raise HTTPException(status_code=404, detail=f"SDLC task '{task_id}' not found")
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/tasks/{task_id}/approval")
def approve_task_endpoint(
    task_id: str,
    body: SDLCApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(ADMIN_USER),
) -> dict[str, Any]:
    try:
        task = approve_sdlc_task(
            db=db,
            user=user,
            task_id=task_id,
            provided_plan_hash=body.plan_hash,
            action=body.action,
            rejection_reason=body.rejection_reason,
        )
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/tasks/{task_id}/regenerate")
def regenerate_task_endpoint(
    task_id: str,
    body: SDLCRegenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(AUTHORIZED_USER),
) -> dict[str, Any]:
    try:
        task = regenerate_sdlc_plan(
            db=db,
            user=user,
            task_id=task_id,
            task_type=body.task_type,
            title=body.title,
            description=body.description,
            target_files=body.target_files,
        )
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/tasks/{task_id}/execute")
def execute_task_endpoint(
    task_id: str,
    body: SDLCExecuteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(ADMIN_USER),
) -> dict[str, Any]:
    try:
        task = execute_sdlc_task(
            db=db,
            user=user,
            task_id=task_id,
            verification_command_key=body.verification_command_key,
        )
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
