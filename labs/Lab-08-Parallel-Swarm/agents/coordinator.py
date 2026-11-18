"""AURA Coordinator for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.administrative_agent import AdministrativeDataCollectionAgent
from agents.api_calculation_agent import APICalculationAgent
from agents.evidence_validation_agent import EvidenceValidationAgent
from agents.human_review_agent import HumanReviewAgent
from agents.report_generation_agent import ReportGenerationAgent
from agents.research_agent import ResearchDataCollectionAgent
from agents.teaching_agent import TeachingDataCollectionAgent
from models.schemas import WorkflowState
from swarm.executor import SwarmExecutor
from swarm.merge import SwarmMerge


class AURACoordinator:
    """Central orchestrator managing intake, parallel swarm dispatch, merge, and downstream pipeline."""

    def __init__(
        self,
        human_reviewer_id: str = "REV_HOD_001",
        human_reviewer_role: str = "HoD",
        human_review_decision: str = "APPROVED",
        human_review_comments: str = "Faculty appraisal verified against institutional benchmarks.",
        institutional_override: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize coordinator with specialist agents and reviewer settings."""
        self.research_agent = ResearchDataCollectionAgent()
        self.teaching_agent = TeachingDataCollectionAgent()
        self.admin_agent = AdministrativeDataCollectionAgent()
        self.validation_agent = EvidenceValidationAgent()
        self.scoring_agent = APICalculationAgent()
        self.report_agent = ReportGenerationAgent()
        self.human_review_agent = HumanReviewAgent(
            reviewer_id=human_reviewer_id,
            reviewer_role=human_reviewer_role,
            simulated_decision=human_review_decision,
            comments=human_review_comments,
            institutional_override=institutional_override,
        )
        self.swarm_executor = SwarmExecutor(max_workers=3)
        self.swarm_merge = SwarmMerge()

    def intake_gate(self, state: WorkflowState) -> WorkflowState:
        """Validate profile and faculty consent prior to swarm dispatch.

        If faculty denies consent for all categories, terminates workflow immediately.
        """
        state.add_audit_entry(
            node_name="AURACoordinator:IntakeGate",
            action="PROFILE_INTAKE_VERIFIED",
            details={
                "faculty_id": state.faculty_id,
                "faculty_name": state.faculty_name,
                "appraisal_period": state.appraisal_period,
                "consent": state.consent,
            },
            status="SUCCESS",
        )

        consent_flags = list(state.consent.values())
        if all(flag is False for flag in consent_flags):
            state.workflow_status = "TERMINATED"
            state.publication_status = "BLOCKED"
            state.add_audit_entry(
                node_name="AURACoordinator:IntakeGate",
                action="WORKFLOW_TERMINATED_ALL_CONSENT_DENIED",
                details={"reason": "Faculty denied consent for all appraisal categories."},
                status="FAILED",
            )
            return state

        state.workflow_status = "COLLECTING"
        return state

    def publish_gate(self, state: WorkflowState) -> WorkflowState:
        """Publish dashboard and report ONLY after human governance approval.

        Guardrails:
        - Never publish unapproved reports or scores.
        - Verify review decision is explicitly APPROVED.
        - If unapproved or exceptions remain, set publication_status = BLOCKED.
        """
        review = state.review_decision or {}
        decision = review.get("decision")

        if state.workflow_status == "APPROVED" and decision == "APPROVED":
            state.publication_status = "APPROVED_AND_PUBLISHED"
            state.workflow_status = "APPROVED_AND_PUBLISHED"
            if state.report:
                state.report["publication_status"] = "APPROVED_AND_PUBLISHED"
                state.report["published_at"] = datetime.now(timezone.utc).isoformat()

            state.add_audit_entry(
                node_name="AURACoordinator:PublishGate",
                action="APPRAISAL_PUBLISHED",
                details={
                    "report_id": state.report.get("report_id"),
                    "faculty_id": state.faculty_id,
                    "verified_api_score": state.api_score.get("overall_verified_score"),
                    "published_status": "APPROVED_AND_PUBLISHED",
                },
                status="SUCCESS",
            )
        else:
            state.publication_status = "BLOCKED"
            state.add_audit_entry(
                node_name="AURACoordinator:PublishGate",
                action="PUBLICATION_BLOCKED",
                details={
                    "workflow_status": state.workflow_status,
                    "review_decision": decision,
                    "reason": "Report lacks required human approval or unresolved exceptions remain.",
                },
                status="WARNING",
            )

        return state

    def run_workflow(self, state: WorkflowState) -> WorkflowState:
        """Run the complete hybrid parallel swarm appraisal workflow.

        Sequential lifecycle:
        1. Intake Gate & Consent Verification
        2. Parallel Swarm Collection (Research, Teaching, Administrative concurrent dispatch)
        3. Synchronized Merge & Conflict Detection
        4. Evidence Validation
        5. API Calculation
        6. Report Generation
        7. Human Review Gate
        8. Dashboard Publication Gate
        """
        # Step 1: Intake & Consent Gate
        state = self.intake_gate(state)
        if state.workflow_status == "TERMINATED":
            return state

        # Step 2: Parallel Swarm Collection
        collector_tasks = {
            "ResearchDataCollectionAgent": self.research_agent.execute,
            "TeachingDataCollectionAgent": self.teaching_agent.execute,
            "AdministrativeDataCollectionAgent": self.admin_agent.execute,
        }
        self.swarm_executor.execute_swarm(tasks=collector_tasks, state=state)

        # Step 3: Swarm Synchronization & Merge
        state = self.swarm_merge.merge(state)
        if state.merge_result and state.merge_result.get("status") == "FAILED":
            state.workflow_status = "FAILED"
            state.publication_status = "BLOCKED"
            return state

        # Step 4: Evidence Validation
        state = self.validation_agent.execute(state)

        # Step 5: API Calculation
        state = self.scoring_agent.execute(state)

        # Step 6: Report Generation
        state = self.report_agent.execute(state)

        # Step 7: Human Review Gate
        state = self.human_review_agent.execute(state)

        # Step 8: Dashboard Publication Gate
        state = self.publish_gate(state)

        return state
