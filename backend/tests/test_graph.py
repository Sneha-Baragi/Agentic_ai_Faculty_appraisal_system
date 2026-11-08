from app.agents.graph import (
    GRAPH_NODE_NAMES,
    LAB7_NODE_ROLES,
    LAB7_NODE_SEQUENCE,
    PARALLEL_COLLECTION_NODES,
    build_graph,
    parallel_collection_router,
)
from app.scoring.engine import ENGINE_VERSION


def test_graph_compiles_and_reaches_human_gate_placeholder() -> None:
    graph = build_graph()
    result = graph.invoke(
        {
            "run_id": "r1",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
        }
    )
    assert result["next_action"] == "await_human"
    assert result["approval"] is None
    assert result["score_result"]["engine_version"] == ENGINE_VERSION
    assert result["score_result"]["total"] == 0.0
    for name in GRAPH_NODE_NAMES:
        assert name in (
            "aura_prepare",
            "retrieve_memory",
            "collect_research",
            "collect_teaching",
            "collect_admin",
            "evidence_validation",
            "api_calculation",
            "report_generation",
            "validation_gate",
            "human_gate",
        )


def test_graph_has_parallel_collector_nodes() -> None:
    assert "collect_research" in GRAPH_NODE_NAMES
    assert "collect_teaching" in GRAPH_NODE_NAMES
    assert "collect_admin" in GRAPH_NODE_NAMES


def test_graph_uses_native_langgraph_fan_out_for_parallel_collection() -> None:
    assert parallel_collection_router({}) == PARALLEL_COLLECTION_NODES
    assert PARALLEL_COLLECTION_NODES == [
        "collect_research",
        "collect_teaching",
        "collect_admin",
    ]


def test_graph_exposes_lab7_roles_and_serial_sequence() -> None:
    expected_roles = {
        "aura_prepare": "coordinator/setup",
        "retrieve_memory": "memory_retrieval",
        "collect_research": "research_agent",
        "collect_teaching": "teaching_agent",
        "collect_admin": "administrative_agent",
        "evidence_validation": "evidence_validation",
        "api_calculation": "appraisal_calculation",
        "report_generation": "report_generation",
        "validation_gate": "validation_gate",
        "human_gate": "human_review",
    }

    assert LAB7_NODE_ROLES == expected_roles
    assert LAB7_NODE_SEQUENCE == [
        "aura_prepare",
        "retrieve_memory",
        "collect_research",
        "collect_teaching",
        "collect_admin",
        "evidence_validation",
        "api_calculation",
        "report_generation",
        "validation_gate",
        "human_gate",
    ]
    assert GRAPH_NODE_NAMES == LAB7_NODE_SEQUENCE


def test_graph_sequence_keeps_memory_before_collection_and_human_gate_last() -> None:
    memory_index = LAB7_NODE_SEQUENCE.index("retrieve_memory")
    research_index = LAB7_NODE_SEQUENCE.index("collect_research")
    teaching_index = LAB7_NODE_SEQUENCE.index("collect_teaching")
    admin_index = LAB7_NODE_SEQUENCE.index("collect_admin")
    evidence_index = LAB7_NODE_SEQUENCE.index("evidence_validation")
    api_index = LAB7_NODE_SEQUENCE.index("api_calculation")
    report_index = LAB7_NODE_SEQUENCE.index("report_generation")
    human_index = LAB7_NODE_SEQUENCE.index("human_gate")

    assert memory_index < research_index < evidence_index
    assert memory_index < teaching_index < evidence_index
    assert memory_index < admin_index < evidence_index
    assert evidence_index < api_index < report_index < human_index
    assert LAB7_NODE_SEQUENCE[-1] == "human_gate"


def test_graph_parallel_collection_converges_before_evidence_validation() -> None:
    graph = build_graph()
    result = graph.invoke(
        {
            "run_id": "r1",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "all_activities": [
                {"id": 1, "category": "research", "evidence_ids": [11], "evidence_statuses": ["valid"]},
                {"id": 2, "category": "teaching", "evidence_ids": [22], "evidence_statuses": ["valid"]},
                {"id": 3, "category": "administrative", "evidence_ids": [33], "evidence_statuses": ["valid"]},
            ],
        }
    )

    assert result["raw_research"][0]["id"] == 1
    assert result["raw_teaching"][0]["id"] == 2
    assert result["raw_admin"][0]["id"] == 3
    accepted_ids = {item["id"] for item in result["validated_set"]["accepted"]}
    assert accepted_ids == {1, 2, 3}
    assert result["validation_result"]["ok"] is True


def test_graph_includes_history_retrieval_and_keeps_memory_context() -> None:
    graph = build_graph()
    memory_context = {
        "previous_scores": [{"cycle_id": "old-cycle", "total": 80.0}],
        "previous_reports": [{"cycle_id": "old-cycle", "version_number": 1}],
    }

    result = graph.invoke(
        {
            "run_id": "r1",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "memory_context": memory_context,
        }
    )

    assert result["next_action"] == "await_human"
    assert result["approval"] is None
    assert result["score_result"]["engine_version"] == ENGINE_VERSION
    assert result["score_result"]["total"] == 0.0
    assert result["memory_context"] == memory_context
    assert any(event.get("event") == "history_retrieved" for event in result["audit_events"])
    for name in GRAPH_NODE_NAMES:
        assert name in (
            "aura_prepare",
            "retrieve_memory",
            "collect_research",
            "collect_teaching",
            "collect_admin",
            "evidence_validation",
            "api_calculation",
            "report_generation",
            "validation_gate",
            "human_gate",
        )

