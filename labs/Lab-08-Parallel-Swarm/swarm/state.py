"""Workflow State Management for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from typing import Dict, Optional
import uuid

from models.schemas import WorkflowState


def create_initial_state(
    faculty_id: str = "FAC001",
    faculty_name: str = "Dr. Ananya Sharma",
    appraisal_period: str = "2025-2026",
    requester_role: str = "Faculty_Member",
    consent: Optional[Dict[str, bool]] = None,
    test_injection: Optional[str] = None,
    run_id: Optional[str] = None,
    scenario_name: Optional[str] = None,
) -> WorkflowState:
    """Create an isolated, pristine workflow state for a faculty appraisal run.

    Args:
        faculty_id: Target faculty ID.
        faculty_name: Name of faculty member.
        appraisal_period: Evaluation academic year.
        requester_role: Role of the initiating user.
        consent: Explicit consent map for data source extraction.
        test_injection: Optional injection flag ('MISSING_EVIDENCE', 'MISMATCHED_EVIDENCE', 'FAIL_COLLECTOR').
        run_id: Unique execution identifier. If None, auto-generated.
        scenario_name: Optional human-readable scenario name for traceability.

    Returns:
        Fresh WorkflowState instance.
    """
    default_consent = {
        "research": True,
        "teaching_learning": True,
        "administrative": True,
    }
    if consent is not None:
        default_consent.update(consent)

    resolved_run_id = run_id if run_id is not None else f"SWARM_RUN_{uuid.uuid4().hex[:8].upper()}"

    return WorkflowState(
        run_id=resolved_run_id,
        faculty_id=faculty_id,
        faculty_name=faculty_name,
        appraisal_period=appraisal_period,
        requester_role=requester_role,
        scenario_name=scenario_name,
        test_injection=test_injection,
        consent=default_consent,
    )
