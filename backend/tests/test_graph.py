from app.agents.graph import GRAPH_NODE_NAMES, build_graph
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
            "collect_research",
            "collect_teaching",
            "collect_admin",
            "evidence_validation",
            "api_calculation",
            "report_generation",
            "validation_gate",
            "human_gate_placeholder",
        )


def test_graph_has_parallel_collector_nodes() -> None:
    assert "collect_research" in GRAPH_NODE_NAMES
    assert "collect_teaching" in GRAPH_NODE_NAMES
    assert "collect_admin" in GRAPH_NODE_NAMES