def test_graph_parallel_identical_duplicate_activities_deduplicated_safely() -> None:
    graph = build_graph()
    activities = [
        {
            "id": 101,
            "category": "research",
            "activity_type": "journal_paper",
            "quantity": 1,
            "evidence_ids": [11],
            "evidence_statuses": ["valid"],
        },
        {
            "id": 101,
            "category": "research",
            "activity_type": "journal_paper",
            "quantity": 1,
            "evidence_ids": [11],
            "evidence_statuses": ["valid"],
        },
        {
            "id": 202,
            "category": "teaching",
            "activity_type": "course_delivery",
            "quantity": 1,
            "evidence_ids": [22],
            "evidence_statuses": ["valid"],
        },
    ]

    result = graph.invoke(
        {
            "run_id": "r-dedup",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "all_activities": activities,
        }
    )

    accepted = result["validated_set"]["accepted"]
    accepted_ids = [item["id"] for item in accepted]
    assert accepted_ids.count(101) == 1
    assert accepted_ids.count(202) == 1
    assert len(accepted) == 2
    assert result["validation_result"]["ok"] is True
    assert result["next_action"] == "await_human"

    dedup_events = [e for e in result["audit_events"] if e.get("event") == "parallel_duplicate_deduplicated"]
    assert len(dedup_events) == 1
    assert dedup_events[0]["activity_id"] == "101"
    assert dedup_events[0]["duplicate_count"] == 2


def test_graph_parallel_conflicting_duplicate_activities_rejected_with_warning() -> None:
    graph = build_graph()
    activities = [
        {
            "id": 501,
            "category": "research",
            "activity_type": "journal_paper",
            "evidence_ids": [51],
            "evidence_statuses": ["valid"],
        },
        {
            "id": 501,
            "category": "teaching",
            "activity_type": "course_delivery",
            "evidence_ids": [51],
            "evidence_statuses": ["valid"],
        },
        {
            "id": 601,
            "category": "administrative",
            "activity_type": "committee",
            "evidence_ids": [61],
            "evidence_statuses": ["valid"],
        },
    ]

    result = graph.invoke(
        {
            "run_id": "r-conflict",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "all_activities": activities,
        }
    )

    accepted = result["validated_set"]["accepted"]
    rejected = result["validated_set"]["rejected"]
    warnings = result["validated_set"]["warnings"]

    # Activity 501 must be completely rejected due to parallel conflict
    accepted_ids = [item["id"] for item in accepted]
    assert 501 not in accepted_ids
    assert 601 in accepted_ids

    # Conflicting instances are recorded with reason parallel_agent_conflict
    conflict_rejections = [r for r in rejected if r.get("reason") == "parallel_agent_conflict"]
    assert len(conflict_rejections) == 2
    assert all(r["id"] == 501 for r in conflict_rejections)

    # Actionable human-review warning is present
    conflict_warnings = [w for w in warnings if "activity_501_conflict_unresolved" in w]
    assert len(conflict_warnings) == 1
    assert "human review required" in conflict_warnings[0]

    # Audit event is emitted
    conflict_events = [e for e in result["audit_events"] if e.get("event") == "parallel_conflict_detected"]
    assert len(conflict_events) == 1
    assert conflict_events[0]["activity_id"] == "501"
    assert conflict_events[0]["conflict_count"] == 2


def test_graph_parallel_concurrent_audit_events_and_errors_merge() -> None:
    from app.agents.state import AppraisalGraphState, ReplaceList, merge_audit_events, merge_errors
    from langgraph.graph import StateGraph, START, END

    # 1. Direct unit verification of reducers
    base_errors = ["err_initial", "err_shared"]
    new_errors_1 = ["err_shared", "err_unique_1"]
    new_errors_2 = ["err_unique_2"]
    merged_err = merge_errors(merge_errors(base_errors, new_errors_1), new_errors_2)
    assert merged_err == ["err_initial", "err_shared", "err_unique_1", "err_unique_2"]

    # ReplaceList clears/replaces
    cleared = merge_errors(merged_err, ReplaceList(["repaired_only"]))
    assert cleared == ["repaired_only"]

    ev1 = [{"event": "start"}, {"event": "collector_a"}]
    ev2 = [{"event": "collector_a"}, {"event": "collector_b"}]
    merged_ev = merge_audit_events(ev1, ev2)
    assert len(merged_ev) == 3
    assert merged_ev == [{"event": "start"}, {"event": "collector_a"}, {"event": "collector_b"}]

    # 2. Graph invocation with parallel branches writing errors and audit_events concurrently
    builder = StateGraph(AppraisalGraphState)
    builder.add_node("branch_a", lambda s: {"errors": ["err_branch_a"], "audit_events": [{"event": "ev_a"}]})
    builder.add_node("branch_b", lambda s: {"errors": ["err_branch_b"], "audit_events": [{"event": "ev_b"}]})
    builder.add_node("join", lambda s: {})
    builder.add_conditional_edges(START, lambda s: ["branch_a", "branch_b"])
    builder.add_edge("branch_a", "join")
    builder.add_edge("branch_b", "join")
    builder.add_edge("join", END)

    compiled = builder.compile()
    res = compiled.invoke({"run_id": "r_parallel", "errors": ["err_root"], "audit_events": [{"event": "ev_root"}]})

    assert res["errors"] == ["err_root", "err_branch_a", "err_branch_b"]
    assert res["audit_events"] == [{"event": "ev_root"}, {"event": "ev_a"}, {"event": "ev_b"}]


