from __future__ import annotations

from typing import Any, TypedDict
from langgraph.graph import END, START, StateGraph

from app.services.sdlc_factory import (
    compute_plan_hash,
    generate_sdlc_plan,
    run_allowlisted_verification,
)


class SDLCGraphState(TypedDict, total=False):
    task_id: str
    user_id: str
    title: str
    description: str
    target_files: list[str]
    status: str
    plan: dict[str, Any]
    approved_plan_hash: str | None
    execution_results: list[dict[str, Any]]
    rejection_reason: str | None
    errors: list[str]


def sdlc_plan_node(state: SDLCGraphState) -> dict[str, Any]:
    task_id = state.get("task_id") or "sdlc-temp"
    title = state.get("title") or "Development Task"
    description = state.get("description") or "SDLC task description"
    target_files = state.get("target_files") or []

    plan = generate_sdlc_plan(task_id, title, description, target_files)
    return {
        "status": "awaiting_approval",
        "plan": plan,
    }


def sdlc_human_gate_node(state: SDLCGraphState) -> dict[str, Any]:
    status = state.get("status", "awaiting_approval")
    plan = state.get("plan") or {}
    approved_hash = state.get("approved_plan_hash")
    current_hash = plan.get("plan_hash")

    if status == "approved" and approved_hash == current_hash:
        return {"status": "approved"}
    elif status == "rejected":
        return {"status": "rejected"}
    else:
        return {"status": "awaiting_approval"}


def sdlc_execute_node(state: SDLCGraphState) -> dict[str, Any]:
    status = state.get("status")
    if status != "approved":
        return {
            "status": "failed",
            "errors": [f"Cannot execute task in status '{status}'. Explicit human approval required."],
        }

    res = run_allowlisted_verification("pytest_quick", timeout_seconds=30)
    exec_results = list(state.get("execution_results") or [])
    exec_results.append(res)

    if res["success"]:
        return {"status": "completed", "execution_results": exec_results}
    else:
        return {
            "status": "failed",
            "execution_results": exec_results,
            "errors": [f"Verification command failed with exit code {res['exit_code']}"],
        }


def build_sdlc_graph():
    builder = StateGraph(SDLCGraphState)
    builder.add_node("sdlc_plan_node", sdlc_plan_node)
    builder.add_node("sdlc_human_gate_node", sdlc_human_gate_node)
    builder.add_node("sdlc_execute_node", sdlc_execute_node)

    builder.add_edge(START, "sdlc_plan_node")
    builder.add_edge("sdlc_plan_node", "sdlc_human_gate_node")
    builder.add_edge("sdlc_human_gate_node", "sdlc_execute_node")
    builder.add_edge("sdlc_execute_node", END)

    return builder.compile()


sdlc_graph = build_sdlc_graph()
