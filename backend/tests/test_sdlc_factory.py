import pytest
from sqlalchemy.orm import Session

from pathlib import Path
from app.models import AuditLog
from app.services.sdlc_factory import (
    approve_sdlc_task,
    compute_plan_hash,
    create_sdlc_task,
    execute_sdlc_task,
    get_allowlisted_commands,
    get_project_root,
    is_safe_path,
    run_allowlisted_verification,
)
from .conftest import auth_headers, login, make_user


def test_sdlc_path_traversal_prevention():
    assert is_safe_path("backend/app/main.py") is True
    assert is_safe_path("frontend/src/api/client.js") is True
    assert is_safe_path("../secret.txt") is False
    assert is_safe_path("../../Windows/System32") is False
    assert is_safe_path("C:/Windows/System32/cmd.exe") is False
    assert is_safe_path("/etc/shadow") is False


def test_sdlc_project_root_resolution_and_commands(monkeypatch, tmp_path):
    # Default resolution
    resolved_root = get_project_root()
    assert resolved_root.is_dir()
    assert (resolved_root / "backend").is_dir() or (resolved_root / "app").is_dir()

    # Commands resolve dynamically without hardcoded windows virtualenv strings
    commands = get_allowlisted_commands(resolved_root)
    assert "pytest_quick" in commands
    assert "pytest_full" in commands
    assert "frontend_build" in commands
    assert commands["pytest_quick"][1] == "-m"
    assert commands["pytest_quick"][2] == "pytest"

    # Environment variable override test
    monkeypatch.setenv("SDLC_PROJECT_ROOT", str(tmp_path))
    assert get_project_root() == tmp_path.resolve()

    # Path safety under explicit base root
    mock_container_root = tmp_path / "mock_app"
    mock_container_root.mkdir()
    (mock_container_root / "tests").mkdir()
    assert is_safe_path("tests/test_demo.py", base_root=mock_container_root) is True
    assert is_safe_path(str(mock_container_root / "tests" / "test_demo.py"), base_root=mock_container_root) is True
    assert is_safe_path("/etc/passwd", base_root=mock_container_root) is False
    assert is_safe_path("C:/Windows/System32", base_root=mock_container_root) is False
    assert is_safe_path("../../outside.txt", base_root=mock_container_root) is False


def test_sdlc_prohibited_command_rejection():
    with pytest.raises(ValueError, match="Prohibited verification command key"):
        run_allowlisted_verification("rm -rf /")

    with pytest.raises(ValueError, match="Prohibited verification command key"):
        run_allowlisted_verification("git push origin main")


def test_sdlc_task_creation_and_plan(db_session: Session):
    user = make_user(db_session, "sdlc_dev@demo.local", ["admin"])
    task = create_sdlc_task(
        db=db_session,
        user=user,
        title="Add L11 Unit Tests",
        description="Create unit tests for Agentic SDLC Factory.",
        target_files=["backend/tests/test_sdlc_factory.py"],
    )

    assert task["task_id"].startswith("sdlc-")
    assert task["status"] == "awaiting_approval"
    assert "plan" in task
    assert "plan_hash" in task["plan"]
    assert len(task["plan"]["steps"]) == 3


def test_sdlc_plan_hash_approval_enforcement(db_session: Session):
    creator = make_user(db_session, "sdlc_creator_hash@demo.local", ["faculty"])
    approver = make_user(db_session, "sdlc_approver@demo.local", ["admin"])
    task = create_sdlc_task(
        db=db_session,
        user=creator,
        title="Refactor API Routing",
        description="Clean up router registrations.",
        target_files=["backend/app/main.py"],
    )

    # Wrong hash must be rejected
    with pytest.raises(ValueError, match="Plan hash mismatch"):
        approve_sdlc_task(
            db=db_session,
            user=approver,
            task_id=task["task_id"],
            provided_plan_hash="invalid_hash_12345",
            action="approve",
        )

    # Correct hash succeeds
    correct_hash = task["plan"]["plan_hash"]
    approved_task = approve_sdlc_task(
        db=db_session,
        user=approver,
        task_id=task["task_id"],
        provided_plan_hash=correct_hash,
        action="approve",
    )
    assert approved_task["status"] == "approved"
    assert approved_task["approved_plan_hash"] == correct_hash
    assert approved_task["approved_by"] == str(approver.id)


