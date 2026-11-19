"""Audit and Sensitive Data Redaction module for Lab 10: Cloud Operations Agent.

Implements:
1. Pattern-based redaction of sensitive credentials, tokens, passwords, and connection strings.
2. Construction of auditable, immutable decision traces.
"""

from __future__ import annotations

import re
from typing import Any

from models.schemas import DecisionTrace


SENSITIVE_PATTERNS = [
    re.compile(r"password\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"secret\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"token\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE),
    re.compile(r"(postgres|mysql|mongodb|redis)://[^:]+:([^@]+)@", re.IGNORECASE),
]


def redact_sensitive_text(text: str) -> str:
    """Redact sensitive passwords, tokens, API keys, and database credentials from strings."""
    if not isinstance(text, str):
        return text

    redacted = text
    # Special handling for DB URI with password
    redacted = re.sub(
        r"((?:postgres|mysql|mongodb|redis)://[^:]+:)([^@]+)(@)",
        r"\1[REDACTED]\3",
        redacted,
        flags=re.IGNORECASE,
    )
    # Generic token and password patterns
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)

    return redacted


def redact_data(val: Any) -> Any:
    """Recursively redact sensitive data from strings, dictionaries, and lists."""
    if isinstance(val, str):
        return redact_sensitive_text(val)
    elif isinstance(val, dict):
        cleaned: dict[str, Any] = {}
        for k, v in val.items():
            if any(s in k.lower() for s in ["password", "secret", "token", "apikey", "api_key"]):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_data(v)
        return cleaned
    elif isinstance(val, list):
        return [redact_data(item) for item in val]
    return val


def create_decision_trace(
    scenario_id: str,
    incident_start: str | None,
    severity: str,
    severity_calculation: str,
    affected_path: str,
    root_cause_hypothesis: str,
    proposed_action: str,
    risk_level: str,
    execution_outcome: str,
    decision_reason: str,
    action_executed: str | None = None,
    approval_request: dict[str, Any] | None = None,
    urgency_noted: bool = False,
) -> DecisionTrace:
    """Create a structured, auditable decision trace for an incident response."""
    return DecisionTrace(
        scenario_id=scenario_id,
        incident_start=incident_start,
        severity=severity,
        severity_calculation=severity_calculation,
        affected_path=affected_path,
        root_cause_hypothesis=redact_sensitive_text(root_cause_hypothesis),
        proposed_action=proposed_action,
        risk_level=risk_level,
        execution_outcome=execution_outcome,
        decision_reason=decision_reason,
        action_executed=action_executed,
        approval_request=redact_data(approval_request) if approval_request else None,
        urgency_noted=urgency_noted,
    )
