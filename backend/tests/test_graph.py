from app.agents.graph import (
    GRAPH_NODE_NAMES,
    LAB7_NODE_ROLES,
    LAB7_NODE_SEQUENCE,
    build_graph,
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
