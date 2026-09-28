from backend.app.services.runtime import AppraisalRuntime, RuntimeContext


def test_runtime_context_preserves_run_metadata_and_scope():
    context = RuntimeContext(
        faculty_id="faculty-123",
        cycle_id="cycle-456",
        run_id="run-789",
        thread_id="thread-abc",
        execution_scope={"faculty_id": "faculty-123", "cycle_id": "cycle-456"},
        memory_context={"last_total": 82.5},
        audit_context={"events": [{"event": "seed"}]},
    )

    assert context.faculty_id == "faculty-123"
    assert context.cycle_id == "cycle-456"
    assert context.run_id == "run-789"
    assert context.thread_id == "thread-abc"
    assert context.execution_scope["faculty_id"] == "faculty-123"
    assert context.memory_context == {"last_total": 82.5}
    assert context.audit_context["events"] == [{"event": "seed"}]


def test_runtime_context_reuses_supplied_thread_id():
    runtime = AppraisalRuntime()
    context = runtime.create_context(
        faculty_id="faculty-1",
        cycle_id="cycle-1",
        run_id="run-1",
        thread_id="existing-thread",
    )

    assert context.thread_id == "existing-thread"
    assert context.run_id == "run-1"


def test_runtime_uses_run_id_as_default_thread_id():
    runtime = AppraisalRuntime()
    context = runtime.create_context(
        faculty_id="faculty-2",
        cycle_id="cycle-2",
        run_id="run-2",
    )

    assert context.thread_id == "run-2"


def test_snapshot_returns_serializable_runtime_summary():
    runtime = AppraisalRuntime()
    context = runtime.create_context(
        faculty_id="faculty-3",
        cycle_id="cycle-3",
        run_id="run-3",
        memory_context={"history": ["old"]},
    )

    snapshot = runtime.snapshot(
        context,
        {
            "next_action": "await_human",
            "approval": {"status": "approved"},
            "validation_result": {"ok": True},
            "audit_events": [{"event": "graph_step"}],
        },
    )

    assert isinstance(snapshot, dict)
    assert snapshot["run_id"] == "run-3"
    assert snapshot["thread_id"] == "run-3"
    assert snapshot["faculty_id"] == "faculty-3"
    assert snapshot["cycle_id"] == "cycle-3"
    assert snapshot["next_action"] == "await_human"
    assert snapshot["approval"] == {"status": "approved"}
    assert snapshot["validation_result"] == {"ok": True}
    assert snapshot["audit_events"]


def test_runtime_audit_helpers_record_runtime_events():
    runtime = AppraisalRuntime()
    context = runtime.create_context(
        faculty_id="faculty-4",
        cycle_id="cycle-4",
        run_id="run-4",
    )

    start_event = runtime.record_start(context, source="runtime")
    approval_event = runtime.record_approval_required(context, reviewer="hod@example.com")
    resume_event = runtime.record_resume(context, resumed_from="interrupt")

    assert start_event["event"] == "run_started"
    assert approval_event["event"] == "approval_required"
    assert resume_event["event"] == "run_resumed"
    assert len(context.audit_context["events"]) == 3


def test_runtime_approval_required_and_resume_context_are_serializable():
    runtime = AppraisalRuntime()
    context = runtime.create_context(
        faculty_id="faculty-approval",
        cycle_id="cycle-approval",
        run_id="run-approval",
        thread_id="thread-approval",
    )

    approval_event = runtime.record_approval_required(context, state="awaiting_review")
    resume_context = runtime.prepare_resume(context, action="approve", reason="approved", reviewer="hod@example.com")

    assert approval_event["event"] == "approval_required"
    assert approval_event["run_id"] == "run-approval"
    assert approval_event["thread_id"] == "thread-approval"
    assert resume_context["run_id"] == "run-approval"
    assert resume_context["thread_id"] == "thread-approval"
    assert resume_context["faculty_id"] == "faculty-approval"
    assert resume_context["cycle_id"] == "cycle-approval"
    assert resume_context["action"] == "approve"
    assert resume_context["reason"] == "approved"


def test_snapshot_does_not_expose_raw_orm_objects():
    runtime = AppraisalRuntime()
    context = runtime.create_context(
        faculty_id="faculty-5",
        cycle_id="cycle-5",
        run_id="run-5",
    )

    snapshot = runtime.snapshot(
        context,
        {
            "approval": {"status": "rejected"},
            "validation_result": {"ok": False},
            "audit_events": [{"event": "runtime_only"}],
        },
    )

    assert isinstance(snapshot["approval"], dict)
    assert isinstance(snapshot["validation_result"], dict)
    assert isinstance(snapshot["audit_events"], list)
    assert all(not hasattr(item, "__dict__") for item in snapshot["audit_events"])
