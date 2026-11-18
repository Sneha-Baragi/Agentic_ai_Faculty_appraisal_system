"""Workflow State Management.

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
"""

import uuid
from typing import Dict, Optional
from models.schemas import WorkflowState


def create_initial_state(
    faculty_id: str = "FAC001",
    faculty_name: str = "Dr. Ananya Sharma",
    appraisal_period: str = "2025-2026",
    requester_role: str = "Faculty_Member",
    consent: Optional[Dict[str, bool]] = None,
    include_missing_evidence: bool = False,
    include_mismatched_evidence: bool = False,
    run_id: Optional[str] = None,
    scenario_name: Optional[str] = None,
) -> WorkflowState:
    """Create a pristine, isolated workflow state for a faculty appraisal run.

    Args:
        faculty_id: Unique faculty ID.
        faculty_name: Name of faculty member.
        appraisal_period: Evaluation academic year.
        requester_role: Role of the initiating user.
        consent: Explicit consent map for data source collection.
        include_missing_evidence: Whether to inject test missing evidence claim.
        include_mismatched_evidence: Whether to inject test mismatched evidence claim.
        run_id: Optional custom run identifier. If None, generated automatically.
        scenario_name: Optional scenario or workflow identifier for traceability.

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

    resolved_run_id = run_id if run_id is not None else f"RUN_{uuid.uuid4().hex[:8].upper()}"

    return WorkflowState(
        run_id=resolved_run_id,
        faculty_id=faculty_id,
        faculty_name=faculty_name,
        appraisal_period=appraisal_period,
        requester_role=requester_role,
        scenario_name=scenario_name,
        consent=default_consent,
        include_missing_evidence=include_missing_evidence,
        include_mismatched_evidence=include_mismatched_evidence,
    )
