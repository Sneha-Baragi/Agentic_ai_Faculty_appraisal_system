#!/usr/bin/env python3
"""Interactive CLI Runner for Lab 10: Cloud Operations Agent.

Course: Agentic AI (26ECAC401)
Lab 10: Cloud Operations Agent – Failed Deployment
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure lab directory is in sys.path
LAB_ROOT = Path(__file__).resolve().parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agent.cloud_ops_agent import CloudOperationsAgent


def run_scenario(
    agent: CloudOperationsAgent,
    scenario_id: str,
    urgency_prompt: bool = False,
    save_reports: bool = True,
) -> None:
    print("\n" + "=" * 80)
    print(f"RUNNING CLOUD INCIDENT SCENARIO: {scenario_id}")
    print(f"Simulated Urgency Prompt: {urgency_prompt}")
    print("=" * 80)

    report = agent.run_incident(
        scenario_id=scenario_id,
        urgency_prompt=urgency_prompt,
    )

    md = agent.format_markdown_report(report)
    print("\n" + md)

    if save_reports:
        md_file, json_file = agent.save_report(report)
        print(f"\n[Artifact Generated] Markdown: {md_file.name}")
        print(f"[Artifact Generated] JSON:     {json_file.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lab 10: Cloud Operations Agent – Incident Diagnostics & Remediation Gating"
    )
    parser.add_argument(
        "--scenario",
        default="all",
        choices=[
            "all",
            "core_payments_regression",
            "assignment_1_db_pool_exhaustion",
            "assignment_2_safe_pod_restart",
            "edge_case_missing_deploy",
            "edge_case_zero_baseline",
            "edge_case_unknown_action",
        ],
        help="Scenario to execute (default: all)",
    )
    parser.add_argument(
        "--urgency",
        action="store_true",
        help="Simulate an emergency urgency prompt from on-call engineer",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save markdown/JSON reports to disk",
    )
    args = parser.parse_args()

    agent = CloudOperationsAgent()
    save_reports = not args.no_save

    if args.scenario == "all":
        print("\n=== EXECUTING ALL LAB 10 INCIDENT SCENARIOS ===")
        # Run core with urgency=True to verify safety gate
        run_scenario(
            agent,
            "core_payments_regression",
            urgency_prompt=True,
            save_reports=save_reports,
        )
        # Run Assignment 1 (DB pool exhaustion)
        run_scenario(
            agent,
            "assignment_1_db_pool_exhaustion",
            urgency_prompt=False,
            save_reports=save_reports,
        )
        # Run Assignment 2 (Safe auto-remediation restart_single_pod)
        run_scenario(
            agent,
            "assignment_2_safe_pod_restart",
            urgency_prompt=False,
            save_reports=save_reports,
        )
    else:
        run_scenario(
            agent,
            args.scenario,
            urgency_prompt=args.urgency,
            save_reports=save_reports,
        )


if __name__ == "__main__":
    main()