def test_sdlc_no_execution_after_rejection(db_session: Session):
    creator = make_user(db_session, "sdlc_creator_rej@demo.local", ["faculty"])
    approver = make_user(db_session, "sdlc_rejector@demo.local", ["admin"])
    task = create_sdlc_task(
        db=db_session,
        user=creator,
        title="Risky Structural Refactor",
        description="Drop legacy database tables.",
        target_files=["backend/app/models/base.py"],
    )

    correct_hash = task["plan"]["plan_hash"]
    rejected_task = approve_sdlc_task(
        db=db_session,
        user=approver,
        task_id=task["task_id"],
        provided_plan_hash=correct_hash,
        action="reject",
        rejection_reason="High risk architectural modification rejected by security policy.",
    )
    assert rejected_task["status"] == "rejected"

    # Execution of rejected task must fail
    with pytest.raises(ValueError, match="Cannot execute task in status 'rejected'"):
        execute_sdlc_task(db=db_session, user=approver, task_id=task["task_id"])


def test_sdlc_rbac_authorization(client, db_session: Session):
    # Non-authorized user or student cannot access SDLC Factory API
    unauth_user = make_user(db_session, "unauth@demo.local", ["student"])
    token = login(client, "unauth@demo.local")

    res = client.post(
        "/api/v1/sdlc/tasks",
        headers=auth_headers(token),
        json={
            "title": "Unauthorized Task",
            "description": "Attempt to create task without permission.",
            "target_files": [],
        },
    )
    assert res.status_code == 403


def test_sdlc_execution_and_verification_report(client, db_session: Session):
    creator = make_user(db_session, "sdlc_creator_exec@demo.local", ["faculty"])
    approver = make_user(db_session, "sdlc_exec_admin@demo.local", ["admin"])
    creator_token = login(client, creator.email)
    approver_token = login(client, approver.email)

    # 1. Create task
    c_res = client.post(
        "/api/v1/sdlc/tasks",
        headers=auth_headers(creator_token),
        json={
            "title": "Execute Verification Test",
            "description": "Run allowlisted pytest suite for L11 verification.",
            "target_files": ["backend/tests/test_sdlc_factory.py"],
        },
    )
    assert c_res.status_code == 200, c_res.text
    task_data = c_res.json()
    task_id = task_data["task_id"]
    plan_hash = task_data["plan"]["plan_hash"]

    # 2. Cannot execute prior to approval
    e_fail = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/execute",
        headers=auth_headers(approver_token),
        json={"verification_command_key": "pytest_quick"},
    )
    assert e_fail.status_code == 400

    # 3. Approve task with correct plan hash (by distinct approver)
    a_res = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/approval",
        headers=auth_headers(approver_token),
        json={"plan_hash": plan_hash, "action": "approve"},
    )
    assert a_res.status_code == 200, a_res.text
    assert a_res.json()["status"] == "approved"
    assert a_res.json()["approved_by"] == str(approver.id)

    # 4. Execute approved task
    e_res = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/execute",
        headers=auth_headers(approver_token),
        json={"verification_command_key": "pytest_quick"},
    )
    assert e_res.status_code == 200, e_res.text
    exec_data = e_res.json()
    assert exec_data["status"] in ["completed", "failed"]
    assert len(exec_data["execution_results"]) > 0
    res_item = exec_data["execution_results"][0]
    assert "exit_code" in res_item
    assert "duration_ms" in res_item


def test_sdlc_audit_trail(db_session: Session):
    creator = make_user(db_session, "sdlc_audit_creator@demo.local", ["faculty"])
    approver = make_user(db_session, "sdlc_audit_user@demo.local", ["admin"])
    task = create_sdlc_task(
        db=db_session,
        user=creator,
        title="Audit Trail Verification",
        description="Verify audit log entries created during task lifecycle.",
        target_files=["backend/app/services/sdlc_factory.py"],
    )

    plan_hash = task["plan"]["plan_hash"]
    approve_sdlc_task(
        db=db_session,
        user=approver,
        task_id=task["task_id"],
        provided_plan_hash=plan_hash,
        action="approve",
    )

    logs = list(
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == task["task_id"])
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    assert len(logs) >= 2
    actions = [l.action for l in logs]
    assert "sdlc_task_created" in actions
    assert "sdlc_plan_approved" in actions


def test_sdlc_verification_only_plan_has_no_code_implementation_step(db_session: Session):
    user = make_user(db_session, "verify_tester@demo.local", ["admin"])
    task = create_sdlc_task(
        db=db_session,
        user=user,
        title="Verify Backend and Frontend Build",
        description="Verify existing test suites and production build without modifying any code.",
        target_files=[],
    )

    assert task["task_type"] == "verification"
    plan_steps = task["plan"]["steps"]
    step_titles = [s["title"].lower() for s in plan_steps]
    step_descriptions = [s["description"].lower() for s in plan_steps]

    # Must contain inspection and verification steps
    assert any("scope & constraint inspection" in t for t in step_titles)
    assert any("automated test suite verification" in t for t in step_titles)

    # Must NOT contain code implementation or mutation steps
    for t in step_titles:
        assert "code implementation" not in t
        assert "code change" not in t
    for d in step_descriptions:
        assert "apply structured code changes" not in d


