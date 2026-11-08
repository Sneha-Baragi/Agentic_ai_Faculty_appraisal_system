"""Phase 2 LangGraph workflow: collectors, evidence gate, DEMO scoring. No LLM.

Phase 5C / Lab 3: Adds checkpointed_graph with MemorySaver and a real
interrupt()-based human governance gate. The legacy compiled_graph (no
checkpointer) is retained for backward-compatible unit tests.
"""

from langgraph.graph import END, START, StateGraph

from app.agents.state import AppraisalGraphState, PlannerGraphState, ReplaceList
from app.scoring.engine import calculate_score, load_demo_rubric
from app.services.reports import DEMO_DISCLAIMER, build_report
from app.services.scoring_map import (
    appraisal_year_from_cycle,
    to_score_inputs,
    to_scholar_score_inputs,
    to_student_feedback_score_input,
)
from app.services.student_feedback import get_student_feedback_record
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

# Lab 7: explicit agent-role metadata for the serial appraisal graph.
# These are role labels only; the underlying functions and behavior remain
# unchanged so Lab 3/Lab 4/Lab 5/Lab 6 functionality stays intact.
LAB7_NODE_ROLES = {
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

# The collection stage is intentionally a fan-out group after memory retrieval.
# This uses the native LangGraph conditional edge mechanism for a graph-level
# fan-out and then converges at evidence_validation.
LAB7_NODE_SEQUENCE = [
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

PARALLEL_COLLECTION_NODES = ["collect_research", "collect_teaching", "collect_admin"]


def parallel_collection_router(state: AppraisalGraphState):
    return PARALLEL_COLLECTION_NODES


def _all_activities(state: AppraisalGraphState) -> list[dict]:
    raw = state.get("all_activities")
    if raw is None:
        return []
    return [a for a in raw if isinstance(a, dict)]


def aura_prepare(state: AppraisalGraphState) -> dict:
    existing_events = list(state.get("audit_events") or [])
    new_events = []
    if not any(e.get("event") == "aura_prepare" for e in existing_events):
        new_events.append({"event": "aura_prepare", "phase": 2, "stub": False})
    return {
        "attempt": state.get("attempt") or 0,
        "max_attempts": state.get("max_attempts") or 3,
        "next_action": "continue",
        "errors": list(state.get("errors") or []),
        "audit_events": existing_events + new_events,
    }


def retrieve_memory(state: AppraisalGraphState) -> dict:
    memory_context = state.get("memory_context") or {}
    existing_events = list(state.get("audit_events") or [])
    if any(e.get("event") == "history_retrieved" for e in existing_events):
        return {"audit_events": existing_events}
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


def _are_activities_identical(a1: dict, a2: dict) -> bool:
    if a1 == a2:
        return True
    significant_keys = ("id", "category", "activity_type", "quantity", "evidence_ids", "evidence_statuses")
    for k in significant_keys:
        v1 = a1.get(k)
        v2 = a2.get(k)
        if isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
            if list(v1) != list(v2):
                return False
        elif v1 != v2:
            return False
    return True


def collect_research(state: AppraisalGraphState) -> dict:
    try:
        acts = _all_activities(state)
        research_acts = [a for a in acts if isinstance(a, dict) and a.get("category") == "research"]
        return {"raw_research": research_acts}
    except Exception as exc:
        return {
            "raw_research": [],
            "errors": [f"collector_research_failed: {str(exc)}"],
            "audit_events": [{"event": "collector_failed", "collector": "collect_research", "error": str(exc)}],
        }


def collect_teaching(state: AppraisalGraphState) -> dict:
    try:
        acts = _all_activities(state)
        teaching_acts = [a for a in acts if isinstance(a, dict) and a.get("category") == "teaching"]
        return {"raw_teaching": teaching_acts}
    except Exception as exc:
        return {
            "raw_teaching": [],
            "errors": [f"collector_teaching_failed: {str(exc)}"],
            "audit_events": [{"event": "collector_failed", "collector": "collect_teaching", "error": str(exc)}],
        }


def collect_admin(state: AppraisalGraphState) -> dict:
    try:
        acts = _all_activities(state)
        admin_acts = [a for a in acts if isinstance(a, dict) and a.get("category") == "administrative"]
        return {"raw_admin": admin_acts}
    except Exception as exc:
        return {
            "raw_admin": [],
            "errors": [f"collector_admin_failed: {str(exc)}"],
            "audit_events": [{"event": "collector_failed", "collector": "collect_admin", "error": str(exc)}],
        }


def evidence_validation(state: AppraisalGraphState) -> dict:
    raw_res = state.get("raw_research")
    raw_teach = state.get("raw_teaching")
    raw_admin = state.get("raw_admin")

    research_items = list(raw_res) if isinstance(raw_res, list) else []
    teaching_items = list(raw_teach) if isinstance(raw_teach, list) else []
    admin_items = list(raw_admin) if isinstance(raw_admin, list) else []

    all_items = research_items + teaching_items + admin_items

    accepted: list[dict] = []
    rejected: list[dict] = []
    warnings: list[str] = []
    new_audit_events: list[dict] = []

    # 1. Group valid dictionary items by normalized activity ID
    grouped_by_id: dict[str, list[dict]] = {}
    for item in all_items:
        if not isinstance(item, dict):
            warnings.append(f"malformed_activity_skipped: expected dict, got {type(item).__name__}")
            rejected.append({"raw": repr(item), "reason": "malformed_activity_record"})
            continue

        act_id = item.get("id")
        if act_id is None:
            warnings.append("activity_missing_id_skipped")
            rejected.append({**item, "reason": "missing_activity_id"})
            continue

        str_id = str(act_id)
        grouped_by_id.setdefault(str_id, []).append(item)

    # 2. Process each activity ID group according to deterministic conflict policy
    for str_id, group in grouped_by_id.items():
        if len(group) == 1:
            item = group[0]
            statuses = item.get("evidence_statuses") or []
            evidence_ids = item.get("evidence_ids") or []
            if evidence_ids and all(status in {"valid", "extracted"} for status in statuses):
                accepted.append(item)
            else:
                rejected.append({**item, "reason": "missing_or_invalid_evidence"})
                warnings.append(f"activity_{item.get('id')}_not_scored")
        else:
            first = group[0]
            all_identical = all(_are_activities_identical(first, other) for other in group[1:])

            if all_identical:
                # Deterministic Policy 1: Identical duplicate records are safely deduplicated
                new_audit_events.append({
                    "event": "parallel_duplicate_deduplicated",
                    "activity_id": str_id,
                    "duplicate_count": len(group),
                })
                statuses = first.get("evidence_statuses") or []
                evidence_ids = first.get("evidence_ids") or []
                if evidence_ids and all(status in {"valid", "extracted"} for status in statuses):
                    accepted.append(first)
                else:
                    rejected.append({**first, "reason": "missing_or_invalid_evidence"})
                    warnings.append(f"activity_{first.get('id')}_not_scored")
            else:
                # Deterministic Policy 2: Conflicting records with same activity ID cannot be scored twice
                # Reject affected records and provide actionable warning for human review
                conflicting_categories = sorted(list({str(r.get("category")) for r in group if r.get("category")}))
                conflicting_types = sorted(list({str(r.get("activity_type")) for r in group if r.get("activity_type")}))

                conflict_msg = (
                    f"activity_{str_id}_conflict_unresolved: conflicting parallel findings across collector agents "
                    f"(categories: {conflicting_categories}, types: {conflicting_types}); human review required"
                )
                warnings.append(conflict_msg)

                new_audit_events.append({
                    "event": "parallel_conflict_detected",
                    "activity_id": str_id,
                    "conflict_count": len(group),
                    "categories": conflicting_categories,
                    "types": conflicting_types,
                })

                for item in group:
                    rejected.append({
                        **item,
                        "reason": "parallel_agent_conflict",
                        "conflict_details": {
                            "activity_id": str_id,
                            "categories": conflicting_categories,
                            "types": conflicting_types,
                        },
                    })

    result_updates: dict = {
        "validated_set": {
            "accepted": accepted,
            "rejected": rejected,
            "warnings": warnings,
        }
    }
    if new_audit_events:
        result_updates["audit_events"] = new_audit_events

    return result_updates


def api_calculation(state: AppraisalGraphState) -> dict:
    accepted = (state.get("validated_set") or {}).get("accepted") or []
    rubric = load_demo_rubric()
    inputs = to_score_inputs(accepted)
    scholar_inputs, publications = to_scholar_score_inputs(
        state.get("research_metrics"),
        appraisal_year=appraisal_year_from_cycle(state.get("cycle_academic_year")),
        expected_scholar_id=state.get("configured_scholar_id"),
        cycle_id=state.get("cycle_id"),
        manual_activities=state.get("all_activities") or [],
        rubric=rubric,
    )
    feedback_data = state.get("student_feedback")
    if feedback_data is None and state.get("faculty_name"):
        feedback_data = get_student_feedback_record(state.get("faculty_name"))
    feedback_input = to_student_feedback_score_input(feedback_data, rubric=rubric)
    feedback_inputs = [feedback_input] if feedback_input is not None else []

    result = calculate_score(inputs + scholar_inputs + feedback_inputs, rubric)
    research_metrics = state.get("research_metrics")
    if isinstance(research_metrics, dict):
        research_metrics = {**research_metrics, "publications": publications}
    return {
        "score_result": result.to_dict(),
        "research_metrics": research_metrics,
        "student_feedback": feedback_data,
    }


def report_generation(state: AppraisalGraphState) -> dict:
    score = state.get("score_result") or {}
    activities = _all_activities(state)
    built = build_report(
        profile={"id": state.get("faculty_id"), "full_name": state.get("faculty_name")},
        cycle={"id": state.get("cycle_id"), "academic_year": state.get("cycle_academic_year")},
        activities=activities,
        evidence=[],
        score=score,
        research_metrics=state.get("research_metrics"),
        student_feedback=state.get("student_feedback"),
        memory_context=state.get("memory_context"),
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
    val_set = state.get("validated_set")
    errors = list(state.get("errors") or [])
    attempt = state.get("attempt") or 0
    max_attempts = state.get("max_attempts") or 3

    has_score = score is not None and isinstance(score, dict) and "total" in score
    has_val = val_set is not None and isinstance(val_set, dict) and "accepted" in val_set
    no_fatal_errors = len(errors) == 0

    ok = has_score and has_val and no_fatal_errors

    if ok:
        action = "await_human"
    elif attempt < max_attempts:
        action = "heal"
    else:
        action = "escalate_human"

    existing_events = list(state.get("audit_events") or [])
    new_events = []
    if action == "escalate_human":
        if not any(e.get("event") == "graph_self_healing_exhausted" for e in existing_events):
            new_events.append({
                "event": "graph_self_healing_exhausted",
                "attempt": attempt,
                "max_attempts": max_attempts,
                "errors": errors,
            })

    return {
        "validation_result": {
            "ok": ok,
            "errors": list(errors),
            "warnings": (val_set or {}).get("warnings") or [],
            "attempt": attempt,
            "max_attempts": max_attempts,
        },
        "next_action": action,
        "audit_events": existing_events + new_events,
    }


def heal(state: AppraisalGraphState) -> dict:
    """Phase 2 / Lab 4: Bounded deterministic self-healing node.

    Repairs only documented structural issues in state without fabricating data.
    Increments attempt counter by exactly 1.
    """
    attempt = (state.get("attempt") or 0) + 1
    max_attempts = state.get("max_attempts") or 3
    existing_events = list(state.get("audit_events") or [])
    repairs_applied: list[str] = []

    updates: dict[str, Any] = {
        "attempt": attempt,
    }

    # 1. Structural repair of validated_set if missing or malformed keys
    validated_set = state.get("validated_set")
    if validated_set is None or not isinstance(validated_set, dict):
        updates["validated_set"] = {"accepted": [], "rejected": [], "warnings": []}
        repairs_applied.append("normalized_validated_set_structure")
    else:
        fixed_val_set = dict(validated_set)
        modified = False
        for key in ("accepted", "rejected", "warnings"):
            if key not in fixed_val_set or not isinstance(fixed_val_set[key], list):
                fixed_val_set[key] = []
                modified = True
        if modified:
            updates["validated_set"] = fixed_val_set
            repairs_applied.append("repaired_validated_set_keys")

    # 2. Activity categorization & evidence status normalization
    all_acts = state.get("all_activities")
    if all_acts and isinstance(all_acts, list):
        sanitized_acts = []
        acts_modified = False
        for act in all_acts:
            if not isinstance(act, dict):
                continue
            act_copy = dict(act)
            cat = act_copy.get("category")
            if isinstance(cat, str):
                trimmed_cat = cat.strip().lower()
                if trimmed_cat != cat:
                    act_copy["category"] = trimmed_cat
                    acts_modified = True
            elif not cat:
                atype = str(act_copy.get("activity_type") or "").lower()
                if atype in {"publications", "research", "journal", "conference", "patent"}:
                    act_copy["category"] = "research"
                    acts_modified = True
                elif atype in {"course_delivery", "teaching", "pedagogy"}:
                    act_copy["category"] = "teaching"
                    acts_modified = True
                elif atype in {"committee", "administrative", "coordinator", "outreach"}:
                    act_copy["category"] = "administrative"
                    acts_modified = True
            sanitized_acts.append(act_copy)
        if acts_modified:
            updates["all_activities"] = sanitized_acts
            updates["raw_research"] = [a for a in sanitized_acts if a.get("category") == "research"]
            updates["raw_teaching"] = [a for a in sanitized_acts if a.get("category") == "teaching"]
            updates["raw_admin"] = [a for a in sanitized_acts if a.get("category") == "administrative"]
            repairs_applied.append("normalized_activity_categories")

    # 3. Clear transient repairable errors, but retain unrepairable errors
    errors = list(state.get("errors") or [])
    remaining_errors = [e for e in errors if not any(r in e for r in ("validated_set_malformed", "category_unnormalized"))]
    updates["errors"] = ReplaceList(remaining_errors)

    # 4. Formulate heal_plan
    heal_plan = {
        "attempt": attempt,
        "max_attempts": max_attempts,
        "repairs_applied": repairs_applied,
        "status": "repaired" if repairs_applied else "unrepairable",
    }
    updates["heal_plan"] = heal_plan

    # 5. Append audit event
    healing_event = {
        "event": "graph_self_healing_attempt",
        "attempt": attempt,
        "max_attempts": max_attempts,
        "repairs": repairs_applied,
    }
    updates["audit_events"] = existing_events + [healing_event]

    return updates


def validation_router_legacy(state: AppraisalGraphState) -> str:
    action = state.get("next_action")
    if action == "heal":
        return "heal"
    return "human_gate_placeholder"


def validation_router(state: AppraisalGraphState) -> str:
    action = state.get("next_action")
    if action == "heal":
        return "heal"
    return "human_gate"


def human_gate_placeholder(state: AppraisalGraphState) -> dict:
    """Compile-safe stand-in kept for the legacy compiled_graph and existing tests.

    Returns immediately without interrupting. The checkpointed_graph uses the
    real human_gate node below.
    """
    action = "await_human" if state.get("next_action") != "escalate_human" else "escalate_human"
    return {"approval": None, "next_action": action}


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
            "message": (
                "Appraisal report ready. Awaiting HOD/reviewer governance decision."
                if state.get("next_action") != "escalate_human"
                else "Appraisal self-healing exhausted. Unresolved issues require human review."
            ),
            "faculty_id": state.get("faculty_id"),
            "cycle_id": state.get("cycle_id"),
            "run_id": state.get("run_id"),
            "score_total": (state.get("score_result") or {}).get("total"),
            "rating_recommendation": (state.get("report_draft") or {}).get("rating_recommendation"),
            "research_metrics_status": state.get("research_metrics_status", "not_supplied"),
            "research_metrics_issue": state.get("research_metrics_issue"),
            "escalation_status": state.get("next_action"),
            "validation_errors": (state.get("validation_result") or {}).get("errors", []),
        }
    )

    # decision is the value passed by the reviewer via Command(resume=...)
    # It should be a dict: {"action": "approve"|"reject"|"request_changes",
    #                        "reviewer": <email>, "reason": <str|None>}
    if isinstance(decision, dict):
        action = decision.get("action")
        reason = decision.get("reason")
        reviewer = decision.get("reviewer")
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
    builder.add_node("heal", heal)
    builder.add_node("human_gate_placeholder", human_gate_placeholder)

    builder.add_edge(START, "aura_prepare")
    builder.add_edge("aura_prepare", "retrieve_memory")
    builder.add_conditional_edges(
        "retrieve_memory",
        parallel_collection_router,
    )
    builder.add_edge("collect_research", "evidence_validation")
    builder.add_edge("collect_teaching", "evidence_validation")
    builder.add_edge("collect_admin", "evidence_validation")
    builder.add_edge("evidence_validation", "api_calculation")
    builder.add_edge("api_calculation", "report_generation")
    builder.add_edge("report_generation", "validation_gate")
    builder.add_conditional_edges(
        "validation_gate",
        validation_router_legacy,
        {
            "heal": "heal",
            "human_gate_placeholder": "human_gate_placeholder",
        },
    )
    builder.add_edge("heal", "evidence_validation")
    builder.add_edge("human_gate_placeholder", END)
    return builder.compile()


def build_checkpointed_graph(checkpointer=None):
    """Phase 5C / Lab 3 / SEC-02: Checkpointed graph with human governance gate.

    - Uses official PostgresSaver backed by ConnectionPool(open=False) for PostgreSQL.
    - Uses MemorySaver for explicit SQLite/test environments.
    - Rejects invalid or unsupported schemes with ValueError.
    - Rejects SQLite in production environments.
    """
    from app.core.config import get_settings
    from app.core.checkpointer import get_postgres_saver, is_postgres_url, is_sqlite_url
    from langgraph.checkpoint.memory import MemorySaver

    if checkpointer is None:
        settings = get_settings()
        url = (settings.database_url or "").strip()
        env = (settings.app_env or "development").strip().lower()

        if is_postgres_url(url):
            checkpointer = get_postgres_saver()
        elif is_sqlite_url(url):
            if env in {"production", "prod"}:
                raise ValueError(
                    "SQLite database URL is not permitted for LangGraph checkpoint persistence in production."
                )
            checkpointer = MemorySaver()
        else:
            raise ValueError(
                f"Unsupported database scheme for LangGraph checkpointer: '{url}'. "
                "Expected PostgreSQL (postgresql://) or SQLite (sqlite://)."
            )

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
    builder.add_node("heal", heal)
    builder.add_node("human_gate", human_gate)

    builder.add_edge(START, "aura_prepare")
    builder.add_edge("aura_prepare", "retrieve_memory")
    builder.add_conditional_edges(
        "retrieve_memory",
        parallel_collection_router,
    )
    builder.add_edge("collect_research", "evidence_validation")
    builder.add_edge("collect_teaching", "evidence_validation")
    builder.add_edge("collect_admin", "evidence_validation")
    builder.add_edge("evidence_validation", "api_calculation")
    builder.add_edge("api_calculation", "report_generation")
    builder.add_edge("report_generation", "validation_gate")
    builder.add_conditional_edges(
        "validation_gate",
        validation_router,
        {
            "heal": "heal",
            "human_gate": "human_gate",
        },
    )
    builder.add_edge("heal", "evidence_validation")
    builder.add_edge("human_gate", END)
    return builder.compile(checkpointer=checkpointer)


def get_checkpointed_graph(checkpointer=None):
    """Return a fresh checkpointed graph compiled with the specified or active checkpointer.

    Addresses the stale-checkpointer risk across checkpointer re-initialization cycles.
    """
    return build_checkpointed_graph(checkpointer=checkpointer)


compiled_graph = build_graph()

# Phase 5C / Lab 3 / SEC-02: Checkpointed graph for real appraisal runs.
# Backed by PostgresSaver via ConnectionPool(open=False) when PostgreSQL is configured.
checkpointed_graph = build_checkpointed_graph()

GRAPH_NODE_NAMES = LAB7_NODE_SEQUENCE
