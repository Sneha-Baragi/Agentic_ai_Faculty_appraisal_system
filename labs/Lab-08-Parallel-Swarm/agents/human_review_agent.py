"""Human Review Specialist Agent for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from models.schemas import ReviewDecision, WorkflowState

AUTHORIZED_REVIEWER_ROLES: Set[str] = {"HoD", "Dean", "IQAC"}

# Defined mock governance authorities permitted to issue appraisal policy overrides
# NOTE: This is an educational mock simulation of institutional governance policies for Lab 8.
# It does NOT represent production-grade access control, cryptographic attestation, or SSO auth.
MOCK_AUTHORIZED_OVERRIDE_AUTHORITIES: Set[str] = {
    "Academic_Council",
    "Governing_Body",
    "Dean_Academic_Affairs",
    "Vice_Chancellor",
}

# Recognized mock institutional statutory policy references
MOCK_RECOGNIZED_POLICY_REFS: Set[str] = {
    "STATUTE_POLICY_4.2_SABBATICAL_EXEMPTION",
    "STATUTE_POLICY_7B_EXEMPTION",
    "EXEMPTION_POLICY_7",
    "POLICY_ACADEMIC_LEAVE_2025",
}


class HumanReviewAgent:
    """Manages human governance approval gates for faculty appraisal reports."""

    def __init__(
        self,
        reviewer_id: str = "REV_HOD_001",
        reviewer_role: str = "HoD",
        simulated_decision: str = "APPROVED",
        comments: str = "Faculty appraisal report reviewed and verified against institutional criteria.",
        institutional_override: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize human review agent with reviewer credentials, decision, and optional override."""
        self.reviewer_id = reviewer_id
        self.reviewer_role = reviewer_role
        self.simulated_decision = simulated_decision
        self.comments = comments
        self.institutional_override = institutional_override

    @classmethod
    def validate_institutional_override(cls, override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate caller-supplied institutional override against mock governance rules.

        Educational Note:
        This validates against a mock set of authorized academic bodies and policy references
        configured for Lab 8 demonstration. It is an educational simulation of institutional
        governance gates and does NOT claim production-grade security or cryptographic attestation.

        Validation rules:
        1. Must be a non-empty dictionary.
        2. Must explicitly set override_authorized=True.
        3. 'authorized_by' must be a recognized mock institutional authority.
        4. 'policy_ref' must be a recognized mock institutional policy/statute reference.
        5. 'reason' must be provided as a non-empty string explaining the exemption.
        """
        if not override or not isinstance(override, dict):
            return {"is_valid": False, "reason": "No override dictionary provided"}

        if not override.get("override_authorized", False):
            return {"is_valid": False, "reason": "override_authorized flag is not True"}

        authorizing_body = str(override.get("authorized_by", "")).strip()
        if authorizing_body not in MOCK_AUTHORIZED_OVERRIDE_AUTHORITIES:
            return {
                "is_valid": False,
                "reason": (
                    f"Unrecognized or unauthorized overriding authority: '{authorizing_body}'. "
                    f"Recognized mock authorities: {sorted(list(MOCK_AUTHORIZED_OVERRIDE_AUTHORITIES))}"
                ),
            }

        policy_ref = str(override.get("policy_ref", "")).strip()
        if policy_ref not in MOCK_RECOGNIZED_POLICY_REFS and not (policy_ref.startswith("STATUTE_") or policy_ref.startswith("POLICY_")):
            return {
                "is_valid": False,
                "reason": (
                    f"Unrecognized institutional policy reference: '{policy_ref}'. "
                    f"Recognized mock policies: {sorted(list(MOCK_RECOGNIZED_POLICY_REFS))}"
                ),
            }

        reason = str(override.get("reason", "")).strip()
        if not reason:
            return {"is_valid": False, "reason": "Missing required justification/reason in override"}

        return {"is_valid": True, "reason": "Valid institutional override"}

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Execute the human review gate with strict role and exception guardrails.

        Guardrails:
        - Role enforcement: Only 'HoD', 'Dean', and 'IQAC' are authorized.
        - Unresolved exceptions guard: Cannot grant final approval if unresolved evidence exceptions remain
          or if collection was incomplete.
        - Consent limitations guard: Cannot grant ordinary final approval if appraisal is consent-limited
          unless an explicit, authorized institutional policy or review override is validated.
        - Audit trail: All approvals, rejections, corrections, and unauthorized attempts are logged.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Guardrail 1: Role Authorization Check
        if self.reviewer_role not in AUTHORIZED_REVIEWER_ROLES:
            error_msg = (
                f"Unauthorized reviewer role: '{self.reviewer_role}'. "
                f"Only {sorted(list(AUTHORIZED_REVIEWER_ROLES))} are authorized to review appraisals."
            )
            state.publication_status = "BLOCKED"
            state.workflow_status = "REJECTED"
            state.add_audit_entry(
                node_name="HumanReviewAgent",
                action="UNAUTHORIZED_REVIEW_ATTEMPT",
                details={
                    "reviewer_id": self.reviewer_id,
                    "reviewer_role": self.reviewer_role,
                    "error": error_msg,
                },
                status="FAILED",
            )
            return state

        # Guardrail 2: Evidence Exception, Incomplete Collection & Consent Limitations Enforcement
        unresolved_count = len(state.evidence_exceptions)
        merge_status = state.merge_result.get("status") if state.merge_result else "SUCCESS"
        api_data = state.api_score or {}
        is_consent_limited = api_data.get("is_consent_limited", False) or (merge_status == "CONSENT_LIMITED")
        skipped_cats = api_data.get("skipped_categories", [])

        # Check and validate caller-supplied institutional override
        effective_override = self.institutional_override or getattr(state, "institutional_override", None)
        override_validation = self.validate_institutional_override(effective_override)
        has_authorized_override = override_validation["is_valid"]

        if effective_override is not None and not has_authorized_override:
            state.add_audit_entry(
                node_name="HumanReviewAgent",
                action="INVALID_OVERRIDE_REJECTED",
                details={
                    "attempted_override": effective_override,
                    "validation_failure": override_validation["reason"],
                },
                status="FAILED",
            )

        if self.simulated_decision == "APPROVED":
            block_reasons = []
            if unresolved_count > 0:
                block_reasons.append(f"{unresolved_count} unresolved evidence exception(s) exist")
            if merge_status in ("PARTIAL", "FAILED"):
                block_reasons.append(f"collection was incomplete (merge status: {merge_status})")
            if is_consent_limited and not has_authorized_override:
                cat_list = ", ".join(skipped_cats) if skipped_cats else "one or more required categories"
                detail_msg = (
                    f"appraisal is consent-limited (category '{cat_list}' skipped due to withheld consent; "
                    f"override rejected: {override_validation['reason']})"
                    if effective_override is not None
                    else f"appraisal is consent-limited (category '{cat_list}' skipped due to withheld consent; "
                    "no authorized institutional override provided)"
                )
                block_reasons.append(detail_msg)

            if block_reasons:
                error_msg = (
                    f"Approval blocked: {'; '.join(block_reasons)}. "
                    "Final score and report cannot be approved without all required categories collected, "
                    "unless an explicit authorized institutional policy override is provided."
                )
                state.publication_status = "BLOCKED"
                is_purely_consent = (
                    is_consent_limited
                    and not has_authorized_override
                    and unresolved_count == 0
                    and merge_status not in ("PARTIAL", "FAILED")
                )
                state.workflow_status = "BLOCKED_ON_CONSENT" if is_purely_consent else "BLOCKED_ON_EXCEPTIONS"
                decision_payload = ReviewDecision(
                    reviewer_id=self.reviewer_id,
                    reviewer_role=self.reviewer_role,
                    decision="NEEDS_CORRECTION",
                    comments=error_msg,
                    timestamp=timestamp,
                ).to_dict()
                state.review_decision = decision_payload

                state.add_audit_entry(
                    node_name="HumanReviewAgent",
                    action="APPROVAL_BLOCKED_CONSENT_LIMITATION" if is_purely_consent else "APPROVAL_BLOCKED_UNRESOLVED_EXCEPTIONS",
                    details={
                        "unresolved_exceptions_count": unresolved_count,
                        "merge_status": merge_status,
                        "is_consent_limited": is_consent_limited,
                        "has_authorized_override": has_authorized_override,
                        "override_validation": override_validation,
                        "decision": "NEEDS_CORRECTION",
                        "comments": error_msg,
                    },
                    status="WARNING",
                )
                return state

        # Create review decision record
        decision_obj = ReviewDecision(
            reviewer_id=self.reviewer_id,
            reviewer_role=self.reviewer_role,
            decision=self.simulated_decision,
            comments=self.comments,
            timestamp=timestamp,
        )
        decision_dict = decision_obj.to_dict()
        state.review_decision = decision_dict

        if state.report:
            state.report["review_decision"] = decision_dict

        if self.simulated_decision == "APPROVED":
            state.workflow_status = "APPROVED"
            state.add_audit_entry(
                node_name="HumanReviewAgent",
                action="APPRAISAL_APPROVED_WITH_OVERRIDE" if (is_consent_limited and has_authorized_override) else "APPRAISAL_APPROVED",
                details={
                    "reviewer_id": self.reviewer_id,
                    "reviewer_role": self.reviewer_role,
                    "decision": "APPROVED",
                    "override_applied": bool(is_consent_limited and has_authorized_override),
                    "override_details": effective_override if (is_consent_limited and has_authorized_override) else None,
                },
                status="SUCCESS",
            )
        elif self.simulated_decision == "REJECTED":
            state.workflow_status = "REJECTED"
            state.publication_status = "BLOCKED"
            state.add_audit_entry(
                node_name="HumanReviewAgent",
                action="APPRAISAL_REJECTED",
                details={
                    "reviewer_id": self.reviewer_id,
                    "reviewer_role": self.reviewer_role,
                    "decision": "REJECTED",
                    "comments": self.comments,
                },
                status="WARNING",
            )
        else:
            state.workflow_status = "NEEDS_CORRECTION"
            state.publication_status = "BLOCKED"
            state.add_audit_entry(
                node_name="HumanReviewAgent",
                action="APPRAISAL_NEEDS_CORRECTION",
                details={
                    "reviewer_id": self.reviewer_id,
                    "reviewer_role": self.reviewer_role,
                    "decision": "NEEDS_CORRECTION",
                    "comments": self.comments,
                },
                status="WARNING",
            )

        return state
