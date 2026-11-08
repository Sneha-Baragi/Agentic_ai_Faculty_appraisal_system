from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, User

import shutil
import sys

def get_project_root() -> Path:
    """Resolve the project root dynamically from configuration, container runtime, or code layout."""
    env_root = os.environ.get("SDLC_PROJECT_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if candidate.is_dir():
            return candidate

    # Container check: standard Docker backend root is /app
    app_dir = Path("/app")
    if app_dir.is_dir() and (app_dir / "app").is_dir():
        return app_dir.resolve()

    # Layout-based discovery: backend/app/services/sdlc_factory.py -> project root is 3 levels up
    try:
        current_file = Path(__file__).resolve()
        # If in <root>/backend/app/services/sdlc_factory.py -> parents[3] is <root>
        if len(current_file.parents) >= 4 and (current_file.parents[3] / "backend").is_dir():
            return current_file.parents[3]
        # If in <root>/app/services/sdlc_factory.py -> parents[2] is <root>
        if len(current_file.parents) >= 3 and (current_file.parents[2] / "app").is_dir():
            return current_file.parents[2]
    except Exception:
        pass

    return Path.cwd().resolve()


PROJECT_ROOT = get_project_root()


class SDLCStepModel(BaseModel):
    step_id: str
    title: str
    description: str
    target_files: list[str] = Field(default_factory=list)
    risk_level: str = "low"  # "low", "medium", "high"
    test_criteria: list[str] = Field(default_factory=list)
    status: str = "pending"  # "pending", "approved", "in_progress", "completed", "failed", "skipped"
    execution_logs: str | None = None
    test_results: dict[str, Any] | None = None


class SDLCPlanModel(BaseModel):
    plan_id: str
    plan_hash: str
    task_type: str
    steps: list[SDLCStepModel]
    risk_assessment: str
    created_at: str


def compute_plan_hash(steps: list[dict[str, Any]]) -> str:
    canonical_str = json.dumps(steps, sort_keys=True)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def is_safe_path(target_path_str: str, base_root: Path | None = None) -> bool:
    try:
        if not target_path_str or ".." in target_path_str:
            return False
        root = base_root if base_root is not None else get_project_root()
        root_resolved = root.resolve()
        path = Path(target_path_str)
        if path.is_absolute():
            resolved = path.resolve()
        else:
            resolved = (root_resolved / path).resolve()
        return resolved == root_resolved or str(resolved).startswith(str(root_resolved) + os.sep)
    except Exception:
        return False


def get_allowlisted_commands(root: Path | None = None) -> dict[str, list[str]]:
    project_dir = root if root is not None else get_project_root()
    py_exec = sys.executable or "python"

    # In Docker container (/app), tests are in /app/tests. On host, tests might be in backend/tests.
    if (project_dir / "tests").is_dir():
        quick_test_target = "tests/test_cloud_ops.py"
    else:
        quick_test_target = "backend/tests/test_cloud_ops.py"

    return {
        "pytest_quick": [py_exec, "-m", "pytest", quick_test_target, "-q"],
        "pytest_full": [py_exec, "-m", "pytest", "-q"],
        "frontend_build": ["npm", "--prefix", "frontend", "run", "build"],
    }


def run_allowlisted_verification(command_key: str, timeout_seconds: int = 45) -> dict[str, Any]:
    project_root = get_project_root()
    commands = get_allowlisted_commands(project_root)
    if command_key not in commands:
        raise ValueError(f"Prohibited verification command key: {command_key}")

    cmd_args = commands[command_key]
    executable = cmd_args[0]

    # Pre-execution validation
    if not project_root.is_dir():
        return {
            "command_key": command_key,
            "cmd_args": cmd_args,
            "exit_code": -1,
            "success": False,
            "duration_ms": 0.0,
            "stdout": "",
            "stderr": f"Resolved working directory does not exist: {project_root}",
        }

    # If executable is not an absolute path or direct binary in PATH, verify it
    if not os.path.isabs(executable) and not shutil.which(executable):
        return {
            "command_key": command_key,
            "cmd_args": cmd_args,
            "exit_code": -1,
            "success": False,
            "duration_ms": 0.0,
            "stdout": "",
            "stderr": f"Required executable not found in runtime environment: {executable}",
        }

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd_args,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            stdin=subprocess.DEVNULL,
        )
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "command_key": command_key,
            "cmd_args": cmd_args,
            "exit_code": proc.returncode,
            "success": proc.returncode == 0,
            "duration_ms": duration_ms,
            "stdout": proc.stdout[:4000] if proc.stdout else "",
            "stderr": proc.stderr[:2000] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "command_key": command_key,
            "cmd_args": cmd_args,
            "exit_code": -1,
            "success": False,
            "duration_ms": duration_ms,
            "stdout": "",
            "stderr": f"Verification command timed out after {timeout_seconds} seconds.",
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "command_key": command_key,
            "cmd_args": cmd_args,
            "exit_code": -1,
            "success": False,
            "duration_ms": duration_ms,
            "stdout": "",
            "stderr": str(exc),
        }


