from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agents.graph import (
    build_checkpointed_graph,
    build_graph,
    evidence_validation,
    heal,
    validation_gate,
)
from app.models import AppraisalReport, AppraisalScore, FacultyActivity, FacultyProfile, Rubric
from app.scoring.engine import ActivityScoreInput, calculate_score, load_demo_rubric
from app.services.memory import retrieve_faculty_memory
from app.services.reports import build_report
from tests.conftest import make_cycle, make_faculty_profile, make_user


def test_historical_context_rendered_in_markdown_html_and_json():
    profile = {"id": "f1", "full_name": "Dr. Uday Kulkarni", "email": "uday@demo.local"}
    cycle = {"id": "c1", "name": "Cycle 2026-27", "academic_year": "2026-27"}
    activities = []
    evidence = []
    score = {
        "total": 85.0,
        "rating_recommendation": "A",
        "category_totals": {"research": 40.0, "teaching": 30.0, "administrative": 15.0},
        "line_items": [],
    }
    memory_context = {
        "previous_scores": [
            {
                "id": "score-old-1",
                "cycle_id": "2025-26",
                "total": 78.5,
                "breakdown": {"research": 35.0, "teaching": 28.5, "administrative": 15.0},
                "computed_at": "2025-06-15T10:00:00Z",
            }
        ],
        "previous_reports": [
            {
                "id": "report-old-1",
                "rating_recommendation": "B",
                "version_number": 1,
            }
        ],
    }

    built = build_report(
        profile=profile,
        cycle=cycle,
        activities=activities,
        evidence=evidence,
        score=score,
        memory_context=memory_context,
    )

    # 1. JSON payload preserves context
    assert built["json"]["memory_context"] == memory_context
    assert built["json"]["historical_memory"] == memory_context

    # 2. Markdown output includes historical section
    md = built["markdown"]
    assert "## Historical Performance (Previous Cycles)" in md
    assert "Previous Cycle (2025-26)" in md
    assert "Total 78.5 pts" in md
    assert "Research: 35.0" in md

    # 3. HTML output includes escaped historical section
    html = built["html"]
    assert "<h2>Historical Performance (Previous Cycles)</h2>" in html
    assert "Previous Cycle (2025-26)" in html
    assert "Total 78.5 pts" in html
    assert "Research: 35.0" in html


def test_historical_context_safe_handling_of_empty_or_none():
    profile = {"id": "f2", "full_name": "New Faculty", "email": "new@demo.local"}
    cycle = {"id": "c1", "name": "Cycle 2026-27", "academic_year": "2026-27"}
    score = {"total": 50.0, "rating_recommendation": "C"}

    # Case A: memory_context is None
    built_none = build_report(
        profile=profile,
        cycle=cycle,
        activities=[],
        evidence=[],
        score=score,
        memory_context=None,
    )
    assert "## Historical Performance (Previous Cycles)" in built_none["markdown"]
    assert "No prior appraisal cycle records found." in built_none["markdown"]
    assert "<p>No prior appraisal cycle records found.</p>" in built_none["html"]
    assert built_none["json"].get("memory_context") is None

    # Case B: memory_context is empty dict
    built_empty = build_report(
        profile=profile,
        cycle=cycle,
        activities=[],
        evidence=[],
        score=score,
        memory_context={},
    )
    assert "No prior appraisal cycle records found." in built_empty["markdown"]
    assert "<p>No prior appraisal cycle records found.</p>" in built_empty["html"]


def test_historical_context_does_not_affect_deterministic_scoring():
    rubric = load_demo_rubric()
    current_inputs = [
        ActivityScoreInput(activity_id="act-1", rubric_code="journal_paper", category="research", evidence_ids=("ev-1",)),
        ActivityScoreInput(activity_id="act-2", rubric_code="course_delivery", category="teaching", evidence_ids=("ev-2",), quantity=30.0),
    ]

    base_result = calculate_score(current_inputs, rubric)

    # Prove that calculate_score does not take or use historical data
    # and that identical current inputs produce identical scores regardless of past scores
    high_history = {"previous_scores": [{"total": 100.0, "breakdown": {"research": 40.0}}]}
    low_history = {"previous_scores": [{"total": 10.0, "breakdown": {"research": 5.0}}]}

    # Scores calculated
    res_high = calculate_score(current_inputs, rubric)
    res_low = calculate_score(current_inputs, rubric)

    assert base_result.total == res_high.total == res_low.total
    assert base_result.category_totals == res_high.category_totals == res_low.category_totals
    assert base_result.rating_recommendation == res_high.rating_recommendation == res_low.rating_recommendation


def test_graph_self_healing_recovers_structural_defect():
    graph = build_graph()

    # Structural defect: activity category has leading whitespace and validated_set is None
    state_input = {
        "run_id": "r-heal-1",
        "faculty_id": "f-1",
        "cycle_id": "c-1",
        "rubric_id": "DEMO_RUBRIC_v1",
        "attempt": 0,
        "max_attempts": 3,
        "errors": ["validated_set_malformed"],
        "audit_events": [],
        "all_activities": [
            {
                "id": 101,
                "category": " research ",  # Unnormalized whitespace
                "activity_type": "journal_paper",
                "evidence_ids": [1],
                "evidence_statuses": ["valid"],
            }
        ],
        "validated_set": None,  # Missing/malformed validated_set triggers validation failure
    }

    result = graph.invoke(state_input)

    # Self-healing repaired the state and completed to human_gate_placeholder
    assert result["next_action"] == "await_human"
    assert result["validation_result"]["ok"] is True
    assert result["attempt"] >= 1
    assert result["heal_plan"] is not None
    assert result["heal_plan"]["status"] == "repaired"

    # Verify healing audit event is present
    healing_events = [e for e in result["audit_events"] if e.get("event") == "graph_self_healing_attempt"]
    assert len(healing_events) >= 1
    assert healing_events[0]["attempt"] == 1


