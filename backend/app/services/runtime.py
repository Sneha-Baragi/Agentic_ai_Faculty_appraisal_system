from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class RuntimeContext:
    """Serializable execution context for one appraisal runtime run."""

    faculty_id: str
    cycle_id: str
    run_id: str
    thread_id: str
    execution_scope: dict[str, Any] = field(default_factory=dict)
    memory_context: dict[str, Any] | None = None
    audit_context: dict[str, Any] = field(default_factory=lambda: {"events": []})


class AppraisalRuntime:
    """Thin coordinator abstraction for the existing LangGraph appraisal workflow.

    This layer intentionally does not replace LangGraph or perform direct database
    access. It only prepares a serializable runtime context and exposes small
    helper methods for run state tracking and checkpoint-oriented execution.
    """

    def __init__(self, *, graph: Any | None = None) -> None:
        self.graph = graph

    def create_context(
        self,
        *,
        faculty_id: str,
        cycle_id: str,
        run_id: str,
        thread_id: str | None = None,
        execution_scope: Mapping[str, Any] | None = None,
        memory_context: Mapping[str, Any] | None = None,
        audit_context: Mapping[str, Any] | None = None,
    ) -> RuntimeContext:
        resolved_scope = dict(execution_scope or {})
        resolved_scope.setdefault("faculty_id", str(faculty_id))
        resolved_scope.setdefault("cycle_id", str(cycle_id))
        resolved_scope.setdefault("run_id", str(run_id))
        resolved_scope.setdefault("allowed_scope", {
            "faculty_id": str(faculty_id),
            "cycle_id": str(cycle_id),
            "run_id": str(run_id),
        })

        resolved_audit = {"events": []}
        if audit_context:
            resolved_audit.update(dict(audit_context))
            if "events" in dict(audit_context):
                resolved_audit["events"] = list(dict(audit_context).get("events") or [])

        resolved_thread_id = str(thread_id) if thread_id else str(run_id)

        return RuntimeContext(
            faculty_id=str(faculty_id),
            cycle_id=str(cycle_id),
            run_id=str(run_id),
            thread_id=resolved_thread_id,
            execution_scope=resolved_scope,
            memory_context=dict(memory_context) if memory_context is not None else None,
            audit_context=resolved_audit,
        )

    def record_start(self, context: RuntimeContext, **payload: Any) -> dict[str, Any]:
        event = {
            "event": "run_started",
            "phase": "runtime_start",
            "run_id": context.run_id,
            "thread_id": context.thread_id,
            "faculty_id": context.faculty_id,
            "cycle_id": context.cycle_id,
        }
        event.update(payload)
        context.audit_context.setdefault("events", [])
        context.audit_context["events"].append(event)
        return event

    def record_resume(self, context: RuntimeContext, **payload: Any) -> dict[str, Any]:
        event = {
            "event": "run_resumed",
            "phase": "runtime_resume",
            "run_id": context.run_id,
            "thread_id": context.thread_id,
            "faculty_id": context.faculty_id,
            "cycle_id": context.cycle_id,
        }
        event.update(payload)
        context.audit_context.setdefault("events", [])
        context.audit_context["events"].append(event)
        return event

    def prepare_resume(
        self,
        context: RuntimeContext,
        *,
        action: str,
        reason: str | None = None,
        reviewer: str | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        resume_context = {
            "run_id": context.run_id,
            "thread_id": context.thread_id,
            "faculty_id": context.faculty_id,
            "cycle_id": context.cycle_id,
            "execution_scope": dict(context.execution_scope),
            "action": action,
            "reason": reason,
            "reviewer": reviewer,
        }
        resume_context.update(payload)
        self.record_resume(context, action=action, reason=reason, reviewer=reviewer, **payload)
        return resume_context

    def record_approval_required(self, context: RuntimeContext, **payload: Any) -> dict[str, Any]:
        event = {
            "event": "approval_required",
            "phase": "human_approval",
            "run_id": context.run_id,
            "thread_id": context.thread_id,
            "faculty_id": context.faculty_id,
            "cycle_id": context.cycle_id,
        }
        event.update(payload)
        context.audit_context.setdefault("events", [])
        context.audit_context["events"].append(event)
        return event

    def snapshot(self, context: RuntimeContext, state: Mapping[str, Any] | None = None) -> dict[str, Any]:
        source = dict(state or {})
        runtime_events = list(context.audit_context.get("events") or [])
        if "audit_events" in source:
            runtime_events = list(source.get("audit_events") or [])
        elif source.get("audit_events") is not None:
            runtime_events = list(source.get("audit_events") or [])

        data: dict[str, Any] = {
            "run_id": context.run_id,
            "thread_id": context.thread_id,
            "faculty_id": context.faculty_id,
            "cycle_id": context.cycle_id,
            "execution_scope": dict(context.execution_scope),
            "memory_context": dict(context.memory_context) if context.memory_context is not None else None,
            "audit_events": runtime_events,
        }

        for key in ("next_action", "approval", "validation_result"):
            if key in source:
                data[key] = source[key]
        return data


__all__ = ["RuntimeContext", "AppraisalRuntime"]