# Global in-memory registry of SDLC tasks backed by AuditLog database events for recovery across restarts
_sdlc_tasks_store: dict[str, dict[str, Any]] = {}


def resolve_task_type(title: str, description: str, explicit_task_type: str | None = None) -> str:
    """Explicit task type takes precedence over keyword-based intent detection."""
    if explicit_task_type in ["verification", "development"]:
        return explicit_task_type

    # Keyword-based fallback detection
    verification_keywords = [
        "verify",
        "verification",
        "check",
        "audit",
        "inspect",
        "test only",
        "read only",
        "do not modify",
        "no code changes",
        "no mutation",
    ]
    text = f"{title} {description}".lower()
    if any(k in text for k in verification_keywords):
        return "verification"
    return "development"


def validate_plan_constraints(task_type: str, steps: list[dict[str, Any]]) -> None:
    """Server-side constraint validation: verification-only tasks must not contain mutation steps."""
    if task_type == "verification":
        forbidden_keywords = [
            "code implementation",
            "apply structured code",
            "apply code changes",
            "modify file",
            "file modification",
            "file mutation",
            "deployment",
        ]
        for step in steps:
            title = str(step.get("title", "")).lower()
            desc = str(step.get("description", "")).lower()
            # If step title indicates implementation or desc contains actionable mutation phrases
            if "implementation" in title or "modify" in title or "mutation" in title or "deploy" in title:
                raise ValueError("Plan violates task constraints: verification-only task must not contain implementation or mutation steps.")
            if any(term in desc for term in forbidden_keywords):
                raise ValueError("Plan violates task constraints: verification-only task must not contain implementation or mutation steps.")


def generate_sdlc_plan(
    task_id: str,
    title: str,
    description: str,
    target_files: list[str],
    task_type: str | None = None,
) -> dict[str, Any]:
    effective_type = resolve_task_type(title, description, task_type)
    validated_files = [f for f in target_files if is_safe_path(f)]

    if effective_type == "verification":
        raw_steps = [
            {
                "step_id": f"{task_id}-step-1",
                "title": "Scope & Constraint Inspection",
                "description": f"Inspect target scope ({', '.join(validated_files) or 'Project workspace'}), verify no files are to be altered, and validate constraints.",
                "target_files": validated_files,
                "risk_level": "low",
                "test_criteria": ["Confirm zero file mutation requirements are preserved"],
                "status": "pending",
            },
            {
                "step_id": f"{task_id}-step-2",
                "title": "Automated Test Suite Verification",
                "description": "Execute allowlisted pytest verification suite and collect results.",
                "target_files": validated_files,
                "risk_level": "low",
                "test_criteria": ["pytest exit_code == 0"],
                "status": "pending",
            },
            {
                "step_id": f"{task_id}-step-3",
                "title": "Build & Bundle Verification",
                "description": "Execute allowlisted frontend production build verification and bundle check.",
                "target_files": validated_files,
                "risk_level": "low",
                "test_criteria": ["npm run build exit_code == 0"],
                "status": "pending",
            },
        ]
        risk_assessment = "Read-only verification task. No files will be created, modified, or deleted."
    else:
        raw_steps = [
            {
                "step_id": f"{task_id}-step-1",
                "title": "Architecture & Constraint Verification",
                "description": f"Verify task scope, target files ({', '.join(validated_files) or 'None'}), and risk boundaries.",
                "target_files": validated_files,
                "risk_level": "low",
                "test_criteria": ["All target paths must resolve strictly within workspace"],
                "status": "pending",
            },
            {
                "step_id": f"{task_id}-step-2",
                "title": "Code Implementation Planning & Review",
                "description": f"Plan structured code changes for: {title}",
                "target_files": validated_files,
                "risk_level": "medium",
                "test_criteria": ["Implementation plan meets requirements without introducing lints"],
                "status": "pending",
            },
            {
                "step_id": f"{task_id}-step-3",
                "title": "Automated Verification & Build Test",
                "description": "Execute allowlisted pytest suite and frontend production build.",
                "target_files": validated_files,
                "risk_level": "low",
                "test_criteria": ["pytest exit_code == 0", "npm build exit_code == 0"],
                "status": "pending",
            },
        ]
        risk_assessment = "Standard development task. Mandatory human approval required before execution."

    validate_plan_constraints(effective_type, raw_steps)
    plan_hash = compute_plan_hash(raw_steps)

    return {
        "plan_id": f"plan-{task_id[:8]}",
        "plan_hash": plan_hash,
        "task_type": effective_type,
        "steps": raw_steps,
        "risk_assessment": risk_assessment,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }



