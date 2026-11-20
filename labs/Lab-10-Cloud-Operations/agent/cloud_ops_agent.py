"""Cloud Operations Agent Master Orchestrator for Lab 10.

Implements the Observe -> Reason -> Act workflow:
1. Observe: Ingest deployment logs, deployment history, and error metrics.
2. Reason: Identify incident timing, classify severity, correlate recent releases, assess risk.
3. Act: Route high-risk actions to human approval gate; permit safe auto-remediation for low-risk actions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.audit import create_decision_trace, redact_data, redact_sensitive_text
from agent.diagnostics import (
    classify_severity,
    correlate_with_recent_changes,
    find_incident_start,
)
from agent.remediation import (
    draft_approval_request,
    evaluate_remediation,
    risk_level,
)
from models.schemas import (
    DeployRecord,
    IncidentReport,
    LogEntry,
    MetricsPayload,
    RiskLevel,
    SeverityLevel,
)


class CloudOperationsAgent:
    """Autonomous Cloud Operations Agent for Incident Diagnostics and Remediation Gating."""

    def __init__(self, fixtures_path: str | Path | None = None) -> None:
        if fixtures_path is None:
            fixtures_path = (
                Path(__file__).resolve().parent.parent / "data" / "incident_fixtures.json"
            )
        self.fixtures_path = Path(fixtures_path)
        self._fixtures: dict[str, Any] = {}
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        if self.fixtures_path.exists():
            with open(self.fixtures_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._fixtures = data.get("scenarios", {})

    def get_scenario(self, scenario_id: str) -> dict[str, Any]:
        """Fetch scenario data by scenario ID."""
        if scenario_id not in self._fixtures:
            raise KeyError(f"Scenario '{scenario_id}' not found in fixtures.")
        return self._fixtures[scenario_id]

    def list_scenarios(self) -> list[str]:
        """List all available scenario IDs."""
        return list(self._fixtures.keys())

    def diagnose_and_propose(
        self,
        logs: list[dict[str, Any] | LogEntry] | None,
        deploys: list[dict[str, Any] | DeployRecord] | None,
        metrics: dict[str, Any] | MetricsPayload | None,
        proposed_action: str = "rollback",
        urgency_prompt: bool = False,
    ) -> dict[str, Any]:
        """Official reference pipeline method.
        
        Observe -> Reason -> Act, ending in a drafted human-approval request.
        The agent NEVER auto-executes a high-risk remediation action, even
        under a simulated urgency prompt.
        """
        # Step 1: Severity classification with safety validation
        sev_result = classify_severity(metrics)
        incident_start = find_incident_start(logs)

        # Condition 2A: Explicit handling of invalid metrics
        if not sev_result.is_valid:
            return {
                "severity": sev_result.severity.value,
                "incident_start": incident_start,
                "status": "REJECTED_INVALID_METRICS",
                "error": sev_result.error_message,
                "calculation_details": sev_result.calculation_details,
            }

        severity = sev_result.severity.value

        # Step 2: Root-cause correlation
        hypothesis = correlate_with_recent_changes(logs, deploys, incident_start)

        # Step 3: Risk assessment and execution gating
        remediation_outcome = evaluate_remediation(
            action=proposed_action,
            hypothesis=hypothesis,
            severity=sev_result.severity,
            urgency_prompt=urgency_prompt,
        )

        risk = remediation_outcome.get("risk_level", "unknown")

        # Step 4: Act formatting
        if risk == "high":
            # Hard assert: action_executed must NEVER appear in high-risk output
            result = {
                "severity": severity,
                "incident_start": incident_start,
                **remediation_outcome,
            }
            assert "action_executed" not in result, (
                f"SAFETY VIOLATION: High-risk action '{proposed_action}' must never auto-execute!"
            )
            return redact_data(result)

        if risk == "low":
            result = {
                "severity": severity,
                "incident_start": incident_start,
                **remediation_outcome,
            }
            return redact_data(result)

        # Unknown action rejection
        result = {
            "severity": severity,
            "incident_start": incident_start,
            **remediation_outcome,
        }
        return redact_data(result)

    def run_incident(
        self,
        scenario_id: str,
        scenario_data: dict[str, Any] | None = None,
        proposed_action: str | None = None,
        urgency_prompt: bool = False,
    ) -> IncidentReport:
        """Run complete incident investigation and produce a structured IncidentReport."""
        if scenario_data is None:
            scenario_data = self.get_scenario(scenario_id)

        title = scenario_data.get("title", scenario_id)
        description = scenario_data.get("description", "")
        logs = scenario_data.get("logs", [])
        deploys = scenario_data.get("deploy_history", [])
        metrics = scenario_data.get("metrics", {})
        action = proposed_action or scenario_data.get("proposed_action", "rollback")

        # Execute diagnosis and governance proposal
        diag_result = self.diagnose_and_propose(
            logs=logs,
            deploys=deploys,
            metrics=metrics,
            proposed_action=action,
            urgency_prompt=urgency_prompt,
        )

        sev_result = classify_severity(metrics)
        incident_start = diag_result.get("incident_start")
        hyp = correlate_with_recent_changes(logs, deploys, incident_start)
        risk = risk_level(action).value

        # Build decision trace
        outcome = diag_result.get("execution_outcome", "UNKNOWN")
        reason = diag_result.get("decision_reason", "No decision reason recorded.")
        action_executed = diag_result.get("action_executed")

        approval_request_dict = None
        if risk == "high":
            approval_request_dict = {
                "diagnosis": diag_result.get("diagnosis"),
                "proposed_action": diag_result.get("proposed_action"),
                "risk_if_wrong": diag_result.get("risk_if_wrong"),
                "rollback_plan": diag_result.get("rollback_plan"),
                "status": diag_result.get("status"),
                "note": diag_result.get("note"),
            }

        decision_trace = create_decision_trace(
            scenario_id=scenario_id,
            incident_start=incident_start,
            severity=sev_result.severity.value,
            severity_calculation=sev_result.calculation_details,
            affected_path=hyp.affected_path,
            root_cause_hypothesis=hyp.hypothesis,
            proposed_action=action,
            risk_level=risk,
            execution_outcome=outcome,
            decision_reason=reason,
            action_executed=action_executed,
            approval_request=approval_request_dict,
            urgency_noted=urgency_prompt,
        )

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return IncidentReport(
            scenario_id=scenario_id,
            title=title,
            description=description,
            observed_logs_count=len(logs),
            observed_deploys_count=len(deploys),
            metrics=redact_data(metrics),
            incident_start=incident_start,
            severity=sev_result.severity.value,
            hypothesis=redact_sensitive_text(hyp.hypothesis),
            proposed_action=action,
            risk_level=risk,
            decision_trace=decision_trace,
            approval_request=approval_request_dict,
            action_executed=action_executed,
            generated_at=now_iso,
        )

    def format_markdown_report(self, report: IncidentReport) -> str:
        """Format an IncidentReport into an auditable GitHub Flavored Markdown document."""
        lines: list[str] = []
        lines.append(f"# Cloud Operations Incident Report: {report.title}")
        lines.append(f"\n*Scenario ID:* `{report.scenario_id}` | *Generated at:* `{report.generated_at}`")
        lines.append("\n---\n")

        # 1. Executive Summary & Status
        lines.append("## 1. Executive Incident Summary\n")
        lines.append(f"- **Severity Level:** `{report.severity.upper()}`")
        lines.append(f"- **Incident Start Time:** `{report.incident_start or 'None (No ERROR log)'}`")
        lines.append(f"- **Affected Service / Code Path:** `{report.decision_trace.affected_path}`")
        lines.append(f"- **Proposed Action:** `{report.proposed_action}` (Risk Level: `{report.risk_level.upper()}`)")

        if report.action_executed:
            lines.append(f"- **Action Status:** `AUTOMATICALLY EXECUTED (Local Simulation)` -> `{report.action_executed}`")
        elif report.approval_request:
            lines.append(f"- **Action Status:** `{report.approval_request.get('status')}`")
        else:
            lines.append(f"- **Action Status:** `{report.decision_trace.execution_outcome}`")

        lines.append("\n---\n")

        # 2. Observed Telemetry
        lines.append("## 2. Observed Telemetry & Root-Cause Diagnosis\n")
        lines.append(f"- **Observed Logs Count:** {report.observed_logs_count} entries analyzed")
        lines.append(f"- **Deployment History Count:** {report.observed_deploys_count} entries analyzed")
        lines.append(f"- **Metrics Snapshot:** Baseline Error Rate: `{report.metrics.get('baseline_error_rate')}%`, Current Error Rate: `{report.metrics.get('current_error_rate')}%`")
        lines.append(f"- **Severity Derivation:** {report.decision_trace.severity_calculation}")
        lines.append(f"\n**Root-Cause Hypothesis:**\n> {report.hypothesis}\n")
        lines.append("---\n")

        # 3. Governance Approval or Execution Gate
        lines.append("## 3. Governance Approval & Action Gate\n")
        if report.approval_request:
            req = report.approval_request
            lines.append("### Drafted Human Approval Request (High-Risk Action Gate)\n")
            lines.append(f"- **Status:** `{req.get('status')}`")
            lines.append(f"- **Diagnosis:** {req.get('diagnosis')}")
            lines.append(f"- **Proposed Action:** `{req.get('proposed_action')}`")
            lines.append(f"- **Risk If Wrong:** {req.get('risk_if_wrong')}")
            lines.append(f"- **Rollback Plan:** {req.get('rollback_plan')}")
            if req.get("note"):
                lines.append(f"- **Operator Note:** {req.get('note')}")
            lines.append("\n> [!IMPORTANT]\n> High-risk actions NEVER auto-execute. Manual human approval is required before execution.")
        elif report.action_executed:
            lines.append("### Safe Auto-Remediation (Low-Risk Action)\n")
            lines.append(f"- **Action Executed:** `{report.action_executed}` (Simulation Only)")
            lines.append(f"- **Decision Rationale:** {report.decision_trace.decision_reason}")
            lines.append("\n> [!NOTE]\n> Action classified as LOW-RISK at early_warning severity; auto-execution permitted per Assignment 2 policy.")
        else:
            lines.append("### Action Blocked\n")
            lines.append(f"- **Outcome:** `{report.decision_trace.execution_outcome}`")
            lines.append(f"- **Rationale:** {report.decision_trace.decision_reason}")

        lines.append("\n---\n")

        # 4. Audit Decision Trace
        trace = report.decision_trace
        lines.append("## 4. Immutable Decision Trace\n")
        lines.append(f"- **Scenario:** `{trace.scenario_id}`")
        lines.append(f"- **Execution Outcome:** `{trace.execution_outcome}`")
        lines.append(f"- **Decision Reason:** {trace.decision_reason}")
        lines.append(f"- **Urgency Noted:** `{trace.urgency_noted}` (Urgency cannot bypass approval gate)")
        lines.append(f"\n> [!NOTE]\n> {report.simulation_disclaimer}\n")

        return "\n".join(lines)

    def save_report(
        self, report: IncidentReport, output_dir: str | Path | None = None
    ) -> tuple[Path, Path]:
        """Save incident report as markdown and JSON artifacts in reports directory."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "reports"
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in report.scenario_id).strip("_")

        md_file = out_path / f"incident_{slug}_{timestamp}.md"
        json_file = out_path / f"incident_{slug}_{timestamp}.json"

        md_content = self.format_markdown_report(report)
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        return md_file, json_file