def test_graph_collector_malformed_output_fails_safely_without_silent_success(monkeypatch) -> None:
    from app.agents.graph import collect_research, evidence_validation

    # 1. Direct test of collector exception isolation
    state_mock = {"all_activities": 12345}
    fail_res = collect_research(state_mock)  # type: ignore[arg-type]
    assert fail_res["raw_research"] == []
    assert any("collector_research_failed" in err for err in fail_res["errors"])
    assert any(ev.get("event") == "collector_failed" for ev in fail_res["audit_events"])

    # 2. Evidence validation handling of malformed records from collectors: non-dict and missing id
    val_res = evidence_validation({
        "raw_research": [
            "not_a_valid_dict_activity",
            {"activity_type": "journal_paper", "category": "research"},  # missing id
            {
                "id": 888,
                "category": "research",
                "activity_type": "journal_paper",
                "evidence_ids": [88],
                "evidence_statuses": ["valid"],
            },
        ],
        "raw_teaching": [],
        "raw_admin": [],
    })

    accepted = val_res["validated_set"]["accepted"]
    rejected = val_res["validated_set"]["rejected"]
    warnings = val_res["validated_set"]["warnings"]

    assert len(accepted) == 1
    assert accepted[0]["id"] == 888
    rejected_reasons = {r.get("reason") for r in rejected}
    assert "malformed_activity_record" in rejected_reasons
    assert "missing_activity_id" in rejected_reasons
    assert any("malformed_activity_skipped" in w for w in warnings)
    assert any("activity_missing_id_skipped" in w for w in warnings)

    # 3. Collector failure during graph invocation prevents silent success
    def faulty_collect_research(s):
        return {
            "raw_research": [],
            "errors": ["collector_research_failed: Simulated connection failure"],
            "audit_events": [{"event": "collector_failed", "collector": "collect_research", "error": "Simulated"}],
        }

    monkeypatch.setattr("app.agents.graph.collect_research", faulty_collect_research)
    faulty_graph = build_graph()
    faulty_res = faulty_graph.invoke(
        {
            "run_id": "r-faulty-collector",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 3,
            "max_attempts": 3,
            "errors": [],
            "audit_events": [],
            "all_activities": [],
        }
    )
    assert faulty_res["validation_result"]["ok"] is False
    assert any("collector_research_failed" in err for err in faulty_res["validation_result"]["errors"])
    assert faulty_res["next_action"] == "escalate_human"
    assert any(ev.get("event") == "graph_self_healing_exhausted" for ev in faulty_res["audit_events"])


def test_graph_self_healing_and_human_review_preserved() -> None:
    graph = build_graph()

    # Case 1: Repairable state where category needs normalization and transient error is cleared
    raw_activities = [
        {
            "id": 901,
            "category": "RESEARCH ",  # trailing space & uppercase -> needs normalization
            "activity_type": "journal_paper",
            "evidence_ids": [91],
            "evidence_statuses": ["valid"],
        }
    ]

    res_healed = graph.invoke(
        {
            "run_id": "r-heal",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 0,
            "max_attempts": 3,
            "errors": ["category_unnormalized"],
            "audit_events": [],
            "all_activities": raw_activities,
        }
    )

    assert res_healed["validation_result"]["ok"] is True
    assert res_healed["next_action"] == "await_human"
    assert res_healed["attempt"] >= 1
    assert any(e.get("event") == "graph_self_healing_attempt" for e in res_healed["audit_events"])
    assert res_healed["heal_plan"] is not None
    assert "normalized_activity_categories" in res_healed["heal_plan"]["repairs_applied"]

    # Case 2: Unrepairable error reaching max attempts escalates to human review
    res_escalated = graph.invoke(
        {
            "run_id": "r-escalate",
            "faculty_id": "f1",
            "cycle_id": "c1",
            "rubric_id": "DEMO_RUBRIC_v1",
            "attempt": 3,
            "max_attempts": 3,
            "errors": ["fatal_data_corruption_unrepairable"],
            "audit_events": [],
            "all_activities": [],
        }
    )

    assert res_escalated["validation_result"]["ok"] is False
    assert res_escalated["next_action"] == "escalate_human"
    assert any(e.get("event") == "graph_self_healing_exhausted" for e in res_escalated["audit_events"])