def is_admin_user(user: User) -> bool:
    if not user or not getattr(user, "roles", None):
        return False
    return any(getattr(r, "name", "").lower() == "admin" for r in user.roles)

def create_sdlc_task(
    db: Session,
    user: User,
    title: str,
    description: str,
    target_files: list[str],
    task_type: str | None = None,
) -> dict[str, Any]:
    task_id = f"sdlc-{int(time.time() * 1000)}"
    plan = generate_sdlc_plan(task_id, title, description, target_files, task_type)

    task_data = {
        "task_id": task_id,
        "user_id": str(user.id),
        "user_email": user.email,
        "title": title,
        "description": description,
        "task_type": plan["task_type"],
        "target_files": [f for f in target_files if is_safe_path(f)],
        "status": "awaiting_approval",
        "plan": plan,
        "approved_plan_hash": None,
        "approved_by": None,
        "approved_at": None,
        "current_step_index": 0,
        "execution_results": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _sdlc_tasks_store[task_id] = task_data

    # Audit persistence
    db.add(
        AuditLog(
            actor_id=user.id,
            action="sdlc_task_created",
            entity_type="sdlc_task",
            entity_id=task_id,
            before=None,
            after={
                "title": title,
                "task_type": plan["task_type"],
                "status": "awaiting_approval",
                "plan_hash": plan["plan_hash"],
            },
        )
    )
    db.commit()

    return task_data


def get_sdlc_task(db: Session, task_id: str, user: User | None = None) -> dict[str, Any] | None:
    task = None
    if task_id in _sdlc_tasks_store:
        task = _sdlc_tasks_store[task_id]
    else:
        logs = list(
            db.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == "sdlc_task", AuditLog.entity_id == task_id)
                .order_by(AuditLog.created_at.asc())
            )
        )
        if logs:
            latest_log = logs[-1]
            after_data = latest_log.after if isinstance(latest_log.after, dict) else {}
            task = after_data.get("task_state")

    if task and user is not None:
        if not is_admin_user(user) and str(task.get("user_id")) != str(user.id):
            raise PermissionError(f"Access denied: you do not have permission to access SDLC task '{task_id}'.")

    return task


