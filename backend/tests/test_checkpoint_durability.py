"""SEC-02 Stage 1: Focused regression tests for LangGraph checkpointer state durability."""

from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

import app.core.checkpointer as cp_module
import app.core.config as config_module
from app.agents.graph import build_checkpointed_graph
from app.core.config import Settings

SAFE_PROD_SECRET = "production-test-secret-at-least-32-chars-long-123456"


@pytest.mark.no_checkpointer_isolation
def test_postgres_configuration_does_not_silently_select_memory_saver(monkeypatch):
    """Verify that when PostgreSQL is configured, build_checkpointed_graph selects
    PostgresSaver and never silently falls back to MemorySaver.
    """
    test_settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+psycopg://appraisal:appraisal@localhost:5432/appraisal",
        jwt_secret=SAFE_PROD_SECRET,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)

    try:
        graph = build_checkpointed_graph()
        assert isinstance(graph.checkpointer, PostgresSaver), (
            f"Expected PostgresSaver when PostgreSQL is configured, got {type(graph.checkpointer)}"
        )
        assert not isinstance(graph.checkpointer, MemorySaver)
    finally:
        cp_module.close_checkpointer()


@pytest.mark.no_checkpointer_isolation
def test_sqlite_configuration_selects_memory_saver(monkeypatch):
    """Verify that when SQLite is configured in development/test, build_checkpointed_graph selects MemorySaver."""
    test_settings = Settings(
        _env_file=None,
        app_env="development",
        database_url="sqlite:///./test.db",
        jwt_secret=SAFE_PROD_SECRET,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)

    graph = build_checkpointed_graph()
    assert isinstance(graph.checkpointer, MemorySaver), (
        f"Expected MemorySaver when SQLite is configured, got {type(graph.checkpointer)}"
    )


@pytest.mark.no_checkpointer_isolation
def test_sqlite_in_production_raises_value_error(monkeypatch):
    """Verify that SQLite is explicitly rejected for checkpointer persistence in production."""
    test_settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="sqlite:///./test.db",
        jwt_secret=SAFE_PROD_SECRET,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)

    with pytest.raises(
        ValueError,
        match="SQLite database URL is not permitted for LangGraph checkpoint persistence in production",
    ):
        build_checkpointed_graph()


@pytest.mark.no_checkpointer_isolation
def test_unsupported_database_scheme_raises_value_error(monkeypatch):
    """Verify that unsupported database schemes raise an explicit configuration error."""
    test_settings = Settings(
        _env_file=None,
        app_env="development",
        database_url="mysql://user:pass@localhost:3306/appraisal",
        jwt_secret=SAFE_PROD_SECRET,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)

    with pytest.raises(
        ValueError,
        match="Unsupported database scheme for LangGraph checkpointer: 'mysql://user:pass@localhost:3306/appraisal'",
    ):
        build_checkpointed_graph()


@pytest.mark.no_checkpointer_isolation
@pytest.mark.parametrize("env_name", ["test", "development", "staging", "production", "custom_env"])
def test_init_checkpointer_cleans_up_and_fails_closed_across_all_environments(env_name, monkeypatch):
    """Verify that when pool.open() succeeds but setup() fails:
    - pool.close() is called
    - global state is reset
    - RuntimeError is raised unconditionally regardless of APP_ENV
    """
    test_settings = Settings(
        _env_file=None,
        app_env=env_name,
        database_url="postgresql+psycopg://appraisal:appraisal@localhost:5432/appraisal",
        jwt_secret=SAFE_PROD_SECRET,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)

    mock_pool = MagicMock()
    mock_pool.open = MagicMock()
    mock_pool.close = MagicMock()

    mock_saver = MagicMock()
    mock_saver.setup.side_effect = ConnectionResetError("Simulated DB setup failure after open")

    monkeypatch.setattr(cp_module, "get_checkpointer_pool", lambda: mock_pool)
    monkeypatch.setattr(cp_module, "get_postgres_saver", lambda: mock_saver)

    try:
        with pytest.raises(
            RuntimeError,
            match="Fail-closed: Unable to initialize durable PostgreSQL checkpointer",
        ):
            cp_module.init_checkpointer()

        mock_pool.open.assert_called_once()
        mock_pool.close.assert_called_once()
        assert cp_module._pool is None
        assert cp_module._saver is None
    finally:
        cp_module.close_checkpointer()


