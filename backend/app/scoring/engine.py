"""Deterministic appraisal scoring. No LLM imports or calls."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ENGINE_VERSION = "1.0.0"
DEMO_RUBRIC_PATH = Path(__file__).with_name("demo_rubric.json")


class ScoringError(ValueError):
    """Raised when an activity cannot be scored from the approved rubric."""


@dataclass(frozen=True)
class ActivityScoreInput:
    activity_id: str
    category: str
    rubric_code: str
    evidence_ids: tuple[str, ...]
    quantity: float = 1.0


@dataclass
class LineItem:
    activity_id: str
    rubric_code: str
    points: float
    evidence_ids: list[str]


@dataclass
class ScoreResult:
    total: float
    category_totals: dict[str, float]
    line_items: list[LineItem]
    rating_recommendation: str
    engine_version: str = ENGINE_VERSION
    rubric_id: str = "DEMO_RUBRIC_v1"
    is_demo: bool = True
    disclaimer: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def load_demo_rubric() -> dict[str, Any]:
    return json.loads(DEMO_RUBRIC_PATH.read_text(encoding="utf-8"))


def _item_points(item_def: dict[str, Any], quantity: float) -> float:
    if "points_per_hour" in item_def:
        return float(item_def["points_per_hour"]) * quantity
    return float(item_def["points"]) * quantity


def _rating_for(total: float, bands: list[dict[str, Any]]) -> str:
    ordered = sorted(bands, key=lambda band: band["min"], reverse=True)
    for band in ordered:
        if total >= band["min"]:
            return str(band["rating"])
    return "D"


def calculate_score(
    activities: list[ActivityScoreInput],
    rubric: dict[str, Any] | None = None,
) -> ScoreResult:
    """Map validated activities onto rubric codes and compute a numeric total.

    The LLM must never call this with a fabricated total. This function ignores
    any extra fields and only uses whitelist rubric codes plus evidence ids.
    """
    rubric = rubric or load_demo_rubric()
    categories = rubric["categories"]
    line_items: list[LineItem] = []
    per_code: dict[str, float] = {}

    for activity in activities:
        if not activity.evidence_ids:
            raise ScoringError(f"Activity {activity.activity_id} has no supporting evidence")
        if activity.category not in categories:
            raise ScoringError(f"Unknown category: {activity.category}")
        items = categories[activity.category]["items"]
        if activity.rubric_code not in items:
            raise ScoringError(f"Unknown rubric code: {activity.rubric_code}")

        raw = _item_points(items[activity.rubric_code], activity.quantity)
        line_items.append(
            LineItem(
                activity_id=activity.activity_id,
                rubric_code=activity.rubric_code,
                points=round(raw, 4),
                evidence_ids=list(activity.evidence_ids),
            )
        )
        key = f"{activity.category}:{activity.rubric_code}"
        per_code[key] = per_code.get(key, 0.0) + raw

    capped: dict[str, float] = {}
    for key, value in per_code.items():
        category, code = key.split(":", 1)
        cap = float(categories[category]["items"][code]["cap"])
        capped[key] = min(value, cap)

    category_raw: dict[str, float] = {name: 0.0 for name in categories}
    for key, value in capped.items():
        category, _code = key.split(":", 1)
        category_raw[category] += value

    category_totals: dict[str, float] = {}
    total = 0.0
    for name, spec in categories.items():
        weighted = round(category_raw.get(name, 0.0) * float(spec["weight"]), 4)
        category_totals[name] = weighted
        total += weighted

    total = round(total, 4)
    rating = _rating_for(total, rubric["rating_bands"])
    return ScoreResult(
        total=total,
        category_totals=category_totals,
        line_items=line_items,
        rating_recommendation=rating,
        rubric_id=str(rubric.get("id", "DEMO_RUBRIC_v1")),
        is_demo=bool(rubric.get("is_demo", True)),
        disclaimer=str(rubric.get("disclaimer", "")),
    )