def approve_sdlc_task(
    db: Session,
    user: User,
    task_id: str,
    provided_plan_hash: str,
    action: str,  # "approve" or "reject"
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    task = get_sdlc_task(db, task_id)
    if not task:
        raise ValueError(f"SDLC task not found: {task_id}")

    if not is_admin_user(user):
        raise PermissionError("Access denied: only administrators may review or approve SDLC tasks.")

    if action == "approve" and task.get("user_id") and str(task["user_id"]) == str(user.id):
        raise PermissionError("Separation of duties violation: task creator cannot approve their own SDLC task.")

    current_plan = task.get("plan") or {}
    expected_hash = current_plan.get("plan_hash")

    if action == "reject":
        task["status"] = "rejected"
        task["rejection_reason"] = rejection_reason or "Rejected by human reviewer."
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        _sdlc_tasks_store[task_id] = task

        db.add(
            AuditLog(
                actor_id=user.id,
                action="sdlc_plan_rejected",
                entity_type="sdlc_task",
                entity_id=task_id,
                before={"status": "awaiting_approval"},
                after={"status": "rejected", "rejection_reason": task["rejection_reason"]},
            )
        )
        db.commit()
        return task

    # Approval branch: verify plan hash matches
    if not provided_plan_hash or provided_plan_hash != expected_hash:
        raise ValueError("Plan hash mismatch or plan changed after generation. Approval denied.")

    # Server-side constraint validation before approving
    task_type = task.get("task_type") or current_plan.get("task_type", "development")
    validate_plan_constraints(task_type, current_plan.get("steps", []))

    task["status"] = "approved"
    task["approved_plan_hash"] = expected_hash
    task["approved_by"] = str(user.id)
    task["approved_at"] = datetime.now(timezone.utc).isoformat()
    task["updated_at"] = datetime.now(timezone.utc).isoformat()

    for step in current_plan.get("steps", []):
        step["status"] = "approved"

    _sdlc_tasks_store[task_id] = task

    db.add(
        AuditLog(
            actor_id=user.id,
            action="sdlc_plan_approved",
            entity_type="sdlc_task",
            entity_id=task_id,
            before={"status": "awaiting_approval"},
            after={"status": "approved", "plan_hash": expected_hash},
        )
    )
    db.commit()

    return task


def regenerate_sdlc_plan(
    db: Session,
    user: User,
    task_id: str,
    task_type: str | None = None,
    title: str | None = None,
    description: str | None = None,
    target_files: list[str] | None = None,
) -> dict[str, Any]:
    task = get_sdlc_task(db, task_id)
    if not task:
        raise ValueError(f"SDLC task not found: {task_id}")

    if not is_admin_user(user) and str(task.get("user_id")) != str(user.id):
        raise PermissionError(f"Access denied: you do not have permission to regenerate SDLC task '{task_id}'.")

    eff_title = title or task.get("title", "Development Task")
    eff_desc = description or task.get("description", "")
    eff_files = target_files if target_files is not None else task.get("target_files", [])
    eff_type = task_type or task.get("task_type")

    # Generate new plan
    new_plan = generate_sdlc_plan(task_id, eff_title, eff_desc, eff_files, eff_type)

    old_status = task.get("status")
    task["title"] = eff_title
    task["description"] = eff_desc
    task["target_files"] = [f for f in eff_files if is_safe_path(f)]
    task["task_type"] = new_plan["task_type"]
    task["plan"] = new_plan
    task["status"] = "awaiting_approval"
    task["approved_plan_hash"] = None
    task["approved_by"] = None
    task["approved_at"] = None
    task["rejection_reason"] = None
    task["updated_at"] = datetime.now(timezone.utc).isoformat()

    _sdlc_tasks_store[task_id] = task

    db.add(
        AuditLog(
            actor_id=user.id,
            action="sdlc_plan_regenerated",
            entity_type="sdlc_task",
            entity_id=task_id,
            before={"status": old_status},
            after={
                "status": "awaiting_approval",
                "new_plan_hash": new_plan["plan_hash"],
                "task_type": new_plan["task_type"],
            },
        )
    )
    db.commit()

    return task


def execute_sdlc_task(
    db: Session,
    user: User,
    task_id: str,
    verification_command_key: str = "pytest_quick",
) -> dict[str, Any]:
    task = get_sdlc_task(db, task_id)
    if not task:
        raise ValueError(f"SDLC task not found: {task_id}")

    if not is_admin_user(user):
        raise PermissionError("Access denied: only administrators may execute SDLC tasks.")

    if task["status"] not in ["approved", "in_progress"]:
        raise ValueError(f"Cannot execute task in status '{task['status']}'. Task must be explicitly approved first.")

    current_plan = task.get("plan") or {}
    expected_hash = current_plan.get("plan_hash")

    # Double-check plan hash integrity
    if task.get("approved_plan_hash") != expected_hash:
        task["status"] = "awaiting_approval"
        task["approved_plan_hash"] = None
        raise ValueError("Plan contents were modified after approval. Re-approval required.")

    # Validate constraints before execution
    task_type = task.get("task_type") or current_plan.get("task_type", "development")
    validate_plan_constraints(task_type, current_plan.get("steps", []))

    task["status"] = "executing"
    task["updated_at"] = datetime.now(timezone.utc).isoformat()

    verif_res = run_allowlisted_verification(verification_command_key, timeout_seconds=45)

    steps = current_plan.get("steps", [])
    for idx, step in enumerate(steps):
        if verif_res["success"]:
            step["status"] = "completed"
            step["test_results"] = verif_res
            step["execution_logs"] = f"Step {idx+1} completed successfully. Exit code: 0."
        else:
            step["status"] = "failed"
            step["test_results"] = verif_res
            step["execution_logs"] = f"Step {idx+1} verification failed. Stderr: {verif_res['stderr'][:500]}"

    if verif_res["success"]:
        task["status"] = "completed"
    else:
        task["status"] = "failed"

    task["execution_results"].append(verif_res)
    task["updated_at"] = datetime.now(timezone.utc).isoformat()
    _sdlc_tasks_store[task_id] = task

    db.add(
        AuditLog(
            actor_id=user.id,
            action="sdlc_task_executed",
            entity_type="sdlc_task",
            entity_id=task_id,
            before={"status": "approved"},
            after={
                "status": task["status"],
                "verification_success": verif_res["success"],
                "exit_code": verif_res["exit_code"],
            },
        )
    )
    db.commit()

    return task
