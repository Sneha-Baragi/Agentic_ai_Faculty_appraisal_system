from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from app.scoring.engine import ActivityScoreInput
from app.services.constants import TYPE_TO_RUBRIC
from app.services.student_feedback import calculate_student_feedback_points


def to_score_inputs(accepted_activities: list[dict]) -> list[ActivityScoreInput]:
    """Map evidence-validated activity dicts onto the existing rubric codes."""
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


def to_scholar_score_inputs(
    snapshot: dict[str, Any] | None,
    *,
    appraisal_year: int | None,
    expected_scholar_id: str | None,
    cycle_id: str | None,
    manual_activities: list[dict[str, Any]],
    rubric: dict[str, Any],
) -> tuple[list[ActivityScoreInput], list[dict[str, Any]]]:
    """Adapt a fresh identity-verified Scholar snapshot to research score inputs."""
    if not isinstance(snapshot, dict):
        return [], []

    publications = [dict(item) for item in snapshot.get("publications", []) if isinstance(item, dict)]
    valid_identity = (
        snapshot.get("status") == "retrieved"
        and snapshot.get("human_review_required") is False
        and isinstance(expected_scholar_id, str)
        and bool(expected_scholar_id)
        and snapshot.get("scholar_id") == expected_scholar_id
    )
    if not valid_identity:
        for publication in publications:
            publication["scoring_status"] = "scholar_retrieval_unavailable_or_unverified"
        return [], publications

    scholar_config = rubric.get("scholar_impact") or {}
    metrics = snapshot.get("metrics") or {}
    provenance_base = {
        "source": "Google Scholar / SerpApi",
        "provider": snapshot.get("provider"),
        "scholar_id": snapshot.get("scholar_id"),
        "scholar_url": snapshot.get("scholar_url"),
        "retrieved_at": snapshot.get("retrieved_at"),
        "appraisal_cycle_id": cycle_id,
        "appraisal_year": appraisal_year,
    }
    inputs: list[ActivityScoreInput] = []

    for metric_name, metric_rule in (scholar_config.get("metrics") or {}).items():
        value = metrics.get(metric_name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            continue
        points = _points_for_band(value, metric_rule.get("bands", []))
        rubric_code = metric_rule.get("rubric_code")
        if rubric_code:
            inputs.append(
                ActivityScoreInput(
                    activity_id=f"scholar:{metric_name}",
                    category="research",
                    rubric_code=rubric_code,
                    evidence_ids=(),
                    quantity=points,
                    source="google_scholar",
                    label=f"Google Scholar - {metric_name.replace('_', ' ').title()}",
                    value=value,
                    provenance=dict(provenance_base),
                )
            )

    publications_config = scholar_config.get("current_year_publications") or {}
    classification_config = scholar_config.get("publication_classification") or {}
    manual_keys, manual_citation_ids = _manual_publication_keys(manual_activities)
    seen_scholar_keys: set[tuple[str, int]] = set()
    seen_scholar_citation_ids: set[str] = set()

    for publication in publications:
        year = publication.get("year")
        title = publication.get("title")
        classification = _classify_publication(publication.get("publication"), classification_config)
        publication["classification"] = classification
        if not isinstance(year, int) or isinstance(year, bool) or year != appraisal_year:
            publication["scoring_status"] = "outside_appraisal_year"
            continue
        if not isinstance(title, str) or not title.strip() or classification is None:
            publication["scoring_status"] = "unclassified"
            continue

        normalized_title = _normalize_title(title)
        citation_id = publication.get("citation_id")
        scholar_key = (normalized_title, year)
        if (citation_id and citation_id in seen_scholar_citation_ids) or scholar_key in seen_scholar_keys:
            publication["scoring_status"] = "duplicate_scholar_publication"
            continue
        if (citation_id and citation_id in manual_citation_ids) or (
            normalized_title,
            year,
        ) in manual_keys or any(
            manual_title == normalized_title and (manual_year is None or manual_year == year)
            for manual_title, manual_year in manual_keys
        ):
            publication["scoring_status"] = "duplicate_of_manual_activity"
            continue

        seen_scholar_keys.add(scholar_key)
        if isinstance(citation_id, str) and citation_id:
            seen_scholar_citation_ids.add(citation_id)

        rubric_code = publications_config.get(f"{classification}_rubric_code")
        if not rubric_code:
            publication["scoring_status"] = "unclassified"
            continue
        publication["scoring_status"] = "scored"
        publication["rubric_code"] = rubric_code
        stable_id = citation_id or hashlib.sha256(f"{normalized_title}:{year}".encode()).hexdigest()[:16]
        publication_provenance = {
            **provenance_base,
            "publication_title": title,
            "publication_year": year,
            "citation_id": citation_id,
            "link": publication.get("link"),
        }
        inputs.append(
            ActivityScoreInput(
                activity_id=f"scholar-publication:{stable_id}",
                category="research",
                rubric_code=rubric_code,
                evidence_ids=(),
                source="google_scholar",
                label=f"Google Scholar - Current-year {classification.replace('_', ' ')} paper",
                value=title,
                provenance=publication_provenance,
            )
        )

    return inputs, publications

def to_student_feedback_score_input(
    feedback_data: dict[str, Any] | None,
    rubric: dict[str, Any],
) -> ActivityScoreInput | None:
    """Adapt student feedback record to teaching score input."""
    if not isinstance(feedback_data, dict):
        return None

    percentage = feedback_data.get("feedback_percentage")
    if percentage is None or not isinstance(percentage, (int, float)) or isinstance(percentage, bool):
        return None

    teaching_items = (rubric.get("categories") or {}).get("teaching", {}).get("items") or {}
    feedback_spec = teaching_items.get("student_feedback")
    if not isinstance(feedback_spec, dict):
        return None

    item_cap = float(feedback_spec.get("cap", 10.0))
    raw_points = calculate_student_feedback_points(float(percentage), item_cap)
    faculty_name = feedback_data.get("faculty_name")
    source_file = feedback_data.get("source_file") or "synthetic_student_feedback.csv"

    provenance = {
        "source": "Institutional Student Feedback CSV",
        "faculty_name": faculty_name,
        "feedback_percentage": float(percentage),
        "source_file": source_file,
        "item_cap": item_cap,
        "calculation_formula": "(feedback_percentage / 100) * item_cap",
    }

    val_display = f"{int(percentage)}%" if float(percentage).is_integer() else f"{percentage}%"

    return ActivityScoreInput(
        activity_id="feedback:student_feedback",
        category="teaching",
        rubric_code="student_feedback",
        evidence_ids=(),
        quantity=raw_points,
        source="student_feedback",
        label="Student Feedback",
        value=val_display,
        provenance=provenance,
    )



def appraisal_year_from_cycle(academic_year: str | None) -> int | None:
    """Use the starting calendar year encoded by the appraisal cycle label."""
    if not isinstance(academic_year, str):
        return None
    match = re.search(r"\b(\d{4})\b", academic_year)
    return int(match.group(1)) if match else None


def _points_for_band(value: int, bands: list[dict[str, Any]]) -> float:
    for band in bands:
        minimum = band.get("min")
        maximum = band.get("max")
        if isinstance(minimum, int) and value >= minimum and (maximum is None or value <= maximum):
            return float(band.get("points", 0))
    return 0.0


def _classify_publication(venue: Any, config: dict[str, Any]) -> str | None:
    if not isinstance(venue, str) or not venue.strip():
        return None
    normalized_venue = venue.casefold()
    journal = any(token.casefold() in normalized_venue for token in config.get("journal_indicators", []))
    conference = any(token.casefold() in normalized_venue for token in config.get("conference_indicators", []))
    if journal == conference:
        return None
    return "journal" if journal else "conference"


def _normalize_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.findall(r"\w+", normalized))


def _manual_publication_keys(
    activities: list[dict[str, Any]],
) -> tuple[set[tuple[str, int | None]], set[str]]:
    keys: set[tuple[str, int | None]] = set()
    citation_ids: set[str] = set()
    for activity in activities:
        if activity.get("category") != "research" or activity.get("activity_type") not in {"publications", "conferences"}:
            continue
        title = activity.get("title")
        details = activity.get("details") or {}
        if isinstance(title, str) and title.strip():
            year = details.get("year")
            keys.add((_normalize_title(title), year if isinstance(year, int) and not isinstance(year, bool) else None))
        citation_id = activity.get("citation_id") or details.get("citation_id")
        if isinstance(citation_id, str) and citation_id:
            citation_ids.add(citation_id)
    return keys, citation_ids
