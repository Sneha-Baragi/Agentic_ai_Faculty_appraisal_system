from __future__ import annotations

from typing import Annotated, Any, TypedDict


class ReplaceList(list):
    """Marker class to indicate an update should replace the current list rather than merge."""
    pass


def merge_audit_events(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if isinstance(right, ReplaceList):
        return list(right)
    if left is None:
        left = []
    if right is None:
        right = []
    result = list(left)
    for item in right:
        if item not in result:
            result.append(item)
    return result


def merge_errors(
    left: list[str] | None,
    right: list[str] | None,
) -> list[str]:
    if isinstance(right, ReplaceList):
        return list(right)
    if left is None:
        left = []
    if right is None:
        right = []
    result = list(left)
    for err in right:
        if err not in result:
            result.append(err)
    return result


class AppraisalGraphState(TypedDict, total=False):
    run_id: str
    faculty_id: str
    faculty_name: str | None
    cycle_id: str
    rubric_id: str
    attempt: int
    max_attempts: int
    memory_context: dict[str, Any] | None
    research_metrics_status: str
    research_metrics_issue: str | None
    research_metrics: dict[str, Any] | None
    configured_scholar_id: str | None
    cycle_academic_year: str | None
    all_activities: list[dict[str, Any]]
    raw_research: list[dict[str, Any]]
    raw_teaching: list[dict[str, Any]]
    raw_admin: list[dict[str, Any]]
    validated_set: dict[str, Any] | None
    score_result: dict[str, Any] | None
    report_draft: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    heal_plan: dict[str, Any] | None
    approval: dict[str, Any] | None
    errors: Annotated[list[str], merge_errors]
    audit_events: Annotated[list[dict[str, Any]], merge_audit_events]
    next_action: str
    student_feedback: dict[str, Any] | None


class PlannerGraphState(TypedDict, total=False):
    request: str
    inputs: dict[str, Any]
    clarification_questions: list[str]
    plan: dict[str, Any]
    status: str
