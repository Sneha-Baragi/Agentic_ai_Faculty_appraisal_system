"""Diagnostics module for Lab 10: Cloud Operations Agent.

Implements:
1. Severity classification with explicit validation (rejects zero/negative/missing baselines).
2. Incident start time detection from chronological log entries.
3. Correlation of error streams with deployment history and code path extraction.
"""

from __future__ import annotations

from typing import Any

from models.schemas import (
    DeployRecord,
    Hypothesis,
    LogEntry,
    MetricsPayload,
    SeverityLevel,
    SeverityResult,
)


def classify_severity(metrics: dict[str, Any] | MetricsPayload | None) -> SeverityResult:
    """Classify incident severity based on error rate ratio and threshold checks.
    
    SAFETY REQUIREMENT (Condition 2A):
    Zero, negative, missing, and non-numeric metrics are explicitly rejected with
    SeverityLevel.INVALID_METRICS. Zero baseline is NEVER silently replaced.
    """
    if metrics is None:
        return SeverityResult(
            severity=SeverityLevel.INVALID_METRICS,
            ratio=None,
            calculation_details="Metrics payload is missing (None).",
            is_valid=False,
            error_message="Missing metrics payload: cannot compute severity without baseline and current rates.",
        )

    if isinstance(metrics, MetricsPayload):
        raw_baseline = metrics.baseline_error_rate
        raw_current = metrics.current_error_rate
    elif isinstance(metrics, dict):
        raw_baseline = metrics.get("baseline_error_rate")
        raw_current = metrics.get("current_error_rate")
    else:
        return SeverityResult(
            severity=SeverityLevel.INVALID_METRICS,
            ratio=None,
            calculation_details=f"Unexpected metrics type: {type(metrics).__name__}",
            is_valid=False,
            error_message="Invalid metrics payload structure: expected dictionary or MetricsPayload.",
        )

    # Validate numeric baseline
    if raw_baseline is None or not isinstance(raw_baseline, (int, float)):
        return SeverityResult(
            severity=SeverityLevel.INVALID_METRICS,
            ratio=None,
            calculation_details="Baseline error rate is non-numeric or None.",
            is_valid=False,
            error_message="Invalid baseline error rate: must be a positive numeric value.",
        )

    # Strictly reject zero or negative baseline (No silent 0.001 replacements!)
    if raw_baseline <= 0:
        return SeverityResult(
            severity=SeverityLevel.INVALID_METRICS,
            ratio=None,
            calculation_details=f"Baseline error rate is non-positive: {raw_baseline} <= 0",
            is_valid=False,
            error_message=(
                f"Invalid baseline error rate ({raw_baseline}): baseline must be strictly positive (> 0.0) "
                "to calculate error rate ratios safely without division-by-zero."
            ),
        )

    # Validate numeric current rate
    if raw_current is None or not isinstance(raw_current, (int, float)):
        return SeverityResult(
            severity=SeverityLevel.INVALID_METRICS,
            ratio=None,
            calculation_details="Current error rate is non-numeric or None.",
            is_valid=False,
            error_message="Invalid current error rate: must be a non-negative numeric value.",
        )

    if raw_current < 0:
        return SeverityResult(
            severity=SeverityLevel.INVALID_METRICS,
            ratio=None,
            calculation_details=f"Current error rate is negative: {raw_current} < 0",
            is_valid=False,
            error_message=f"Invalid current error rate ({raw_current}): error rates cannot be negative.",
        )

    baseline = float(raw_baseline)
    current = float(raw_current)
    ratio = round(current / baseline, 2)

    if current > 50.0:
        return SeverityResult(
            severity=SeverityLevel.DOWN,
            ratio=ratio,
            calculation_details=f"Current error rate ({current}%) > 50.0% threshold -> DOWN (ratio: {ratio}x)",
            is_valid=True,
        )

    if ratio >= 2.0:
        return SeverityResult(
            severity=SeverityLevel.DEGRADED,
            ratio=ratio,
            calculation_details=f"Error rate ratio ({ratio}x) >= 2.0 threshold -> DEGRADED ({current}% vs baseline {baseline}%)",
            is_valid=True,
        )

    return SeverityResult(
        severity=SeverityLevel.EARLY_WARNING,
        ratio=ratio,
        calculation_details=f"Error rate ratio ({ratio}x) < 2.0 threshold -> EARLY_WARNING ({current}% vs baseline {baseline}%)",
        is_valid=True,
    )


def find_incident_start(logs: list[dict[str, Any] | LogEntry] | None) -> str | None:
    """Find the timestamp of the first ERROR log entry in chronological logs."""
    if not logs:
        return None

    for entry in logs:
        level = entry.level if isinstance(entry, LogEntry) else entry.get("level")
        ts = entry.ts if isinstance(entry, LogEntry) else entry.get("ts")
        if level == "ERROR":
            return ts

    return None


