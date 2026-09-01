"""Phase 2 LangGraph workflow: collectors, evidence gate, DEMO scoring. No LLM.

State field names stay compatible with Phase 1 tests.
The human_gate node remains a compile-safe placeholder. Later phases must replace
it with a persisted LangGraph interrupt + checkpointer.
"""

from langgraph.graph import END, START, StateGraph

from app.agents.state import AppraisalGraphState, PlannerGraphState
from app.scoring.engine import calculate_score, load_demo_rubric
from app.services.reports import DEMO_DISCLAIMER, build_report
from app.services.scoring_map import to_score_inputs
from app.agents.skills import PlanningSkillInput, planning_skill


def planner_identify_ambiguity(state: PlannerGraphState) -> dict:
    result = planning_skill(PlanningSkillInput(request=state.get("request", ""), **(state.get("inputs") or {})))
    return {"clarification_questions": result.clarification_questions, "status": result.status}


def planner_create_plan(state: PlannerGraphState) -> dict:
    result = planning_skill(PlanningSkillInput(request=state.get("request", ""), **(state.get("inputs") or {})))
    return {"plan": result.model_dump(), "status": result.status}


def build_planner_graph():
    builder = StateGraph(PlannerGraphState)
    builder.add_node("planner_identify_ambiguity", planner_identify_ambiguity)
    builder.add_node("planner_create_plan", planner_create_plan)
    builder.add_edge(START, "planner_identify_ambiguity")
    builder.add_edge("planner_identify_ambiguity", "planner_create_plan")
    builder.add_edge("planner_create_plan", END)
    return builder.compile()


planner_graph = build_planner_graph()


def _all_activities(state: AppraisalGraphState) -> list[dict]:
    return list(state.get("all_activities") or [])


def aura_prepare(state: AppraisalGraphState) -> dict:
    return {
        "attempt": state.get("attempt") or 0,
        "max_attempts": state.get("max_attempts") or 3,
        "next_action": "continue",
        "errors": list(state.get("errors") or []),
        "audit_events": [{"event": "aura_prepare", "phase": 2, "stub": False}],
    }


def collect_research(state: AppraisalGraphState) -> dict:
    return {"raw_research": [a for a in _all_activities(state) if a.get("category") == "research"]}


def collect_teaching(state: AppraisalGraphState) -> dict:
    return {"raw_teaching": [a for a in _all_activities(state) if a.get("category") == "teaching"]}


def collect_admin(state: AppraisalGraphState) -> dict:
    return {"raw_admin": [a for a in _all_activities(state) if a.get("category") == "administrative"]}


def evidence_validation(state: AppraisalGraphState) -> dict:
    merged = list(state.get("raw_research") or []) + list(state.get("raw_teaching") or []) + list(
        state.get("raw_admin") or []
    )
    accepted: list[dict] = []
    rejected: list[dict] = []
    warnings: list[str] = []
    for item in merged:
        statuses = item.get("evidence_statuses") or []
        evidence_ids = item.get("evidence_ids") or []
        if evidence_ids and all(status in {"valid", "extracted"} for status in statuses):
            accepted.append(item)
        else:
            rejected.append({**item, "reason": "missing_or_invalid_evidence"})
            warnings.append(f"activity_{item.get('id')}_not_scored")
    return {"validated_set": {"accepted": accepted, "rejected": rejected, "warnings": warnings}}


def api_calculation(state: AppraisalGraphState) -> dict:
    accepted = (state.get("validated_set") or {}).get("accepted") or []
    inputs = to_score_inputs(accepted)
    result = calculate_score(inputs, load_demo_rubric())
    return {"score_result": result.to_dict()}


def report_generation(state: AppraisalGraphState) -> dict:
    score = state.get("score_result") or {}
    activities = _all_activities(state)
    built = build_report(
        profile={"id": state.get("faculty_id")},
        cycle={"id": state.get("cycle_id")},
        activities=activities,
        evidence=[],
        score=score,
    )
    return {
        "report_draft": {
            "summary_md": built["markdown"],
            "html": built["html"],
            "rating_recommendation": score.get("rating_recommendation"),
            "disclaimer": DEMO_DISCLAIMER,
        }
    }


def validation_gate(state: AppraisalGraphState) -> dict:
    score = state.get("score_result")
    ok = score is not None and "total" in score
    return {
        "validation_result": {
            "ok": ok,
            "errors": [],
            "warnings": (state.get("validated_set") or {}).get("warnings") or [],
        },
        "next_action": "await_human" if ok else "heal",
    }


def human_gate_placeholder(state: AppraisalGraphState) -> dict:
    """Compile-safe stand-in for a persisted interrupt/checkpoint human gate."""
    return {"approval": None, "next_action": "await_human"}


def build_graph():
    builder = StateGraph(AppraisalGraphState)
    builder.add_node("aura_prepare", aura_prepare)
    builder.add_node("collect_research", collect_research)
    builder.add_node("collect_teaching", collect_teaching)
    builder.add_node("collect_admin", collect_admin)
    builder.add_node("evidence_validation", evidence_validation)
    builder.add_node("api_calculation", api_calculation)
    builder.add_node("report_generation", report_generation)
    builder.add_node("validation_gate", validation_gate)
    builder.add_node("human_gate_placeholder", human_gate_placeholder)

    builder.add_edge(START, "aura_prepare")
    builder.add_edge("aura_prepare", "collect_research")
    builder.add_edge("aura_prepare", "collect_teaching")
    builder.add_edge("aura_prepare", "collect_admin")
    builder.add_edge("collect_research", "evidence_validation")
    builder.add_edge("collect_teaching", "evidence_validation")
    builder.add_edge("collect_admin", "evidence_validation")
    builder.add_edge("evidence_validation", "api_calculation")
    builder.add_edge("api_calculation", "report_generation")
    builder.add_edge("report_generation", "validation_gate")
    builder.add_edge("validation_gate", "human_gate_placeholder")
    builder.add_edge("human_gate_placeholder", END)
    return builder.compile()


compiled_graph = build_graph()
GRAPH_NODE_NAMES = [
    "aura_prepare",
    "collect_research",
    "collect_teaching",
    "collect_admin",
    "evidence_validation",
    "api_calculation",
    "report_generation",
    "validation_gate",
    "human_gate_placeholder",
]