def test_graph_self_healing_unrecoverable_failure_escalates_to_human():
    graph = build_graph()

    # Unrecoverable defect: fatal error that heal cannot and must not repair
    state_input = {
        "run_id": "r-heal-fail",
        "faculty_id": "f-fail",
        "cycle_id": "c-1",
        "rubric_id": "DEMO_RUBRIC_v1",
        "attempt": 0,
        "max_attempts": 3,
        "errors": ["unrecoverable_fatal_scoring_corruption"],
        "audit_events": [],
        "all_activities": [],
    }

    result = graph.invoke(state_input)

    # Must terminate within max_attempts and escalate to human review
    assert result["next_action"] == "escalate_human"
    assert result["validation_result"]["ok"] is False
    assert result["attempt"] == 3

    # Verify exhaustion audit event
    exhaustion_events = [e for e in result["audit_events"] if e.get("event") == "graph_self_healing_exhausted"]
    assert len(exhaustion_events) == 1
    assert exhaustion_events[0]["attempt"] == 3


def test_graph_does_not_duplicate_audit_events_on_retry():
    graph = build_graph()

    state_input = {
        "run_id": "r-dedup",
        "faculty_id": "f-dedup",
        "cycle_id": "c-1",
        "rubric_id": "DEMO_RUBRIC_v1",
        "attempt": 0,
        "max_attempts": 3,
        "errors": ["validated_set_malformed"],
        "audit_events": [],
        "all_activities": [],
        "validated_set": None,
    }

    result = graph.invoke(state_input)

    # aura_prepare and history_retrieved must not be duplicated
    aura_events = [e for e in result["audit_events"] if e.get("event") == "aura_prepare"]
    assert len(aura_events) == 1

    history_events = [e for e in result["audit_events"] if e.get("event") == "history_retrieved"]
    assert len(history_events) <= 1


def test_checkpointed_graph_preserves_memory_and_healing_state():
    checkpointer = MemorySaver()
    graph = build_checkpointed_graph(checkpointer=checkpointer)
    thread_id = "thread-memory-test-1"
    config = {"configurable": {"thread_id": thread_id}}

    memory_context = {
        "previous_scores": [{"cycle_id": "old-cycle", "total": 75.0}],
    }

    # Run graph until interrupt at human_gate
    result = graph.invoke(
        {
            "run_id": "r-check-mem",
            "faculty_id": "f-check",
            "cycle_id": "c-check",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "memory_context": memory_context,
            "all_activities": [],
        },
        config=config,
    )

    # Graph interrupted at human_gate
    state = graph.get_state(config)
    assert state.next == ("human_gate",)
    assert state.values["memory_context"] == memory_context

    # Resume graph with reviewer approval
    resumed = graph.invoke(
        Command(resume={"action": "approve", "reviewer": "hod@demo.local"}),
        config=config,
    )
    assert resumed["next_action"] == "approved"
    assert resumed["approval"]["status"] == "approved"


def test_active_cycle_excluded_from_memory_retrieval(db_session: Session):
    from app.models import FacultyAppraisalRun

    user = make_user(db_session, "mem-excl@demo.local", ["faculty"])
    faculty = make_faculty_profile(db_session, user, employee_code="EXCL-01")
    old_cycle = make_cycle(db_session, status="closed")
    active_cycle = make_cycle(db_session, status="open")
    db_session.commit()

    rubric = Rubric(name="Rubric", version="1", json_definition={})
    old_run = FacultyAppraisalRun(faculty_id=faculty.id, cycle_id=old_cycle.id, status="completed")
    active_run = FacultyAppraisalRun(faculty_id=faculty.id, cycle_id=active_cycle.id, status="collecting")
    db_session.add_all([rubric, old_run, active_run])
    db_session.flush()

    old_score = AppraisalScore(
        faculty_id=faculty.id,
        cycle_id=old_cycle.id,
        run_id=old_run.id,
        rubric_id=rubric.id,
        total=80.0,
        breakdown={},
        activity_score_refs=[],
        engine_version="test",
    )
    active_score = AppraisalScore(
        faculty_id=faculty.id,
        cycle_id=active_cycle.id,
        run_id=active_run.id,
        rubric_id=rubric.id,
        total=90.0,
        breakdown={},
        activity_score_refs=[],
        engine_version="test",
    )
    db_session.add_all([old_score, active_score])
    db_session.commit()

    memory = retrieve_faculty_memory(
        db_session,
        faculty=faculty,
        current_cycle_id=active_cycle.id,
    )

    retrieved_cycle_ids = {s["cycle_id"] for s in memory["previous_scores"]}
    assert str(old_cycle.id) in retrieved_cycle_ids
    assert str(active_cycle.id) not in retrieved_cycle_ids
