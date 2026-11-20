"""Data models and schemas for Lab 10: Cloud Operations Agent.

Defines strongly typed structures for log entries, deployment history,
metrics, diagnostic hypotheses, risk classifications, approval requests,
and immutable decision traces.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    HIGH = "high"
    LOW = "low"
    UNKNOWN = "unknown"


class SeverityLevel(str, Enum):
    DOWN = "down"
    DEGRADED = "degraded"
    EARLY_WARNING = "early_warning"
    INVALID_METRICS = "invalid_metrics"


HIGH_RISK_ACTIONS: set[str] = {"rollback", "scale", "config_change", "delete"}
LOW_RISK_ACTIONS: set[str] = {"open_ticket", "notify", "restart_single_pod"}


@dataclass
class LogEntry:
    ts: str
    level: str  # "INFO", "WARN", "ERROR"
    msg: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeployRecord:
    ts: str
    service: str
    version: str
    prev_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricsPayload:
    baseline_error_rate: float | int | None
    current_error_rate: float | int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SeverityResult:
    severity: SeverityLevel
    ratio: float | None
    calculation_details: str
    is_valid: bool
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["severity"] = self.severity.value
        return res


@dataclass
class Hypothesis:
    hypothesis: str
    suspect_deploy: dict[str, Any] | None
    affected_path: str
    timing_correlation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApprovalRequest:
    diagnosis: str
    proposed_action: str
    risk_if_wrong: str
    rollback_plan: str
    status: str = "AWAITING HUMAN APPROVAL -- NOT EXECUTED"
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionTrace:
    scenario_id: str
    incident_start: str | None
    severity: str
    severity_calculation: str
    affected_path: str
    root_cause_hypothesis: str
    proposed_action: str
    risk_level: str
    execution_outcome: str  # "AWAITING_APPROVAL", "AUTO_EXECUTED", "BLOCKED_UNKNOWN", "REJECTED_INVALID"
    decision_reason: str
    action_executed: str | None = None
    approval_request: dict[str, Any] | None = None
    urgency_noted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IncidentReport:
    scenario_id: str
    title: str
    description: str
    observed_logs_count: int
    observed_deploys_count: int
    metrics: dict[str, Any]
    incident_start: str | None
    severity: str
    hypothesis: str
    proposed_action: str
    risk_level: str
    decision_trace: DecisionTrace
    approval_request: dict[str, Any] | None
    action_executed: str | None
    generated_at: str
    simulation_disclaimer: str = (
        "Simulation Disclaimer: This execution is a safe local simulation. "
        "No real cloud infrastructure, APIs, shell processes, or cloud mutations were executed."
    )

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["decision_trace"] = self.decision_trace.to_dict()
        return res
