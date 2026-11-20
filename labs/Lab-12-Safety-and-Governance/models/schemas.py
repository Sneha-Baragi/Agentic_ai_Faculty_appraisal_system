"""Data schemas and domain models for Lab 12: Safety, Security & Governance.

Pure Python standard library only (no third-party dependencies).
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """User roles within the academic appraisal governance system."""

    FACULTY = "faculty"
    HOD = "hod"
    DEAN = "dean"
    ADMIN = "admin"

    @classmethod
    def from_str(cls, value: str) -> Role:
        """Parse role from string case-insensitively."""
        normalized = value.strip().lower()
        for r in cls:
            if r.value == normalized:
                return r
        raise ValueError(f"Invalid Role: {value}. Allowed: {[r.value for r in cls]}")


class Action(str, Enum):
    """Governed actions within the Faculty Appraisal domain."""

    SUBMIT_APPRAISAL = "submit_appraisal"
    VIEW_OWN_APPRAISAL = "view_own_appraisal"
    REVIEW_APPRAISAL = "review_appraisal"
    APPROVE_APPRAISAL = "approve_appraisal"
    OVERRIDE_SCORE = "override_score"
    EXPORT_REPORT = "export_report"
    MANAGE_USERS = "manage_users"

    @classmethod
    def from_str(cls, value: str) -> Action:
        """Parse action from string case-insensitively."""
        normalized = value.strip().lower()
        for a in cls:
            if a.value == normalized:
                return a
        raise ValueError(f"Invalid Action: {value}. Allowed: {[a.value for a in cls]}")


class ThreatLevel(str, Enum):
    """Threat severity levels evaluated by safety guardrails."""

    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


class PIIType(str, Enum):
    """Categories of Personally Identifiable Information detected & redacted."""

    EMAIL = "email"
    PHONE = "phone"
    AADHAAR_SSN = "aadhaar_ssn"
    SALARY = "salary"
    STUDENT_ID = "student_id"


# ---------------------------------------------------------------------------
# Domain Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SecurityContext:
    """Security context representing the authenticated actor making a request."""

    actor_id: str
    role: Role | str
    ip_address: str = "127.0.0.1"
    session_id: str = "sess-default"

    def __post_init__(self) -> None:
        if isinstance(self.role, str):
            self.role = Role.from_str(self.role)

    def to_dict(self) -> dict[str, Any]:
        """Serialize security context to dictionary."""
        return {
            "actor_id": self.actor_id,
            "role": self.role.value if isinstance(self.role, Role) else str(self.role),
            "ip_address": self.ip_address,
            "session_id": self.session_id,
        }


@dataclass
class GuardrailResult:
    """Result of prompt injection and guardrail policy evaluation."""

    allowed: bool
    threat_level: ThreatLevel | str
    violations: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.threat_level, str):
            self.threat_level = ThreatLevel(self.threat_level)

    def to_dict(self) -> dict[str, Any]:
        """Serialize guardrail evaluation result to dictionary."""
        return {
            "allowed": self.allowed,
            "threat_level": (
                self.threat_level.value
                if isinstance(self.threat_level, ThreatLevel)
                else str(self.threat_level)
            ),
            "violations": list(self.violations),
            "details": dict(self.details),
        }


@dataclass
class PIIRedactionResult:
    """Outcome of PII detection and masking execution."""

    original_text: str
    redacted_text: str
    redactions_count: int
    detected_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize PII redaction outcome to dictionary."""
        return {
            "original_text": self.original_text,
            "redacted_text": self.redacted_text,
            "redactions_count": self.redactions_count,
            "detected_types": list(self.detected_types),
        }


@dataclass
class AuditEntry:
    """Tamper-evident cryptographically chained audit record."""

    sequence_number: int
    timestamp: str
    actor_id: str
    role: str
    action: str
    status: str
    payload_hash: str
    prev_hash: str
    record_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize audit entry to dictionary."""
        return asdict(self)


@dataclass
class AppraisalSubmission:
    """Academic appraisal submission payload."""

    faculty_id: str
    faculty_name: str
    department: str
    academic_year: str
    claims_text: str
    self_appraisal_score: float = 0.0
    teaching_hours: int = 0
    publications_count: int = 0
    research_grants_inr: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize appraisal submission to dictionary."""
        return asdict(self)


@dataclass
class GovernanceReport:
    """Comprehensive end-to-end governance pipeline execution report."""

    request_id: str
    timestamp: str
    security_context: SecurityContext
    action: Action | str
    status: str  # "APPROVED", "BLOCKED", "REJECTED"
    rbac_allowed: bool
    rbac_reason: str
    guardrail_result: GuardrailResult | None = None
    pii_result: PIIRedactionResult | None = None
    execution_result: dict[str, Any] = field(default_factory=dict)
    output_guardrail_passed: bool = True
    audit_entry: AuditEntry | None = None
    pipeline_duration_ms: float = 0.0
    disclaimer: str = (
        "SIMULATION ONLY: This safety and governance report was generated "
        "by an isolated deterministic agentic governance pipeline."
    )

    def __post_init__(self) -> None:
        if isinstance(self.action, str):
            try:
                self.action = Action.from_str(self.action)
            except ValueError:
                pass

    def to_dict(self) -> dict[str, Any]:
        """Serialize governance report to dictionary."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "security_context": self.security_context.to_dict(),
            "action": self.action.value if isinstance(self.action, Action) else str(self.action),
            "status": self.status,
            "rbac_allowed": self.rbac_allowed,
            "rbac_reason": self.rbac_reason,
            "guardrail_result": self.guardrail_result.to_dict() if self.guardrail_result else None,
            "pii_result": self.pii_result.to_dict() if self.pii_result else None,
            "execution_result": dict(self.execution_result),
            "output_guardrail_passed": self.output_guardrail_passed,
            "audit_entry": self.audit_entry.to_dict() if self.audit_entry else None,
            "pipeline_duration_ms": self.pipeline_duration_ms,
            "disclaimer": self.disclaimer,
        }