@pytest.mark.no_checkpointer_isolation
def test_close_checkpointer_safely_terminates_pool():
    """Verify close_checkpointer gracefully handles active and None pools."""
    mock_pool = MagicMock()
    cp_module._pool = mock_pool
    cp_module._saver = MagicMock()

    cp_module.close_checkpointer()

    mock_pool.close.assert_called_once()
    assert cp_module._pool is None
    assert cp_module._saver is None

    # Idempotent second call
    cp_module.close_checkpointer()
    assert cp_module._pool is None


@pytest.mark.no_checkpointer_isolation
def test_checkpointer_pool_created_with_open_false(monkeypatch):
    """Verify the PostgreSQL pool is created with open=False and executes no network I/O on creation."""
    test_settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+psycopg://appraisal:appraisal@localhost:5432/appraisal",
        jwt_secret=SAFE_PROD_SECRET,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)

    cp_module.close_checkpointer()
    try:
        pool = cp_module.get_checkpointer_pool()
        # In psycopg_pool, open=False means the pool's closed status is True until open() is called
        assert pool.closed is True
    finally:
        cp_module.close_checkpointer()


@pytest.mark.no_checkpointer_isolation
def test_human_gate_propagates_reviewer_identity_when_decision_is_dict():
    """SEC-02 Stage 2: Verify human_gate preserves decision['reviewer'] when decision is a dict."""
    import uuid
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command
    from app.agents.graph import build_checkpointed_graph

    graph = build_checkpointed_graph(checkpointer=MemorySaver())
    thread_id = f"test-reviewer-dict-{uuid.uuid4().hex[:8]}"

    # Run until interrupted at human_gate
    initial = graph.invoke(
        {
            "run_id": "r1",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "all_activities": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    assert initial.get("next_action") == "await_human"
    assert initial.get("approval") is None

    # Resume with a dict containing reviewer
    reviewer_email = "hod-physics@demo.local"
    resumed = graph.invoke(
        Command(
            resume={
                "action": "approve",
                "reviewer": reviewer_email,
                "reason": "Excellent performance",
            }
        ),
        config={"configurable": {"thread_id": thread_id}},
    )

    approval = resumed.get("approval") or {}
    assert approval.get("action") == "approve"
    assert approval.get("status") == "approved"
    assert approval.get("reviewer") == reviewer_email
    assert approval.get("reason") == "Excellent performance"
    assert resumed.get("next_action") == "approved"


@pytest.mark.no_checkpointer_isolation
def test_human_gate_preserves_none_reviewer_for_string_decision():
    """SEC-02 Stage 2: Verify human_gate sets reviewer to None when decision is a plain string."""
    import uuid
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command
    from app.agents.graph import build_checkpointed_graph

    graph = build_checkpointed_graph(checkpointer=MemorySaver())
    thread_id = f"test-reviewer-str-{uuid.uuid4().hex[:8]}"

    # Run until interrupted at human_gate
    initial = graph.invoke(
        {
            "run_id": "r2",
            "faculty_id": "f2",
            "cycle_id": "c2",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "all_activities": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    assert initial.get("next_action") == "await_human"

    # Resume with string decision
    resumed = graph.invoke(
        Command(resume="approve"),
        config={"configurable": {"thread_id": thread_id}},
    )

    approval = resumed.get("approval") or {}
    assert approval.get("action") == "approve"
    assert approval.get("status") == "approved"
    assert approval.get("reviewer") is None
    assert approval.get("reason") is None
    assert resumed.get("next_action") == "approved"
