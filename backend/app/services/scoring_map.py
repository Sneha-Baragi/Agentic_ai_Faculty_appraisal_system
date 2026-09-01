from __future__ import annotations

from app.scoring.engine import ActivityScoreInput
from app.services.constants import TYPE_TO_RUBRIC


def to_score_inputs(accepted_activities: list[dict]) -> list[ActivityScoreInput]:
    """Map validated activity dicts onto DEMO rubric codes. Does not invent scores."""
    inputs: list[ActivityScoreInput] = []
    for item in accepted_activities:
        activity_type = item.get("activity_type") or ""
        mapping = TYPE_TO_RUBRIC.get(activity_type)
        if mapping is None:
            continue
        category, rubric_code, default_qty = mapping
        evidence_ids = tuple(item.get("evidence_ids") or [])
        if not evidence_ids:
            continue
        quantity = item.get("quantity")
        if quantity is None:
            quantity = default_qty if default_qty is not None else 1.0
        inputs.append(
            ActivityScoreInput(
                activity_id=str(item["id"]),
                category=category,
                rubric_code=rubric_code,
                evidence_ids=evidence_ids,
                quantity=float(quantity),
            )
        )
    return inputs