def test_sdlc_development_plan_classification(db_session: Session):
    user = make_user(db_session, "dev_planner@demo.local", ["admin"])
    task = create_sdlc_task(
        db=db_session,
        user=user,
        title="Implement New Export Feature",
        description="Write new CSV export route and data serializer.",
        target_files=["backend/app/api/export.py"],
        task_type="development",
    )

    assert task["task_type"] == "development"
    step_titles = [s["title"] for s in task["plan"]["steps"]]
    assert "Code Implementation Planning & Review" in step_titles


def test_sdlc_explicit_task_type_overrides_keywords(db_session: Session):
    user = make_user(db_session, "override_tester@demo.local", ["admin"])
    # Title has development keywords ("Implement and Add"), but explicit task_type="verification"
    task = create_sdlc_task(
        db=db_session,
        user=user,
        title="Implement and Add Feature",
        description="Check modules only.",
        target_files=[],
        task_type="verification",
    )

    assert task["task_type"] == "verification"
    step_titles = [s["title"] for s in task["plan"]["steps"]]
    assert "Code Implementation Planning & Review" not in step_titles
    assert "Scope & Constraint Inspection" in step_titles


def test_sdlc_constraint_validation_rejects_violating_plan(db_session: Session):
    from app.services.sdlc_factory import validate_plan_constraints

    violating_steps = [
        {"title": "Code Implementation & Integration", "description": "Apply code changes"}
    ]
    with pytest.raises(ValueError, match="Plan violates task constraints"):
        validate_plan_constraints("verification", violating_steps)


def test_sdlc_plan_regeneration_resets_hash_and_approval(client, db_session: Session):
    creator = make_user(db_session, "regen_creator@demo.local", ["faculty"])
    approver = make_user(db_session, "regen_admin@demo.local", ["admin"])
    creator_token = login(client, creator.email)
    approver_token = login(client, approver.email)

    # 1. Create development task
    c_res = client.post(
        "/api/v1/sdlc/tasks",
        headers=auth_headers(creator_token),
        json={
            "title": "Initial Task",
            "description": "Initial task description.",
            "task_type": "development",
            "target_files": [],
        },
    )
    assert c_res.status_code == 200
    task_id = c_res.json()["task_id"]
    initial_hash = c_res.json()["plan"]["plan_hash"]

    # 2. Approve initial plan (by distinct approver)
    a_res = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/approval",
        headers=auth_headers(approver_token),
        json={"plan_hash": initial_hash, "action": "approve"},
    )
    assert a_res.status_code == 200
    assert a_res.json()["status"] == "approved"

    # 3. Regenerate task as verification-only by creator
    r_res = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/regenerate",
        headers=auth_headers(creator_token),
        json={"task_type": "verification"},
    )
    assert r_res.status_code == 200
    regen_data = r_res.json()
    new_hash = regen_data["plan"]["plan_hash"]

    # Hash must change, status must reset to awaiting_approval, and previous approval invalidated
    assert new_hash != initial_hash
    assert regen_data["status"] == "awaiting_approval"
    assert regen_data["approved_plan_hash"] is None
    assert regen_data["task_type"] == "verification"

    # 4. Old approval must not allow execution
    e_fail = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/execute",
        headers=auth_headers(approver_token),
        json={"verification_command_key": "pytest_quick"},
    )
    assert e_fail.status_code == 400



def test_sdlc_creator_cannot_approve_own_task_service_and_api(client, db_session: Session):
    creator_admin = make_user(db_session, "creator_admin_sod@demo.local", ["admin"])
    independent_admin = make_user(db_session, "independent_admin_sod@demo.local", ["admin"])
    creator_token = login(client, creator_admin.email)
    independent_token = login(client, independent_admin.email)

    task = create_sdlc_task(
        db=db_session,
        user=creator_admin,
        title="Self Approval Block Test",
        description="Verify separation of duties blocks self approval.",
        target_files=["backend/app/main.py"],
    )
    plan_hash = task["plan"]["plan_hash"]

    # Service layer must reject self-approval
    with pytest.raises(PermissionError, match="Separation of duties violation: task creator cannot approve their own SDLC task"):
        approve_sdlc_task(
            db=db_session,
            user=creator_admin,
            task_id=task["task_id"],
            provided_plan_hash=plan_hash,
            action="approve",
        )

    # API layer must return 403 Forbidden with separation of duties message
    api_self_approve = client.post(
        f"/api/v1/sdlc/tasks/{task['task_id']}/approval",
        headers=auth_headers(creator_token),
        json={"plan_hash": plan_hash, "action": "approve"},
    )
    assert api_self_approve.status_code == 403
    assert "Separation of duties violation" in api_self_approve.json()["detail"]

    # Distinct admin can approve
    api_valid_approve = client.post(
        f"/api/v1/sdlc/tasks/{task['task_id']}/approval",
        headers=auth_headers(independent_token),
        json={"plan_hash": plan_hash, "action": "approve"},
    )
    assert api_valid_approve.status_code == 200
    assert api_valid_approve.json()["status"] == "approved"
    assert api_valid_approve.json()["approved_by"] == str(independent_admin.id)


