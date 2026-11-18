"""API Calculation Specialist Agent for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.schemas import WorkflowState


class APICalculationAgent:
    """Calculates Academic Performance Indicator (API) scores with weightage enforcement."""

    def __init__(self, weightages_path: Optional[Path] = None) -> None:
        """Initialize calculation agent with path to weightages configuration."""
        if weightages_path is None:
            self.weightages_path = Path(__file__).resolve().parent.parent / "data" / "weightages.json"
        else:
            self.weightages_path = Path(weightages_path)

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Calculate category-wise and overall API scores from validated activities.

        Rules:
        - Only VERIFIED activities contribute to verified score.
        - Activities with missing, mismatched, or incomplete evidence contribute 0.0 to verified score.
        - If unresolved evidence exceptions exist or collection was partial/failed, score is PROVISIONAL.
        - Transparent mathematical breakdown is recorded.
        - Weightages are strictly illustrative mock values.
        """
        weightages_config: Dict[str, Any] = {
            "version": "1.0.0-illustrative-mock",
            "disclaimer": "These scoring weightages are illustrative mock values configured for Lab 8 hands-on demonstration and must never be construed as official UGC or institutional statutes.",
            "category_weights": {
                "Research": 0.40,
                "Teaching_Learning": 0.40,
                "Administrative": 0.20,
            },
        }

        if self.weightages_path.exists():
            with open(self.weightages_path, "r", encoding="utf-8") as f:
                weightages_config = json.load(f)

        category_weights: Dict[str, float] = weightages_config.get(
            "category_weights",
            {"Research": 0.40, "Teaching_Learning": 0.40, "Administrative": 0.20},
        )
        weight_version = weightages_config.get("version", "1.0.0-illustrative-mock")
        disclaimer = weightages_config.get("disclaimer", "Illustrative mock weightages.")

        # Check for unresolved exceptions, partial collection, or consent limitations
        unresolved_exceptions = state.evidence_exceptions
        merge_status = state.merge_result.get("status") if state.merge_result else "SUCCESS"
        skipped_collectors = state.merge_result.get("skipped_collectors", []) if state.merge_result else []

        # Map categories to their collector roles and consent keys
        category_meta = {
            "Research": {
                "consent_key": "research",
                "collector_role": "ResearchDataCollectionAgent",
            },
            "Teaching_Learning": {
                "consent_key": "teaching_learning",
                "collector_role": "TeachingDataCollectionAgent",
            },
            "Administrative": {
                "consent_key": "administrative",
                "collector_role": "AdministrativeDataCollectionAgent",
            },
        }

        raw_points_by_cat = {"Research": 0.0, "Teaching_Learning": 0.0, "Administrative": 0.0}
        verified_points_by_cat = {"Research": 0.0, "Teaching_Learning": 0.0, "Administrative": 0.0}
        detailed_breakdown: List[Dict[str, Any]] = []

        for act in state.validated_activities:
            cat = act.get("category", "Research")
            claimed_pts = float(act.get("claimed_points", 0.0))
            is_verified = (act.get("evidence_status") == "VERIFIED")
            verified_pts = claimed_pts if is_verified else 0.0

            if cat in raw_points_by_cat:
                raw_points_by_cat[cat] += claimed_pts
                verified_points_by_cat[cat] += verified_pts

            weight = category_weights.get(cat, 0.0)
            contribution = round(verified_pts * weight, 2)

            detailed_breakdown.append({
                "activity_id": act.get("activity_id"),
                "title": act.get("title"),
                "category": cat,
                "collector_role": act.get("collector_role"),
                "claimed_points": claimed_pts,
                "verified_points": verified_pts,
                "status": act.get("evidence_status"),
                "applied_weightage": weight,
                "calculated_contribution": contribution,
            })

        category_scores: Dict[str, Dict[str, Any]] = {}
        total_raw_api = 0.0
        total_verified_api = 0.0
        skipped_categories: List[str] = []

        for cat, weight in category_weights.items():
            meta = category_meta.get(cat, {})
            consent_key = meta.get("consent_key", "")
            role_name = meta.get("collector_role", "")

            # Check if this category was skipped due to withheld consent
            is_consent_denied = (
                not state.consent.get(consent_key, True)
                or role_name in skipped_collectors
                or (state.swarm_results and state.swarm_results.get(role_name, {}).get("status") == "SKIPPED")
            )

            if is_consent_denied:
                skipped_categories.append(cat)
                category_scores[cat] = {
                    "category": cat,
                    "status": "NOT_COLLECTED_CONSENT_DENIED",
                    "collection_status": "SKIPPED_CONSENT_DENIED",
                    "is_collected": False,
                    "is_verified_zero": False,
                    "raw_claimed_points": None,
                    "verified_points": None,
                    "weightage": weight,
                    "raw_weighted_score": None,
                    "verified_weighted_score": None,
                    "notes": "Not collected: Faculty withheld consent for this category. This is NOT a verified zero score.",
                }
            else:
                raw_pts = raw_points_by_cat.get(cat, 0.0)
                ver_pts = verified_points_by_cat.get(cat, 0.0)
                raw_weighted = round(raw_pts * weight, 2)
                ver_weighted = round(ver_pts * weight, 2)

                is_zero = (raw_pts == 0.0 and ver_pts == 0.0)
                cat_status = "VERIFIED_ZERO" if is_zero else "VERIFIED"

                category_scores[cat] = {
                    "category": cat,
                    "status": cat_status,
                    "collection_status": "COLLECTED",
                    "is_collected": True,
                    "is_verified_zero": is_zero,
                    "raw_claimed_points": raw_pts,
                    "verified_points": ver_pts,
                    "weightage": weight,
                    "raw_weighted_score": raw_weighted,
                    "verified_weighted_score": ver_weighted,
                    "notes": "Category collected and verified." if not is_zero else "Category collected: genuinely verified zero points.",
                }
                total_raw_api += raw_weighted
                total_verified_api += ver_weighted

        is_consent_limited = len(skipped_categories) > 0
        has_exceptions = len(unresolved_exceptions) > 0
        is_partial = merge_status in ("PARTIAL", "FAILED")

        is_provisional = has_exceptions or is_partial or is_consent_limited

        if is_consent_limited:
            score_status = "CONSENT_LIMITED"
            score_type = "PARTIAL_CONSENT_LIMITED"
            score_label = "PARTIAL SCORE (Consent-Limited: excludes skipped categories)"
            score_note = (
                f"Partial score reflects ONLY collected categories "
                f"{sorted(list(set(category_weights.keys()) - set(skipped_categories)))}. "
                f"Category {skipped_categories} was skipped due to withheld consent and is not scored."
            )
        elif is_provisional:
            score_status = "PROVISIONAL"
            score_type = "PROVISIONAL"
            score_label = "PROVISIONAL SCORE (Pending Evidence Resolution or Collector Retry)"
            score_note = "Score contains unresolved evidence exceptions or incomplete collection."
        else:
            score_status = "FINALIZED_PENDING_APPROVAL"
            score_type = "FINAL"
            score_label = "FINAL APPRAISAL SCORE"
            score_note = "All categories collected, verified, and weighted according to institutional criteria."

        api_score_payload = {
            "is_provisional": is_provisional,
            "is_consent_limited": is_consent_limited,
            "score_status": score_status,
            "score_type": score_type,
            "score_label": score_label,
            "score_note": score_note,
            "weightage_version": weight_version,
            "weightage_disclaimer": disclaimer,
            "overall_claimed_score": round(total_raw_api, 2),
            "overall_verified_score": round(total_verified_api, 2),
            "category_scores": category_scores,
            "detailed_breakdown": detailed_breakdown,
            "unresolved_exceptions_count": len(unresolved_exceptions),
            "skipped_categories": skipped_categories,
        }

        state.api_score = api_score_payload
        state.workflow_status = "SCORED"

        state.add_audit_entry(
            node_name="APICalculationAgent",
            action="API_CALCULATION_COMPLETE",
            details={
                "is_provisional": is_provisional,
                "score_status": score_status,
                "overall_claimed": round(total_raw_api, 2),
                "overall_verified": round(total_verified_api, 2),
                "exceptions_count": len(unresolved_exceptions),
            },
            status="WARNING" if is_provisional else "SUCCESS",
        )

        return state
