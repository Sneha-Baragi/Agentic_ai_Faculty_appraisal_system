"""Data Models and State Schemas for Lab 7 Agentic Node Graph.

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Activity:
    """Represents a claimed faculty appraisal activity."""

    activity_id: str
    faculty_id: str
    title: str
    category: str  # 'Research', 'Teaching_Learning', 'Administrative'
    sub_category: str
    period: str
    description: str
    claimed_points: float
    source_system: str
    evidence_ref: str
    evidence_status: str = "CLAIMED"  # CLAIMED, VERIFIED, MISSING_EVIDENCE, MISMATCHED_EVIDENCE, INCOMPLETE
    validation_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert activity to dictionary."""
        return asdict(self)


@dataclass
class EvidenceRecord:
    """Represents a registered supporting evidence document."""

    evidence_id: str
    faculty_id: str
    category: str
    document_name: str
    issuing_authority: str
    issue_date: str
    verified_checksum: str
    status: str = "VALID"

    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence to dictionary."""
        return asdict(self)


@dataclass
class ReviewDecision:
    """Represents human governance decision by HoD, Dean, or IQAC."""

    reviewer_id: str
    reviewer_role: str  # 'HoD', 'Dean', 'IQAC'
    decision: str  # 'APPROVED', 'REJECTED', 'NEEDS_CORRECTION'
    comments: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision to dictionary."""
        return asdict(self)


@dataclass
class WorkflowState:
    """Shared workflow state model passed across graph nodes."""

    run_id: str
    faculty_id: str
    faculty_name: str
    appraisal_period: str
    requester_role: str
    scenario_name: Optional[str] = None
    consent: Dict[str, bool] = field(
        default_factory=lambda: {
            "research": True,
            "teaching_learning": True,
            "administrative": True,
        }
    )
    research_activities: List[Dict[str, Any]] = field(default_factory=list)
    teaching_activities: List[Dict[str, Any]] = field(default_factory=list)
    administrative_activities: List[Dict[str, Any]] = field(default_factory=list)
    include_missing_evidence: bool = False
    include_mismatched_evidence: bool = False
    collection_status: Dict[str, Any] = field(default_factory=dict)
    validated_activities: List[Dict[str, Any]] = field(default_factory=list)
    evidence_exceptions: List[Dict[str, Any]] = field(default_factory=list)
    api_score: Dict[str, Any] = field(default_factory=dict)
    report: Dict[str, Any] = field(default_factory=dict)
    review_decision: Optional[Dict[str, Any]] = None
    publication_status: str = "NOT_PUBLISHED"  # NOT_PUBLISHED, APPROVED_AND_PUBLISHED, BLOCKED
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
    workflow_status: str = "INITIALIZED"  # INITIALIZED, COLLECTING, VALIDATED, SCORED, REPORT_GENERATED, AWAITING_APPROVAL, APPROVED, REJECTED, TERMINATED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dictionary."""
        return asdict(self)

    def add_audit_entry(
        self,
        node_name: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        status: str = "SUCCESS",
    ) -> Dict[str, Any]:
        """Append an immutable audit trail entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node_name": node_name,
            "action": action,
            "status": status,
            "details": details or {},
        }
        self.audit_log.append(entry)
        return entry
