"""Deterministic appraisal scoring. No LLM imports or calls."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ENGINE_VERSION = "1.1.0"
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
    source: str = "activity"
    label: str | None = None
    value: Any = None
    provenance: dict[str, Any] | None = None


@dataclass
class LineItem:
    activity_id: str
    rubric_code: str
    points: float
    evidence_ids: list[str]
    source: str = "activity"
    label: str | None = None
    value: Any = None
    provenance: dict[str, Any] | None = None
    category: str | None = None
    category_weight: float | None = None
    weighted_points: float | None = None
    cap: float | None = None
    status: str = "scored"


@dataclass
class ScoreResult:
    total: float
    category_totals: dict[str, float]
    category_raw_totals: dict[str, float]
    line_items: list[LineItem]
    rating_recommendation: str
    category_weights: dict[str, float] = field(default_factory=dict)
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
    code_caps: dict[str, float] = {}
    scholar_config = rubric.get("scholar_impact") or {}
    scholar_metric_codes = {
        item.get("rubric_code"): item
        for item in (scholar_config.get("metrics") or {}).values()
        if isinstance(item, dict) and item.get("rubric_code")
    }

    for activity in activities:
        is_scholar = activity.source == "google_scholar"
        is_feedback = activity.source == "student_feedback"
        if activity.source not in {"activity", "google_scholar", "student_feedback"}:
            raise ScoringError(f"Unknown score source: {activity.source}")
        if not is_scholar and not is_feedback and not activity.evidence_ids:
            raise ScoringError(f"Activity {activity.activity_id} has no supporting evidence")
        if activity.category not in categories:
            raise ScoringError(f"Unknown category: {activity.category}")
        if is_scholar:
            if activity.category != "research":
                raise ScoringError("Google Scholar inputs must belong to research")
            if activity.rubric_code in scholar_metric_codes:
                raw = float(activity.quantity)
                cap = float(scholar_metric_codes[activity.rubric_code]["cap"])
            else:
                items = categories[activity.category]["items"]
                if activity.rubric_code not in items or activity.rubric_code not in {
                    scholar_config.get("current_year_publications", {}).get("journal_rubric_code"),
                    scholar_config.get("current_year_publications", {}).get("conference_rubric_code"),
                }:
                    raise ScoringError(f"Unknown Google Scholar rubric code: {activity.rubric_code}")
                raw = _item_points(items[activity.rubric_code], activity.quantity)
                cap = float(items[activity.rubric_code]["cap"])
        elif is_feedback:
            if activity.category != "teaching":
                raise ScoringError("Student feedback inputs must belong to teaching")
            items = categories[activity.category]["items"]
            if activity.rubric_code not in items:
                raise ScoringError(f"Unknown student feedback rubric code: {activity.rubric_code}")
            raw = float(activity.quantity)
            cap = float(items[activity.rubric_code]["cap"])
        else:
            items = categories[activity.category]["items"]
            if activity.rubric_code not in items:
                raise ScoringError(f"Unknown rubric code: {activity.rubric_code}")
            raw = _item_points(items[activity.rubric_code], activity.quantity)
            cap = float(items[activity.rubric_code]["cap"])

        cat_weight = float(categories[activity.category].get("weight", 0.0))
        item_raw = round(raw, 4)
        item_cap = round(cap, 4)
        item_weighted = round(item_raw * cat_weight, 4)
        item_status = "capped" if item_raw > item_cap else "scored"

        line_items.append(
            LineItem(
                activity_id=activity.activity_id,
                rubric_code=activity.rubric_code,
                points=item_raw,
                evidence_ids=list(activity.evidence_ids),
                source=activity.source,
                label=activity.label,
                value=activity.value,
                provenance=activity.provenance,
                category=activity.category,
                category_weight=cat_weight,
                weighted_points=item_weighted,
                cap=item_cap,
                status=item_status,
            )
        )
        key = f"{activity.category}:{activity.rubric_code}"
        per_code[key] = per_code.get(key, 0.0) + raw
        code_caps[key] = min(code_caps.get(key, cap), cap)

    capped: dict[str, float] = {}
    for key, value in per_code.items():
        category, code = key.split(":", 1)
        cap = code_caps[key]
        capped[key] = min(value, cap)

    category_raw: dict[str, float] = {name: 0.0 for name in categories}
    for key, value in capped.items():
        category, _code = key.split(":", 1)
        category_raw[category] += value

    for name, spec in categories.items():
        raw_cap = spec.get("raw_score_cap")
        if raw_cap is not None:
            category_raw[name] = min(category_raw[name], float(raw_cap))

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
        category_raw_totals={name: round(value, 4) for name, value in category_raw.items()},
        line_items=line_items,
        rating_recommendation=rating,
        category_weights={name: float(spec.get("weight", 0.0)) for name, spec in categories.items()},
        rubric_id=str(rubric.get("id", "DEMO_RUBRIC_v1")),
        is_demo=bool(rubric.get("is_demo", True)),
        disclaimer=str(rubric.get("disclaimer", "")),
    )
