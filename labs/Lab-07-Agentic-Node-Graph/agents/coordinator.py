"""Node 0: apniLeap AURA Coordinator.

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System

Central graph orchestrator coordinating:
- Profile intake and faculty consent verification
- True parallel collection across Research, Teaching, and Administrative agents
- Joining collected data and routing to Evidence Validation
- API scoring with weightage enforcement
- Structured appraisal report generation
- Routing to HoD / Dean / IQAC human review gate
- Publishing dashboard and report ONLY after human approval
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.administrative_agent import AdministrativeAgent
from agents.api_calculation_agent import APICalculationAgent
from agents.evidence_validation_agent import EvidenceValidationAgent
from agents.human_review_agent import HumanReviewAgent
from agents.report_generation_agent import ReportGenerationAgent
from agents.research_agent import ResearchAgent
from agents.teaching_agent import TeachingAgent
from graph.graph_engine import GraphEngine
from graph.node import Node
from models.schemas import WorkflowState


class AURACoordinator:
    """Central graph orchestrator for the Faculty Appraisal Management System."""

    def __init__(
        self,
        human_reviewer_id: str = "REV_HOD_001",
        human_reviewer_role: str = "HoD",
        human_review_decision: str = "APPROVED",
        human_review_comments: str = "Faculty appraisal report approved after verification.",
    ) -> None:
        """Initialize coordinator with default human reviewer settings."""
        self.research_agent = ResearchAgent()
        self.teaching_agent = TeachingAgent()
        self.administrative_agent = AdministrativeAgent()
        self.validation_agent = EvidenceValidationAgent()
        self.scoring_agent = APICalculationAgent()
        self.report_agent = ReportGenerationAgent()
        self.human_review_agent = HumanReviewAgent(
            reviewer_id=human_reviewer_id,
            reviewer_role=human_reviewer_role,
            simulated_decision=human_review_decision,
            comments=human_review_comments,
        )

    # -------------------------------------------------------------------------
    # STAGE 1: Profile & Consent Intake Gate
    # -------------------------------------------------------------------------

    def intake_gate(self, state: WorkflowState) -> WorkflowState:
        """Verify identity, role permissions, and faculty consent prior to collection.

        Guardrails:
        - Must have valid faculty_id.
        - Must check consent dictionary.
        - If all consent flags are False, terminate workflow immediately.
        """
        state.add_audit_entry(
            node_name="AURACoordinator:IntakeGate",
            action="PROFILE_INTAKE_VERIFIED",
            details={
                "faculty_id": state.faculty_id,
                "faculty_name": state.faculty_name,
                "appraisal_period": state.appraisal_period,
                "requester_role": state.requester_role,
                "consent": state.consent,
            },
            status="SUCCESS",
        )

        # Check if consent is completely denied
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

    # -------------------------------------------------------------------------
    # STAGE 7: Dashboard Update & Publication Gate
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # GRAPH BUILDER
    # -------------------------------------------------------------------------

    def build_graph(self) -> GraphEngine:
        """Construct the hybrid sequential and parallel agent node graph."""
        graph = GraphEngine(name="FacultyAppraisalOrchestrator")

        # Node 1: Profile & Consent Intake
        graph.add_node(
            Node(
                name="profile_intake",
                handler=self.intake_gate,
                description="Profile intake and consent verification gate",
            )
        )

        # Nodes 2, 3, 4: Parallel Collection Agents (Group: parallel_collection)
        graph.add_node(
            Node(
                name="research_collection",
                handler=self.research_agent.execute,
                description="Group A: Research Data Collection Agent",
                is_parallel_group_member=True,
                parallel_group_name="parallel_collection",
            )
        )
        graph.add_node(
            Node(
                name="teaching_collection",
                handler=self.teaching_agent.execute,
                description="Group B: Teaching-Learning Data Collection Agent",
                is_parallel_group_member=True,
                parallel_group_name="parallel_collection",
            )
        )
        graph.add_node(
            Node(
                name="administrative_collection",
                handler=self.administrative_agent.execute,
                description="Group C: Administrative Data Collection Agent",
                is_parallel_group_member=True,
                parallel_group_name="parallel_collection",
            )
        )

        # Node 5: Parallel Collection Dispatcher/Join Node
        def _parallel_collection_join(state: WorkflowState) -> WorkflowState:
            # If workflow was terminated at intake (e.g. all consent denied), skip collection
            if state.workflow_status == "TERMINATED":
                return state
            return graph.execute_parallel_group("parallel_collection", state)

        graph.add_node(
            Node(
                name="parallel_collection_join",
                handler=_parallel_collection_join,
                description="Starts and joins the 3 collection agents in parallel via ThreadPoolExecutor",
            )
        )

        # Node 6: Evidence Validation Agent
        graph.add_node(
            Node(
                name="evidence_validation",
                handler=self.validation_agent.execute,
                description="Group D: Evidence Validation Agent",
            )
        )

        # Node 7: API Calculation Agent
        graph.add_node(
            Node(
                name="api_calculation",
                handler=self.scoring_agent.execute,
                description="Group E: API Calculation Agent",
            )
        )

        # Node 8: Report Generation Agent
        graph.add_node(
            Node(
                name="report_generation",
                handler=self.report_agent.execute,
                description="Group F: Report Generation Agent",
            )
        )

        # Node 9: Human Review Approval Gate
        graph.add_node(
            Node(
                name="human_review",
                handler=self.human_review_agent.execute,
                description="Group H: HoD / Dean / IQAC Human Review Agent",
            )
        )

        # Node 10: Dashboard Update & Publication Gate
        graph.add_node(
            Node(
                name="dashboard_publication",
                handler=self.publish_gate,
                description="Publish dashboard and appraisal report after approval",
            )
        )

        # ---------------------------------------------------------------------
        # CONNECT EDGES & TRANSITIONS
        # ---------------------------------------------------------------------
        graph.add_transition(
            from_node="profile_intake",
            to_node="parallel_collection_join",
            condition=lambda state: state.workflow_status != "TERMINATED",
            name="consent_granted",
        )
        graph.add_transition(
            from_node="parallel_collection_join",
            to_node="evidence_validation",
            name="collection_complete",
        )
        graph.add_transition(
            from_node="evidence_validation",
            to_node="api_calculation",
            name="validation_complete",
        )
        graph.add_transition(
            from_node="api_calculation",
            to_node="report_generation",
            name="scoring_complete",
        )
        graph.add_transition(
            from_node="report_generation",
            to_node="human_review",
            name="report_generated",
        )
        graph.add_transition(
            from_node="human_review",
            to_node="dashboard_publication",
            name="review_complete",
        )

        return graph

    def run_workflow(self, state: WorkflowState) -> WorkflowState:
        """Execute the complete appraisal workflow graph on the given state."""
        graph = self.build_graph()
        return graph.run(initial_node_name="profile_intake", state=state)
