#!/usr/bin/env python3
"""Lab 12: Safety, Security & Governance.

Interactive CLI runner demonstrating:
1. Guardrail policy enforcement
2. Prompt injection defense (jailbreak & adversarial blocking)
3. Sensitive PII redaction (phones, emails, Aadhaar/SSN, salary, student IDs)
4. Role boundaries & RBAC access governance (Faculty, HOD, Dean, Admin)
5. Cryptographic SHA-256 hash-chained audit ledger with tamper detection

Usage::

    python main.py                    # Run default governance scenarios
    python main.py --all              # Run all fixture scenarios
    python main.py --scenario <id>    # Run a specific scenario by id
    python main.py --tamper-demo      # Demonstrate audit ledger tamper detection
    python main.py --log-level DEBUG  # Enable verbose debug logs
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Ensure lab directory is on sys.path
_LAB_ROOT = Path(__file__).resolve().parent
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from agents.audit_ledger import AuditLedger  # noqa: E402
from agents.pii_redactor import PIIRedactor  # noqa: E402
from agents.prompt_guard import PromptGuard  # noqa: E402
from agents.rbac_enforcer import RBACEnforcer  # noqa: E402
from governance.governance_engine import GovernanceEngine  # noqa: E402
from models.schemas import (  # noqa: E402
    Action,
    GovernanceReport,
    Role,
    SecurityContext,
)

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with consistent formatting."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def load_fixtures(fixture_path: Path) -> list[dict[str, Any]]:
    """Load scenario fixtures from JSON file."""
    if not fixture_path.exists():
        logger.error("Fixture file not found: %s", fixture_path)
        sys.exit(1)
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_report_markdown(report: GovernanceReport) -> str:
    """Format a GovernanceReport into structured Markdown."""
    lines: list[str] = [
        f"# Governance & Safety Report: {report.request_id}",
        "",
        f"- **Timestamp**: `{report.timestamp}`",
        f"- **Actor**: `{report.security_context.actor_id}` ({report.security_context.role.value if isinstance(report.security_context.role, Role) else report.security_context.role})",
        f"- **Action**: `{report.action.value if isinstance(report.action, Action) else report.action}`",
        f"- **Verdict / Status**: **`{report.status}`**",
        f"- **Processing Time**: {report.pipeline_duration_ms:.2f} ms",
        "",
        "## Pipeline Stages Summary",
        "",
        f"1. **RBAC Authorization**: {'[PASSED]' if report.rbac_allowed else '[REJECTED]'}",
        f"   - Details: {report.rbac_reason}",
        "",
    ]

    if report.guardrail_result:
        lines.extend([
            f"2. **Prompt Injection Guardrails**: {'[PASSED]' if report.guardrail_result.allowed else '[BLOCKED]'}",
            f"   - Threat Level: `{report.guardrail_result.threat_level}`",
            f"   - Violations Count: {len(report.guardrail_result.violations)}",
        ])
        for v in report.guardrail_result.violations:
            lines.append(f"     - *{v}*")
        lines.append("")
    else:
        lines.append("2. **Prompt Injection Guardrails**: *[SKIPPED - Pre-empted by RBAC]*\n")

    if report.pii_result:
        lines.extend([
            f"3. **Sensitive PII Redaction**: [EXECUTED]",
            f"   - Redactions Applied: {report.pii_result.redactions_count}",
            f"   - Entities Detected: {', '.join(report.pii_result.detected_types) or 'None'}",
            f"   - Sanitized Text Snippet: `{report.pii_result.redacted_text[:160]}...`",
            "",
        ])
    else:
        lines.append("3. **Sensitive PII Redaction**: *[SKIPPED]*\n")

    if report.execution_result:
        lines.extend([
            "4. **Execution Result**:",
            "```json",
            json.dumps(report.execution_result, indent=2),
            "```",
            "",
        ])

    if report.audit_entry:
        lines.extend([
            "5. **Cryptographic Audit Block**:",
            f"   - Sequence Number: `#{report.audit_entry.sequence_number}`",
            f"   - Record Hash: `{report.audit_entry.record_hash}`",
            f"   - Previous Hash: `{report.audit_entry.prev_hash}`",
            f"   - Payload Hash: `{report.audit_entry.payload_hash}`",
            "",
        ])

    lines.extend([
        "---",
        f"> *{report.disclaimer}*",
        "",
    ])
    return "\n".join(lines)


def print_banner(title: str) -> None:
    """Print an eye-catching terminal header."""
    bar = "=" * 80
    print(f"\n{bar}\n  {title.upper()}\n{bar}")


def print_report_terminal(scenario: dict[str, Any], report: GovernanceReport) -> None:
    """Print a concise color-coded terminal view of scenario evaluation."""
    status_symbol = {
        "APPROVED": "[PASS - APPROVED]",
        "BLOCKED": "[SHIELD - BLOCKED]",
        "REJECTED": "[DENIED - REJECTED]",
    }.get(report.status, f"[{report.status}]")

    print(f"\nScenario:     {scenario.get('name', scenario.get('scenario_id'))}")
    print(f"Description:  {scenario.get('description', '')}")
    print(f"Actor / Role: {report.security_context.actor_id} ({report.security_context.role.value if isinstance(report.security_context.role, Role) else report.security_context.role})")
    print(f"Action:       {report.action.value if isinstance(report.action, Action) else report.action}")
    print(f"Verdict:      {status_symbol} in {report.pipeline_duration_ms:.2f}ms")
    print(f"RBAC:         {'Allowed' if report.rbac_allowed else 'Rejected: ' + report.rbac_reason}")

    if report.guardrail_result:
        gl = report.guardrail_result
        print(f"Guardrail:    {'Safe' if gl.allowed else 'Flagged: ' + gl.threat_level + ' (' + str(len(gl.violations)) + ' violations)'}")
        for v in gl.violations:
            print(f"              - {v}")

    if report.pii_result and report.pii_result.redactions_count > 0:
        print(f"PII Redactor: {report.pii_result.redactions_count} sensitive entities redacted ({', '.join(report.pii_result.detected_types)})")

    if report.audit_entry:
        print(f"Audit Block:  Seq #{report.audit_entry.sequence_number} | Hash: {report.audit_entry.record_hash[:16]}... (Chained)")
    print("-" * 80)


def save_reports_to_disk(report: GovernanceReport, scenario_id: str) -> tuple[Path, Path]:
    """Save JSON and Markdown artifacts to the reports/ directory."""
    reports_dir = _LAB_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / f"{scenario_id}_report.json"
    md_path = reports_dir / f"{scenario_id}_report.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(format_report_markdown(report))

    return json_path, md_path


def run_scenario(
    engine: GovernanceEngine,
    scenario: dict[str, Any],
    save_reports: bool = True,
) -> GovernanceReport:
    """Execute a single governance scenario fixture."""
    actor_data = scenario["actor"]
    context = SecurityContext(
        actor_id=actor_data["actor_id"],
        role=Role.from_str(actor_data["role"]),
        ip_address=actor_data.get("ip_address", "127.0.0.1"),
        session_id=actor_data.get("session_id", "sess-default"),
    )

    action = Action.from_str(scenario["action"])
    resource_owner = scenario.get("resource_owner_id")
    payload = scenario.get("payload", {})

    report = engine.process_request(
        context=context,
        action=action,
        payload=payload,
        resource_owner_id=resource_owner,
    )

    print_report_terminal(scenario, report)

    if save_reports:
        j_path, m_path = save_reports_to_disk(report, scenario["scenario_id"])
        logger.debug("Saved artifacts: %s, %s", j_path.name, m_path.name)

    return report


def run_tamper_demonstration(engine: GovernanceEngine) -> None:
    """Demonstrate cryptographic audit ledger integrity and tamper detection."""
    print_banner("Cryptographic Audit Ledger Tampering Demonstration")

    ledger = engine.audit_ledger
    print(f"Current Ledger Chain Length: {len(ledger)} entries")

    # Verify initial integrity
    is_valid, broken_idx, msg = ledger.verify_integrity()
    print(f"Step 1: Initial Integrity Verification -> Valid: {is_valid} ({msg})")
    assert is_valid, "Initial chain must be valid!"

    if len(ledger) < 2:
        # Append mock records to demonstrate chaining
        ledger.append_entry("FAC-01", "faculty", "submit_appraisal", "APPROVED", {"score": 85})
        ledger.append_entry("HOD-01", "hod", "review_appraisal", "APPROVED", {"rating": "A"})
        ledger.append_entry("DEAN-01", "dean", "approve_appraisal", "APPROVED", {"status": "FINAL"})

    target_index = 0
    original_entry = ledger.entries[target_index]
    original_status = original_entry.status
    print(f"\nStep 2: Tampering target entry #{original_entry.sequence_number} (index {target_index})...")
    print(f"        Original status: '{original_status}', Hash: {original_entry.record_hash}")

    # Maliciously modify the status without recomputing hashes
    ledger.tamper_entry(target_index, "status", "MALICIOUSLY_ALTERED")
    print(f"        Modified status: '{ledger.entries[target_index].status}' (Cryptographic hash NOT updated)")

    # Re-verify integrity
    is_valid, broken_idx, err_msg = ledger.verify_integrity()
    print(f"\nStep 3: Post-Tampering Verification:")
    print(f"        Integrity Intact: {is_valid}")
    print(f"        Flagged Index:    {broken_idx}")
    print(f"        Detection Alarm:  {err_msg}")

    # Restore legitimate entry to leave system intact
    ledger.tamper_entry(target_index, "status", original_status)
    restored_valid, _, restore_msg = ledger.verify_integrity()
    print(f"\nStep 4: Restored Original Entry -> Integrity Restored: {restored_valid} ({restore_msg})")


def main() -> None:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(
        description="Lab 12: Safety, Security & Governance for Faculty Appraisal System"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all realistic governance scenarios from fixtures",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Run a specific scenario by scenario_id",
    )
    parser.add_argument(
        "--tamper-demo",
        action="store_true",
        help="Run cryptographic audit ledger tampering detection demonstration",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save JSON and Markdown reports to reports/ directory",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging verbosity level",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    fixture_path = _LAB_ROOT / "data" / "governance_fixtures.json"
    scenarios = load_fixtures(fixture_path)
    engine = GovernanceEngine()
    save_reports = not args.no_save

    print_banner("Faculty Appraisal System: Safety, Security & Governance Agent (Lab 12)")
    print(f"Configured Roles:    {[r.value for r in Role]}")
    print(f"Governed Actions:    {[a.value for a in Action]}")
    print(f"Scenarios Loaded:    {len(scenarios)}")

    if args.tamper_demo:
        # Populate ledger with scenarios first then run demo
        for sc in scenarios[:3]:
            run_scenario(engine, sc, save_reports=False)
        run_tamper_demonstration(engine)
        return

    if args.scenario:
        matched = [s for s in scenarios if s.get("scenario_id") == args.scenario]
        if not matched:
            print(f"Error: Scenario '{args.scenario}' not found. Available: {[s['scenario_id'] for s in scenarios]}")
            sys.exit(1)
        run_scenario(engine, matched[0], save_reports=save_reports)
        return

    if args.all:
        for sc in scenarios:
            run_scenario(engine, sc, save_reports=save_reports)
        run_tamper_demonstration(engine)
        return

    # Default execution: run core scenarios
    print("\nRunning representative demo scenarios (use --all to run all fixtures)...")
    for sc in scenarios[:4]:
        run_scenario(engine, sc, save_reports=save_reports)

    # Run tamper demo as well
    run_tamper_demonstration(engine)
    print("\n[Done] All demonstrations completed successfully.")


if __name__ == "__main__":
    main()
