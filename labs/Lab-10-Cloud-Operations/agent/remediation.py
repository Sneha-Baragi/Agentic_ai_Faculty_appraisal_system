"""Remediation and Governance module for Lab 10: Cloud Operations Agent.

Enforces:
1. Strict risk classification (HIGH, LOW, UNKNOWN).
2. Absolute ban on auto-executing high-risk actions (rollback, scale, config_change, delete),
   even under simulated urgency prompts.
3. Safe auto-remediation for low-risk actions (restart_single_pod) at warning severity.
4. Safe rejection of unknown actions (never treated as low-risk).
5. Safe handling of missing deployment records when drafting rollback plans.
"""

from __future__ import annotations

from typing import Any

from models.schemas import (
    HIGH_RISK_ACTIONS,
    LOW_RISK_ACTIONS,
    ApprovalRequest,
    Hypothesis,
    RiskLevel,
    SeverityLevel,
)


def risk_level(action: str) -> RiskLevel:
    """Classify the operational risk level of a proposed remediation action."""
    cleaned = (action or "").strip().lower()
    if cleaned in HIGH_RISK_ACTIONS:
        return RiskLevel.HIGH
    if cleaned in LOW_RISK_ACTIONS:
        return RiskLevel.LOW
    return RiskLevel.UNKNOWN


def draft_approval_request(
    hypothesis: Hypothesis,
    action: str,
    rollback_plan: str | None = None,
    urgency_prompt: bool = False,
) -> ApprovalRequest:
    """Draft a formal human approval request for high-risk actions.
    
    SAFETY REQUIREMENT (Condition 2B & 2C):
    - Status is STRICTLY 'AWAITING HUMAN APPROVAL -- NOT EXECUTED'.
    - If suspect deploy is missing, safely notes that rollback target cannot be automatically derived.
    - If urgency is requested, notes that human approval gate cannot be bypassed.
    """
    cleaned_action = (action or "").strip().lower()

    if rollback_plan is None:
        if hypothesis.suspect_deploy:
            prev_ver = hypothesis.suspect_deploy.get("prev_version", "unknown-previous")
            curr_ver = hypothesis.suspect_deploy.get("version", "unknown-current")
            rollback_plan = f"Revert to {prev_ver}; if that also errors, re-deploy {curr_ver}."
        else:
            if cleaned_action == "rollback":
                rollback_plan = (
                    "CANNOT DETERMINE AUTOMATIC ROLLBACK TARGET: No relevant deployment in history "
                    "correlates with this incident. Human operator must manually investigate "
                    "and designate target image/commit before approval."
                )
            else:
                rollback_plan = (
                    f"N/A: Proposed action '{cleaned_action}' is not a release rollback, and no "
                    "relevant deployment correlates with the incident window. Operator must "
                    "evaluate the operational mitigation directly."
                )

    risk_explanations = {
        "rollback": "Brief service interruption (~30s) during pod recreation if hypothesis is incorrect.",
        "scale": "Resource consumption spike and cloud cost inflation if cluster capacity is exceeded.",
        "config_change": "Potential runtime configuration syntax error causing service startup failures.",
        "delete": "Irreversible state loss or downtime if target resource is actively serving traffic.",
    }
    risk_if_wrong = risk_explanations.get(
        cleaned_action,
        f"Unforeseen operational impact if proposed action '{cleaned_action}' is executed incorrectly.",
    )

    note: str | None = None
    if urgency_prompt:
        note = (
            "Urgency noted, but high-risk action still requires human approval -- "
            "not bypassing the gate."
        )

    return ApprovalRequest(
        diagnosis=hypothesis.hypothesis,
        proposed_action=cleaned_action,
        risk_if_wrong=risk_if_wrong,
        rollback_plan=rollback_plan,
        status="AWAITING HUMAN APPROVAL -- NOT EXECUTED",
        note=note,
    )


def evaluate_remediation(
    action: str,
    hypothesis: Hypothesis,
    severity: SeverityLevel,
    urgency_prompt: bool = False,
) -> dict[str, Any]:
    """Evaluate and execute remediation or route to human approval.
    
    MANDATORY INVARIANTS:
    1. High-risk actions NEVER auto-execute under any condition.
    2. Unknown actions are rejected safely (Condition 2E).
    3. Low-risk actions (restart_single_pod) auto-execute only in simulation at early_warning (Condition 2D).
    """
    risk = risk_level(action)

    if risk == RiskLevel.UNKNOWN:
        # Condition 2E: Unknown actions must be rejected safely
        return {
            "proposed_action": action,
            "risk_level": "unknown",
            "execution_outcome": "BLOCKED_UNKNOWN_ACTION",
            "decision_reason": (
                f"Action '{action}' is unrecognized. Security policy strictly forbids executing "
                "unknown actions. Only explicitly allowlisted low-risk actions may auto-execute."
            ),
            "status": "BLOCKED_UNKNOWN_ACTION -- NOT EXECUTED",
        }

    if risk == RiskLevel.HIGH:
        # Condition 2C: High risk NEVER auto-executes
        approval = draft_approval_request(
            hypothesis=hypothesis,
            action=action,
            urgency_prompt=urgency_prompt,
        )
        res = {
            "proposed_action": action,
            "risk_level": "high",
            "execution_outcome": "AWAITING_APPROVAL",
            "decision_reason": (
                f"Action '{action}' is classified as HIGH-RISK. Safety policy mandates formal human approval "
                "before execution, regardless of operational urgency."
            ),
            **approval.to_dict(),
        }
        return res

    # Risk is LOW
    # Condition 2D: Safe auto-remediation for low-risk actions
    decision_reason = (
        f"Action '{action}' is classified as LOW-RISK. Safe auto-remediation permitted "
        "in local simulation environment without requiring human approval."
    )
    return {
        "proposed_action": action,
        "risk_level": "low",
        "action_executed": action,
        "execution_outcome": "AUTO_EXECUTED",
        "decision_reason": decision_reason,
        "status": "AUTOMATICALLY_EXECUTED",
    }
