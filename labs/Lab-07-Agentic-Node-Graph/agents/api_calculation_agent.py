"""Node 5: API Calculation Agent (Group E).

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
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
        """Calculate component-wise and overall API scores from validated activities.

        Rules:
        - Only VERIFIED activities contribute to verified score.
        - Activities with exceptions do NOT contribute to verified points.
        - If unresolved evidence exceptions exist, score is flagged as PROVISIONAL.
        - Finalized scores can only be produced when zero evidence exceptions exist.
        """
        # Load weightages configuration
        weightages_config: Dict[str, Any] = {
            "version": "1.0.0-illustrative-mock",
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

        # Unresolved exceptions determine provisional vs finalized status
        unresolved_exceptions = state.evidence_exceptions
        is_provisional = len(unresolved_exceptions) > 0

        # Category accumulators
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
                "claimed_points": claimed_pts,
                "verified_points": verified_pts,
                "status": act.get("evidence_status"),
                "applied_weightage": weight,
                "calculated_contribution": contribution,
            })

        # Calculate weighted category scores and overall totals
        category_scores: Dict[str, Dict[str, float]] = {}
        total_raw_api = 0.0
        total_verified_api = 0.0

        for cat, weight in category_weights.items():
            raw_pts = raw_points_by_cat.get(cat, 0.0)
            ver_pts = verified_points_by_cat.get(cat, 0.0)
            raw_weighted = round(raw_pts * weight, 2)
            ver_weighted = round(ver_pts * weight, 2)

            category_scores[cat] = {
                "raw_claimed_points": raw_pts,
                "verified_points": ver_pts,
                "weightage": weight,
                "raw_weighted_score": raw_weighted,
                "verified_weighted_score": ver_weighted,
            }
            total_raw_api += raw_weighted
            total_verified_api += ver_weighted

        api_score_payload = {
            "is_provisional": is_provisional,
            "score_status": "PROVISIONAL" if is_provisional else "FINALIZED_PENDING_APPROVAL",
            "weightage_version": weight_version,
            "overall_claimed_score": round(total_raw_api, 2),
            "overall_verified_score": round(total_verified_api, 2),
            "category_scores": category_scores,
            "detailed_breakdown": detailed_breakdown,
            "unresolved_exceptions_count": len(unresolved_exceptions),
        }

        state.api_score = api_score_payload
        state.workflow_status = "SCORED"

        state.add_audit_entry(
            node_name="APICalculationAgent",
            action="API_CALCULATION_COMPLETE",
            details={
                "is_provisional": is_provisional,
                "overall_verified_score": round(total_verified_api, 2),
                "unresolved_exceptions": len(unresolved_exceptions),
                "weightage_version": weight_version,
            },
            status="WARNING" if is_provisional else "SUCCESS",
        )
        return state
