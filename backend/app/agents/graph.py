"""Phase 2 LangGraph workflow: collectors, evidence gate, DEMO scoring. No LLM.

Phase 5C / Lab 3: Adds checkpointed_graph with MemorySaver and a real
interrupt()-based human governance gate. The legacy compiled_graph (no
checkpointer) is retained for backward-compatible unit tests.
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


def retrieve_memory(state: AppraisalGraphState) -> dict:
    memory_context = state.get("memory_context") or {}
    existing_events = list(state.get("audit_events") or [])
    return {
        "audit_events": existing_events
        + [
            {
                "event": "history_retrieved",
                "phase": 2,
                "memory_context": memory_context,
            }
        ]
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
    """Compile-safe stand-in kept for the legacy compiled_graph and existing tests.

    Returns immediately without interrupting. The checkpointed_graph uses the
    real human_gate node below.
    """
    return {"approval": None, "next_action": "await_human"}


def human_gate(state: AppraisalGraphState) -> dict:
    """Phase 5C / Lab 3: Real LangGraph human-in-the-loop governance gate.

    Calls interrupt() to pause graph execution and persist state in the
    InMemorySaver checkpointer. Execution resumes when the reviewer supplies a
    decision via:
        checkpointed_graph.invoke(
            Command(resume={"action": "approve", "reviewer": email}),
            config={"configurable": {"thread_id": thread_id}},
        )

    LIMITATION: InMemorySaver is process-memory only. Interrupted threads do
    not survive server restarts. Use a database-backed checkpointer for
    production-grade durability.
    """
    from langgraph.types import interrupt

    decision = interrupt(
        {
            "type": "governance_review",
            "message": "Appraisal report ready. Awaiting HOD/reviewer governance decision.",
            "faculty_id": state.get("faculty_id"),
            "cycle_id": state.get("cycle_id"),
            "run_id": state.get("run_id"),
            "score_total": (state.get("score_result") or {}).get("total"),
            "rating_recommendation": (state.get("report_draft") or {}).get("rating_recommendation"),
        }
    )

    # decision is the value passed by the reviewer via Command(resume=...)
    # It should be a dict: {"action": "approve"|"reject"|"request_changes",
    #                        "reviewer": <email>, "reason": <str|None>}
    if isinstance(decision, dict):
       action = decision.get("action")
       reason = decision.get("reason")
    else:
      action = str(decision)
      reason = None

    reviewer = None 

    status_map = {
    "approve": "approved",
    "reject": "rejected",
    "request_changes": "changes_requested",
}

    if action not in status_map:
       raise ValueError(
        f"Invalid governance action: {action}"
    )

    approval_status = status_map[action]

    return {
        "approval": {
            "action": action,
            "status": approval_status,
            "reviewer": reviewer,
            "reason": reason,
        },
        "next_action": approval_status,
    }


def build_graph():
    """Build the legacy non-checkpointed graph (used by compiled_graph).

    Preserves backward compatibility with existing tests that invoke the graph
    without a thread_id and expect human_gate_placeholder semantics.
    """
    builder = StateGraph(AppraisalGraphState)
    builder.add_node("aura_prepare", aura_prepare)
    builder.add_node("retrieve_memory", retrieve_memory)
    builder.add_node("collect_research", collect_research)
    builder.add_node("collect_teaching", collect_teaching)
    builder.add_node("collect_admin", collect_admin)
    builder.add_node("evidence_validation", evidence_validation)
    builder.add_node("api_calculation", api_calculation)
    builder.add_node("report_generation", report_generation)
    builder.add_node("validation_gate", validation_gate)
    builder.add_node("human_gate_placeholder", human_gate_placeholder)

    builder.add_edge(START, "aura_prepare")
    builder.add_edge("aura_prepare", "retrieve_memory")
    builder.add_edge("retrieve_memory", "collect_research")
    builder.add_edge("retrieve_memory", "collect_teaching")
    builder.add_edge("retrieve_memory", "collect_admin")
    builder.add_edge("collect_research", "evidence_validation")
    builder.add_edge("collect_teaching", "evidence_validation")
    builder.add_edge("collect_admin", "evidence_validation")
    builder.add_edge("evidence_validation", "api_calculation")
    builder.add_edge("api_calculation", "report_generation")
    builder.add_edge("report_generation", "validation_gate")
    builder.add_edge("validation_gate", "human_gate_placeholder")
    builder.add_edge("human_gate_placeholder", END)
    return builder.compile()


def build_checkpointed_graph():
    """Phase 5C / Lab 3: Checkpointed graph with real interrupt-based human gate.

    Returns a compiled StateGraph backed by InMemorySaver. Use this for all
    real appraisal executions so the governance gate can pause and be resumed.
    """
    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()

    builder = StateGraph(AppraisalGraphState)
    builder.add_node("aura_prepare", aura_prepare)
    builder.add_node("retrieve_memory", retrieve_memory)
    builder.add_node("collect_research", collect_research)
    builder.add_node("collect_teaching", collect_teaching)
    builder.add_node("collect_admin", collect_admin)
    builder.add_node("evidence_validation", evidence_validation)
    builder.add_node("api_calculation", api_calculation)
    builder.add_node("report_generation", report_generation)
    builder.add_node("validation_gate", validation_gate)
    builder.add_node("human_gate", human_gate)

    builder.add_edge(START, "aura_prepare")
    builder.add_edge("aura_prepare", "retrieve_memory")
    builder.add_edge("retrieve_memory", "collect_research")
    builder.add_edge("retrieve_memory", "collect_teaching")
    builder.add_edge("retrieve_memory", "collect_admin")
    builder.add_edge("collect_research", "evidence_validation")
    builder.add_edge("collect_teaching", "evidence_validation")
    builder.add_edge("collect_admin", "evidence_validation")
    builder.add_edge("evidence_validation", "api_calculation")
    builder.add_edge("api_calculation", "report_generation")
    builder.add_edge("report_generation", "validation_gate")
    builder.add_edge("validation_gate", "human_gate")
    builder.add_edge("human_gate", END)
    return builder.compile(checkpointer=checkpointer)


compiled_graph = build_graph()

# Phase 5C / Lab 3: Checkpointed graph for real appraisal runs.
# NOTE: InMemorySaver is process-memory only; see human_gate docstring.
checkpointed_graph = build_checkpointed_graph()

GRAPH_NODE_NAMES = [
    "aura_prepare",
    "collect_research",
    "collect_teaching",
    "collect_admin",
    "evidence_validation",
    "api_calculation",
    "report_generation",
    "validation_gate",
    "human_gate",
]
