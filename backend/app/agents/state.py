from typing import Any, TypedDict


class AppraisalGraphState(TypedDict, total=False):
    run_id: str
    faculty_id: str
    cycle_id: str
    rubric_id: str
    attempt: int
    max_attempts: int
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
    errors: list[str]
    audit_events: list[dict[str, Any]]
    next_action: str


class PlannerGraphState(TypedDict, total=False):
    request: str
    inputs: dict[str, Any]
    clarification_questions: list[str]
    plan: dict[str, Any]
    status: str
