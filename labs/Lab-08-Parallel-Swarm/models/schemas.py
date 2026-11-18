"""Data Models and State Schemas for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Activity:
    """Represents a faculty appraisal activity claim collected by a specialist agent."""

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
    collector_role: str  # Originating specialist agent
    evidence_status: str = "CLAIMED"  # CLAIMED, VERIFIED, MISSING_EVIDENCE, MISMATCHED_EVIDENCE, INCOMPLETE
    validation_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert activity to dictionary."""
        return asdict(self)


@dataclass
class CollectorResult:
    """Represents the isolated output of a specialist collector agent in the swarm."""

    collector_role: str
    category: str
    status: str  # 'SUCCESS', 'FAILED', 'SKIPPED'
    start_time: str
    end_time: str
    duration_ms: float
    activities: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert collector result to dictionary."""
        return asdict(self)


@dataclass
class MergeResult:
    """Represents the outcome of the synchronized merge stage."""

    status: str  # 'SUCCESS', 'PARTIAL', 'FAILED'
    total_activities: int
    duplicates_detected: List[Dict[str, Any]] = field(default_factory=list)
    conflicts_detected: List[Dict[str, Any]] = field(default_factory=list)
    failed_collectors: List[str] = field(default_factory=list)
    skipped_collectors: List[str] = field(default_factory=list)
    merged_activities: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert merge result to dictionary."""
        return asdict(self)


@dataclass
class EvidenceRecord:
    """Represents an official institutional evidence document."""

    evidence_id: str
    faculty_id: str
    category: str
    document_name: str
    issuing_authority: str
    issue_date: str
    verified_checksum: str
    status: str = "VALID"

    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence record to dictionary."""
        return asdict(self)


@dataclass
class ReviewDecision:
    """Represents a formal human review decision by an authorized institutional authority."""

    reviewer_id: str
    reviewer_role: str  # 'HoD', 'Dean', 'IQAC'
    decision: str  # 'APPROVED', 'REJECTED', 'NEEDS_CORRECTION'
    comments: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert review decision to dictionary."""
        return asdict(self)


@dataclass
class WorkflowState:
    """Central isolated workflow state passed across the parallel swarm and downstream pipeline."""

    run_id: str
    faculty_id: str
    faculty_name: str
    appraisal_period: str
    requester_role: str
    scenario_name: Optional[str] = None
    test_injection: Optional[str] = None  # E.g. 'MISSING_EVIDENCE', 'MISMATCHED_EVIDENCE', 'FAIL_COLLECTOR'
    consent: Dict[str, bool] = field(
        default_factory=lambda: {
            "research": True,
            "teaching_learning": True,
            "administrative": True,
        }
    )
    # Swarm outputs kept strictly isolated per specialist collector before merge
    swarm_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    merge_result: Optional[Dict[str, Any]] = None
    merged_activities: List[Dict[str, Any]] = field(default_factory=list)
    validated_activities: List[Dict[str, Any]] = field(default_factory=list)
    evidence_exceptions: List[Dict[str, Any]] = field(default_factory=list)
    api_score: Dict[str, Any] = field(default_factory=dict)
    report: Dict[str, Any] = field(default_factory=dict)
    review_decision: Optional[Dict[str, Any]] = None
    institutional_override: Optional[Dict[str, Any]] = None
    publication_status: str = "NOT_PUBLISHED"  # NOT_PUBLISHED, APPROVED_AND_PUBLISHED, BLOCKED
    workflow_status: str = "INITIALIZED"  # INITIALIZED, COLLECTING, MERGED, VALIDATED, SCORED, REPORT_GENERATED, AWAITING_APPROVAL, APPROVED, REJECTED, TERMINATED, BLOCKED_ON_EXCEPTIONS, BLOCKED_ON_CONSENT, INCOMPLETE_COLLECTION
    audit_log: List[Dict[str, Any]] = field(default_factory=list)

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
        """Append an immutable audit entry with ISO 8601 UTC timestamp."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node_name": node_name,
            "action": action,
            "status": status,
            "details": details or {},
        }
        self.audit_log.append(entry)
        return entry
