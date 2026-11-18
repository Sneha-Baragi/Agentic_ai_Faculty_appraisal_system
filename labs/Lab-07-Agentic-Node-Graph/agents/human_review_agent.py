"""Node 7: HoD / Dean / IQAC Human Review Agent (Group H).

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from models.schemas import ReviewDecision, WorkflowState

# Authorized reviewer governance roles
AUTHORIZED_REVIEWER_ROLES: Set[str] = {"HoD", "Dean", "IQAC"}


class HumanReviewAgent:
    """Manages human governance approval gates for faculty appraisal reports."""

    def __init__(
        self,
        reviewer_id: str = "REV_HOD_001",
        reviewer_role: str = "HoD",
        simulated_decision: str = "APPROVED",
        comments: str = "Faculty appraisal report reviewed and verified against institutional criteria.",
    ) -> None:
        """Initialize human review agent with credentials and decision parameters."""
        self.reviewer_id = reviewer_id
        self.reviewer_role = reviewer_role
        self.simulated_decision = simulated_decision
        self.comments = comments

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Execute the human review gate with strict role and exception guardrails.

        Guardrails:
        - Role enforcement: Only 'HoD', 'Dean', and 'IQAC' are authorized.
        - Unresolved exceptions guard: Cannot grant final approval if unresolved evidence exceptions remain.
        - Audit trail: All approvals, rejections, and unauthorized attempts are logged.
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

        # Guardrail 2: Evidence Exception Enforcement
        # If unresolved evidence exceptions exist, final approval cannot be granted
        unresolved_count = len(state.evidence_exceptions)
        if self.simulated_decision == "APPROVED" and unresolved_count > 0:
            error_msg = (
                f"Approval blocked: {unresolved_count} unresolved evidence exception(s) exist. "
                "Final score and report cannot be approved until all claims are verified."
            )
            state.publication_status = "BLOCKED"
            state.workflow_status = "BLOCKED_ON_EXCEPTIONS"
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
                action="APPROVAL_BLOCKED_UNRESOLVED_EXCEPTIONS",
                details={
                    "unresolved_exceptions_count": unresolved_count,
                    "decision": "NEEDS_CORRECTION",
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

        if self.simulated_decision == "APPROVED":
            state.workflow_status = "APPROVED"
            if state.report:
                state.report["status"] = "APPROVED"
                state.report["review_decision"] = decision_dict
            state.add_audit_entry(
                node_name="HumanReviewAgent",
                action="REPORT_APPROVED",
                details={
                    "reviewer_id": self.reviewer_id,
                    "reviewer_role": self.reviewer_role,
                    "comments": self.comments,
                },
                status="SUCCESS",
            )

        elif self.simulated_decision == "REJECTED":
            state.workflow_status = "REJECTED"
            state.publication_status = "BLOCKED"
            if state.report:
                state.report["status"] = "REJECTED"
                state.report["review_decision"] = decision_dict
            state.add_audit_entry(
                node_name="HumanReviewAgent",
                action="REPORT_REJECTED",
                details={
                    "reviewer_id": self.reviewer_id,
                    "reviewer_role": self.reviewer_role,
                    "reason": self.comments,
                },
                status="WARNING",
            )

        else:  # NEEDS_CORRECTION
            state.workflow_status = "CORRECTION_REQUIRED"
            state.publication_status = "BLOCKED"
            if state.report:
                state.report["status"] = "NEEDS_CORRECTION"
                state.report["review_decision"] = decision_dict
            state.add_audit_entry(
                node_name="HumanReviewAgent",
                action="CORRECTION_REQUESTED",
                details={
                    "reviewer_id": self.reviewer_id,
                    "reviewer_role": self.reviewer_role,
                    "comments": self.comments,
                },
                status="WARNING",
            )

        return state