def _is_deploy_relevant_to_incident(
    deploy: dict[str, Any],
    affected_path: str,
    combined_errors: str,
    combined_all_logs: str,
) -> bool:
    """Determine whether a deployment is genuinely relevant to the observed incident.
    
    A deployment is NOT selected merely because its timestamp precedes the incident start.
    It must have component, service, or domain affinity with the observed errors.
    """
    svc = (deploy.get("service") or "").strip().lower()
    if not svc:
        return False

    # 1. Official Payments Scenario: payments-service matches refund endpoint regression
    if affected_path == "refund" and svc.startswith("payments"):
        return True

    # 2. Service explicitly referenced in error logs or incident telemetry
    if svc in combined_errors or svc in combined_all_logs:
        return True

    # 3. Component domain affinity
    # For database pool exhaustion, only DB/pool services correlate; unrelated services (e.g. data-exporter) do not.
    if affected_path == "database_pool":
        return any(k in svc for k in ["database", "db-pool", "connection-pool", "postgres", "mysql"])

    if affected_path == "cache_layer":
        return any(k in svc for k in ["redis", "cache", "memcached"])

    if affected_path == "authentication":
        return any(k in svc for k in ["auth", "session", "identity", "token"])

    if affected_path in svc:
        return True

    return False


def correlate_with_recent_changes(
    logs: list[dict[str, Any] | LogEntry] | None,
    deploys: list[dict[str, Any] | DeployRecord] | None,
    incident_start: str | None,
) -> Hypothesis:
    """Correlate error stream with deployment history and extract affected code path.
    
    SAFETY REQUIREMENT (Condition 2B & Defect Correction):
    Correlates deployments using both timestamp AND relevant service/component information.
    Does not select a deployment merely because its timestamp preceded the incident.
    If deployment history is missing or non-correlating, returns suspect_deploy=None.
    """
    raw_logs = logs or []
    raw_deploys = deploys or []

    error_msgs: list[str] = []
    all_log_msgs: list[str] = []
    for l in raw_logs:
        lvl = l.level if isinstance(l, LogEntry) else l.get("level")
        msg = l.msg if isinstance(l, LogEntry) else l.get("msg", "")
        all_log_msgs.append(msg)
        if lvl == "ERROR":
            error_msgs.append(msg)

    combined_errors = " ".join(error_msgs).lower()
    combined_all_logs = " ".join(all_log_msgs).lower()

    # Determine affected code path
    if "refund" in combined_errors:
        affected_path = "refund"
    elif any(k in combined_errors for k in ["connectionpool", "connection pool", "database pool", "pool timeout"]):
        affected_path = "database_pool"
    elif "redis" in combined_errors:
        affected_path = "cache_layer"
    elif any(k in combined_errors for k in ["auth", "session", "token"]):
        affected_path = "authentication"
    elif error_msgs:
        affected_path = "general_application_path"
    else:
        # Check warning logs if no errors
        warn_msgs = [
            (l.msg if isinstance(l, LogEntry) else l.get("msg", ""))
            for l in raw_logs
            if (l.level if isinstance(l, LogEntry) else l.get("level")) == "WARN"
        ]
        warn_text = " ".join(warn_msgs).lower()
        if "memory" in warn_text or "pod" in warn_text:
            affected_path = "worker_pod_runtime"
        else:
            affected_path = "none_detected"

    if not incident_start:
        return Hypothesis(
            hypothesis="No ERROR logs detected in the incident window. System operating at baseline or warning status.",
            suspect_deploy=None,
            affected_path=affected_path,
            timing_correlation="NO_ERRORS_RECORDED",
        )

    # Convert deploy records to dict for inspection
    formatted_deploys: list[dict[str, Any]] = []
    for d in raw_deploys:
        if isinstance(d, DeployRecord):
            formatted_deploys.append(d.to_dict())
        elif isinstance(d, dict):
            formatted_deploys.append(d)

    # Search for matching deploy preceding incident_start that is genuinely relevant
    matching_deploy: dict[str, Any] | None = None
    for d in formatted_deploys:
        dep_ts = d.get("ts", "")
        if dep_ts and dep_ts <= incident_start:
            if _is_deploy_relevant_to_incident(d, affected_path, combined_errors, combined_all_logs):
                matching_deploy = d
                break

    if matching_deploy:
        svc = matching_deploy.get("service", "unknown-service")
        ver = matching_deploy.get("version", "unknown-version")
        dep_ts = matching_deploy.get("ts", "unknown-time")
        hyp = (
            f"Error rate rose starting {incident_start}, shortly after the "
            f"{dep_ts} deploy of {svc} {ver}. Errors are "
            f"concentrated in the {affected_path} code path, consistent with a "
            "regression introduced in that release."
        )
        return Hypothesis(
            hypothesis=hyp,
            suspect_deploy=matching_deploy,
            affected_path=affected_path,
            timing_correlation=f"DEPLOY_PRECEDES_INCIDENT ({dep_ts} < {incident_start})",
        )

    # Missing or non-correlating deployment history
    unrelated_note = ""
    if formatted_deploys:
        unrelated_svcs = [
            f"{d.get('service')} {d.get('version', '')}".strip()
            for d in formatted_deploys
            if d.get("service")
        ]
        if unrelated_svcs:
            unrelated_note = (
                f" Existing deployments in history ({', '.join(unrelated_svcs)}) do not correlate "
                "with the affected component."
            )

    return Hypothesis(
        hypothesis=(
            f"Error rate rose starting {incident_start} in the {affected_path} code path. "
            f"No relevant deployment correlates with the incident window.{unrelated_note} "
            "A safe rollback target cannot be determined from deployment history; manual operator diagnosis required."
        ),
        suspect_deploy=None,
        affected_path=affected_path,
        timing_correlation="NO_CORRELATING_DEPLOY",
    )
