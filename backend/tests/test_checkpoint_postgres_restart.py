"""SEC-02 Stage 2: PostgreSQL LangGraph Checkpoint Restart Durability Integration Tests.

Opt-in test suite verifying cross-restart checkpoint preservation, reviewer propagation,
and duplicate prevention using a dedicated, disposable PostgreSQL test database.

SAFETY RESTRICTIONS:
- This test MUST NEVER run against the application's active database (port 15432 / 'appraisal').
- It requires an explicitly defined DISPOSABLE_POSTGRES_TEST_URL targeting an isolated disposable test database.
- If DISPOSABLE_POSTGRES_TEST_URL is not set or matches the app database, all tests skip safely.
"""

import os
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from app.agents.graph import build_checkpointed_graph, get_checkpointed_graph
from app.agents.state import AppraisalGraphState
from app.core.checkpointer import clean_pg_url, is_postgres_url
from app.core.config import get_settings


def _get_disposable_test_pg_url() -> str | None:
    """Retrieve and validate the dedicated disposable PostgreSQL test URL.

    Enforces strict safety barriers: skips if unset, malformed, or pointing
    to the active application database or default appraisal database.
    """
    raw_url = os.environ.get("DISPOSABLE_POSTGRES_TEST_URL", "").strip()
    if not raw_url:
        return None

    if not is_postgres_url(raw_url):
        pytest.skip(
            f"DISPOSABLE_POSTGRES_TEST_URL is not a valid PostgreSQL URL: {raw_url}"
        )

    clean_test = clean_pg_url(raw_url).lower()
    app_url = clean_pg_url(get_settings().database_url).lower()

    # Safety guard: Never run against the live app database or default appraisal db on 15432
    if clean_test == app_url or ("15432" in clean_test and "appraisal" in clean_test):
        pytest.skip(
            "DISPOSABLE_POSTGRES_TEST_URL points to the active application database "
            "or default appraisal database (port 15432). A separate dedicated disposable "
            "test database is required to protect application state."
        )

    # Verify connectivity to the dedicated disposable test database
    try:
        with psycopg.connect(clean_pg_url(raw_url), connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as exc:
        pytest.skip(
            f"Unable to connect to dedicated disposable test PostgreSQL at {raw_url}: {exc}"
        )

    return raw_url


@pytest.fixture
def disposable_pg_url() -> str:
    url = _get_disposable_test_pg_url()
    if not url:
        pytest.skip(
            "Skipping PostgreSQL restart durability test: DISPOSABLE_POSTGRES_TEST_URL "
            "is not set. Set this environment variable pointing to a dedicated disposable "
            "PostgreSQL database to run this test."
        )
    return url


@pytest.mark.no_checkpointer_isolation
def test_postgres_checkpoint_survives_restart_and_propagates_reviewer(disposable_pg_url: str):
    """Lifecycle test:
    1. Initialize PostgreSQL pool_1 and PostgresSaver_1.
    2. Compile graph_1 with saver_1.
    3. Interrupt disposable thread at human_gate.
    4. Verify checkpoint is written to PostgreSQL checkpoints table.
    5. Simulate container restart: close pool_1 completely, create fresh pool_2, fresh saver_2,
       and compile fresh graph_2 (avoiding stale saver references).
    6. Resume the interrupted thread with reviewer metadata.
    7. Assert reviewer propagation, approved status, score invariance, and no duplicate side effects.
    8. Behavior-based duplicate prevention: verify repeat resume is idempotent, leaves the approval
       and score untouched, and writes zero additional checkpoints.
    9. Clean up only the specific test thread records.
    """
    thread_id = f"test-sec02-{uuid.uuid4().hex[:12]}"
    dsn = clean_pg_url(disposable_pg_url)

    pool_1 = None
    pool_2 = None

    try:
        # Phase 1: First container lifecycle
        pool_1 = ConnectionPool(
            conninfo=dsn,
            open=False,
            min_size=1,
            max_size=2,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        pool_1.open()
        saver_1 = PostgresSaver(pool_1)
        saver_1.setup()

        graph_1 = build_checkpointed_graph(checkpointer=saver_1)

        initial_input: AppraisalGraphState = {
            "run_id": f"run-{uuid.uuid4().hex[:8]}",
            "faculty_id": f"fac-{uuid.uuid4().hex[:8]}",
            "faculty_name": "Dr. Uday Kulkarni",
            "cycle_id": f"cycle-{uuid.uuid4().hex[:8]}",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "all_activities": [
                {
                    "id": 1,
                    "category": "teaching",
                    "activity_type": "course_delivery",
                    "title": "Software Engineering",
                    "evidence_ids": [101],
                    "evidence_statuses": ["valid"],
                }
            ],
        }

        # Execute until human_gate interrupt
        state_1 = graph_1.invoke(
            initial_input,
            config={"configurable": {"thread_id": thread_id}},
        )

        assert state_1.get("next_action") == "await_human"
        assert state_1.get("approval") is None
        score_1 = state_1.get("score_result") or {}
        initial_score_total = score_1.get("total")
        assert initial_score_total is not None
        assert initial_score_total > 0

        # Verify checkpoint exists in PostgreSQL
        with psycopg.connect(dsn) as verify_conn:
            with verify_conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM checkpoints WHERE thread_id = %s",
                    (thread_id,),
                )
                row_count = cur.fetchone()[0]
                assert row_count >= 1, f"Expected checkpoint rows for thread {thread_id}"

        # Phase 2: Simulate backend container restart (tear down container 1)
        pool_1.close(timeout=3)
        assert pool_1.closed is True

        # Phase 3: Second container lifecycle (fresh pool, fresh saver, fresh graph)
        # Avoid stale saver reference by compiling a fresh graph with saver_2
        pool_2 = ConnectionPool(
            conninfo=dsn,
            open=False,
            min_size=1,
            max_size=2,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        pool_2.open()
        saver_2 = PostgresSaver(pool_2)
        saver_2.setup()

        # Crucial safeguard: compile a fresh graph with saver_2 (stale checkpointer avoidance)
        graph_2 = build_checkpointed_graph(checkpointer=saver_2)

        # Resume the interrupted thread
        reviewer_email = "hod-durability@demo.local"
        resume_payload = {
            "action": "approve",
            "reviewer": reviewer_email,
            "reason": "Approved post-restart durability",
        }

        resumed_state = graph_2.invoke(
            Command(resume=resume_payload),
            config={"configurable": {"thread_id": thread_id}},
        )

        # Verify state restoration and reviewer propagation
        approval = resumed_state.get("approval") or {}
        assert approval.get("action") == "approve"
        assert approval.get("status") == "approved"
        assert approval.get("reviewer") == reviewer_email, (
            f"Expected reviewer {reviewer_email}, got {approval.get('reviewer')}"
        )
        assert approval.get("reason") == "Approved post-restart durability"
        assert resumed_state.get("next_action") == "approved"

        # Verify score invariance: score was not recalculated or modified
        resumed_score = resumed_state.get("score_result") or {}
        assert resumed_score.get("total") == initial_score_total

        # Verify absence of duplicate node executions (e.g., aura_prepare was not re-run)
        audit_events = resumed_state.get("audit_events") or []
        aura_events = [e for e in audit_events if e.get("event") == "aura_prepare"]
        assert len(aura_events) == 1, "aura_prepare should not be re-executed on resume"

        # Capture terminal checkpoint metadata
        state_snap_1 = graph_2.get_state({"configurable": {"thread_id": thread_id}})
        checkpoint_id_1 = state_snap_1.config["configurable"]["checkpoint_id"]
        assert state_snap_1.next == (), "Thread must be in terminal state"

        # Phase 4: Behavior-based duplicate resume verification
        # When a thread has reached its terminal state, LangGraph performs an idempotent read:
        # It does not execute nodes, ignores contradictory resume payloads, and writes no new checkpoints.
        conflicting_payload = {
            "action": "reject",
            "reviewer": "malicious-overrule@demo.local",
            "reason": "Attempting illegal state modification on completed thread",
        }
        repeat_resumed = graph_2.invoke(
            Command(resume=conflicting_payload),
            config={"configurable": {"thread_id": thread_id}},
        )

        # 4a: Approval state is immutable (contradictory payload was safely ignored)
        repeat_approval = repeat_resumed.get("approval") or {}
        assert repeat_approval.get("action") == "approve"
        assert repeat_approval.get("status") == "approved"
        assert repeat_approval.get("reviewer") == reviewer_email
        assert repeat_approval.get("reason") == "Approved post-restart durability"
        assert repeat_resumed.get("next_action") == "approved"

        # 4b: Score result remains identical
        repeat_score = repeat_resumed.get("score_result") or {}
        assert repeat_score.get("total") == initial_score_total

        # 4c: No nodes were re-executed (audit events count unchanged)
        assert len(repeat_resumed.get("audit_events") or []) == len(audit_events)

        # 4d: Checkpoint was not modified or duplicated in PostgreSQL
        state_snap_2 = graph_2.get_state({"configurable": {"thread_id": thread_id}})
        assert state_snap_2.config["configurable"]["checkpoint_id"] == checkpoint_id_1

    finally:
        # Guaranteed cleanup of pools and worker threads
        if pool_1 is not None and not pool_1.closed:
            try:
                pool_1.close(timeout=3)
            except Exception:
                pass
        if pool_2 is not None and not pool_2.closed:
            try:
                pool_2.close(timeout=3)
            except Exception:
                pass

        # Phase 5: Clean up ONLY the disposable records created by this test
        try:
            with psycopg.connect(dsn) as cleanup_conn:
                with cleanup_conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM checkpoint_writes WHERE thread_id = %s",
                        (thread_id,),
                    )
                    cur.execute(
                        "DELETE FROM checkpoint_blobs WHERE thread_id = %s",
                        (thread_id,),
                    )
                    cur.execute(
                        "DELETE FROM checkpoints WHERE thread_id = %s",
                        (thread_id,),
                    )
        except Exception:
            pass


@pytest.mark.no_checkpointer_isolation
def test_stale_checkpointer_guard_demonstrates_isolation(disposable_pg_url: str):
    """Verify that compiling a new graph with a fresh saver avoids the closed pool."""
    dsn = clean_pg_url(disposable_pg_url)

    pool_old = None
    pool_new = None

    try:
        pool_old = ConnectionPool(
            conninfo=dsn,
            open=False,
            min_size=1,
            max_size=2,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        pool_old.open()
        saver_old = PostgresSaver(pool_old)
        saver_old.setup()
        graph_old = build_checkpointed_graph(checkpointer=saver_old)

        # Close old pool
        pool_old.close(timeout=3)
        assert pool_old.closed is True

        # Attempting to use graph_old fails because pool is closed
        with pytest.raises(Exception):
            graph_old.invoke(
                {"run_id": "dummy", "attempt": 0, "max_attempts": 3},
                config={"configurable": {"thread_id": "dummy-thread"}},
            )

        # Fresh pool and fresh graph compilation succeeds
        pool_new = ConnectionPool(
            conninfo=dsn,
            open=False,
            min_size=1,
            max_size=2,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        pool_new.open()
        saver_new = PostgresSaver(pool_new)
        saver_new.setup()
        graph_new = build_checkpointed_graph(checkpointer=saver_new)
        assert graph_new.checkpointer is saver_new

    finally:
        if pool_old is not None and not pool_old.closed:
            try:
                pool_old.close(timeout=3)
            except Exception:
                pass
        if pool_new is not None and not pool_new.closed:
            try:
                pool_new.close(timeout=3)
            except Exception:
                pass