def test_sdlc_idor_cross_user_access_prohibited(client, db_session: Session):
    user_a = make_user(db_session, "user_a_idor@demo.local", ["faculty"])
    user_b = make_user(db_session, "user_b_idor@demo.local", ["faculty"])
    admin_user = make_user(db_session, "admin_user_idor@demo.local", ["admin"])

    token_a = login(client, user_a.email)
    token_b = login(client, user_b.email)
    token_admin = login(client, admin_user.email)

    # User A creates a task
    c_res = client.post(
        "/api/v1/sdlc/tasks",
        headers=auth_headers(token_a),
        json={
            "title": "Private User A Task",
            "description": "Sensitive task details owned by User A.",
            "target_files": [],
        },
    )
    assert c_res.status_code == 200
    task_id = c_res.json()["task_id"]

    # User B (different faculty) cannot view User A's task
    get_b = client.get(f"/api/v1/sdlc/tasks/{task_id}", headers=auth_headers(token_b))
    assert get_b.status_code == 403
    assert "Access denied" in get_b.json()["detail"]

    # User B cannot regenerate User A's task
    regen_b = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/regenerate",
        headers=auth_headers(token_b),
        json={"description": "Tampered description"},
    )
    assert regen_b.status_code == 403
    assert "Access denied" in regen_b.json()["detail"]

    # User B cannot approve User A's task (requires admin role)
    approve_b = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/approval",
        headers=auth_headers(token_b),
        json={"plan_hash": "dummy", "action": "approve"},
    )
    assert approve_b.status_code == 403

    # User B cannot execute User A's task (requires admin role)
    exec_b = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/execute",
        headers=auth_headers(token_b),
        json={"verification_command_key": "pytest_quick"},
    )
    assert exec_b.status_code == 403

    # User A CAN view and regenerate their own task
    get_a = client.get(f"/api/v1/sdlc/tasks/{task_id}", headers=auth_headers(token_a))
    assert get_a.status_code == 200
    assert get_a.json()["title"] == "Private User A Task"

    regen_a = client.post(
        f"/api/v1/sdlc/tasks/{task_id}/regenerate",
        headers=auth_headers(token_a),
        json={"title": "Updated User A Task"},
    )
    assert regen_a.status_code == 200
    assert regen_a.json()["title"] == "Updated User A Task"

    # Admin CAN view any task
    get_admin = client.get(f"/api/v1/sdlc/tasks/{task_id}", headers=auth_headers(token_admin))
    assert get_admin.status_code == 200
    assert get_admin.json()["task_id"] == task_id


def test_sdlc_non_admin_cannot_approve_or_execute(client, db_session: Session):
    creator = make_user(db_session, "creator_no_admin@demo.local", ["faculty"])
    reviewer_faculty = make_user(db_session, "reviewer_faculty@demo.local", ["faculty"])
    creator_token = login(client, creator.email)
    faculty_token = login(client, reviewer_faculty.email)

    task = create_sdlc_task(
        db=db_session,
        user=creator,
        title="Role Enforcement Test",
        description="Verify only admin can approve or execute.",
        target_files=[],
    )
    plan_hash = task["plan"]["plan_hash"]

    # Service layer rejects non-admin approval
    with pytest.raises(PermissionError, match="Access denied: only administrators may review or approve SDLC tasks"):
        approve_sdlc_task(
            db=db_session,
            user=reviewer_faculty,
            task_id=task["task_id"],
            provided_plan_hash=plan_hash,
            action="approve",
        )

    # API layer rejects non-admin approval with 403
    resp_approve = client.post(
        f"/api/v1/sdlc/tasks/{task['task_id']}/approval",
        headers=auth_headers(faculty_token),
        json={"plan_hash": plan_hash, "action": "approve"},
    )
    assert resp_approve.status_code == 403

    # Service layer rejects non-admin execution
    with pytest.raises(PermissionError, match="Access denied: only administrators may execute SDLC tasks"):
        execute_sdlc_task(
            db=db_session,
            user=reviewer_faculty,
            task_id=task["task_id"],
        )

    # API layer rejects non-admin execution with 403
    resp_exec = client.post(
        f"/api/v1/sdlc/tasks/{task['task_id']}/execute",
        headers=auth_headers(faculty_token),
        json={"verification_command_key": "pytest_quick"},
    )
    assert resp_exec.status_code == 403
