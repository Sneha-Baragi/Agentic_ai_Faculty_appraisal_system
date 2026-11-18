"""CLI Runner for Lab 7: Agentic Node Graph – Faculty Appraisal Management System.

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System

Demonstrates hybrid agentic workflow orchestration with:
- True parallel multi-threaded data collection (Research, Teaching, Administrative)
- Institutional evidence validation against official registry
- Weighted Academic Performance Indicator (API) scoring
- Versioned appraisal report generation (artifacts saved in reports/)
- Human-in-the-loop review and approval gate (HoD, Dean, IQAC)
- Secure dashboard publication gate

Usage:
    python main.py                       # Runs Scenario A (Success path)
    python main.py --missing-evidence    # Runs Scenario B (Missing evidence)
    python main.py --mismatched-evidence # Runs Scenario C (Mismatched evidence)
    python main.py --human-rejection     # Runs Scenario D (Dean rejection)
    python main.py --consent-denied      # Runs Scenario E (Research consent denied)
    python main.py --unauthorized-reviewer # Runs Scenario F (Student approval attempt)
    python main.py --all                 # Runs all scenarios A through F
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure Lab 7 root is on sys.path
LAB_ROOT = Path(__file__).resolve().parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agents.coordinator import AURACoordinator
from graph.state import create_initial_state
from models.schemas import WorkflowState


def format_table(headers: List[str], rows: List[List[str]]) -> str:
    """Format an ASCII table with consistent column widths."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_str = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"

    data_lines = []
    for row in rows:
        line = "| " + " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)) + " |"
        data_lines.append(line)

    return "\n".join([sep, header_str, sep] + data_lines + [sep])


def print_banner(title: str) -> None:
    """Print standard section banner."""
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def display_workflow_results(state: WorkflowState, graph_trace: List[Dict[str, Any]]) -> None:
    """Display comprehensive execution traces, validation results, API scores, and governance status."""
    # 1. Execution Trace Table
    print("\n[1] Graph Execution Trace (Sequential & Parallel Nodes):")
    trace_headers = ["Step", "Node Name", "Mode", "Duration (ms)", "Status"]
    trace_rows = []
    for t in graph_trace:
        step = str(t.get("step", "-"))
        name = str(t.get("node_name", "-"))
        mode = str(t.get("execution_mode", "SEQUENTIAL"))
        dur = f"{t.get('duration_ms', 0.0):.1f}"
        status = str(t.get("status", "SUCCESS"))
        trace_rows.append([step, name, mode, dur, status])
    print(format_table(trace_headers, trace_rows))

    # 2. Parallel Collection Status
    if state.collection_status:
        print("\n[2] Parallel Data Collection Metrics:")
        col_headers = ["Collector Node", "Status", "Duration (ms)", "Start Time"]
        col_rows = []
        for k, v in state.collection_status.items():
            col_rows.append([
                k,
                v.get("status", "SUCCESS"),
                f"{v.get('duration_ms', 0.0):.1f}",
                v.get("start_time", "").split("T")[-1][:8] if v.get("start_time") else "-",
            ])
        print(format_table(col_headers, col_rows))

    # 3. Evidence Validation Breakdown
    val_activities = state.validated_activities
    exceptions = state.evidence_exceptions
    print("\n[3] Evidence Validation Summary:")
    print(f"    Total Activities Evaluated : {len(val_activities)}")
    print(f"    Verified Claims            : {len(val_activities) - len(exceptions)}")
    print(f"    Exceptions Detected        : {len(exceptions)}")

    if exceptions:
        print("\n    Active Evidence Exceptions:")
        exc_headers = ["Activity ID", "Category", "Claimed Points", "Status", "Reason / Notes"]
        exc_rows = []
        for exc in exceptions:
            exc_rows.append([
                exc.get("activity_id", "-"),
                exc.get("category", "-"),
                f"{exc.get('claimed_points', 0.0):.1f}",
                exc.get("evidence_status", "-"),
                exc.get("validation_notes", "-")[:45],
            ])
        print(format_table(exc_headers, exc_rows))

    # 4. API Score Breakdown
    api_score = state.api_score or {}
    print("\n[4] Academic Performance Indicator (API) Score Breakdown:")
    score_status = api_score.get("score_status", "PROVISIONAL")
    print(f"    Score Status              : {score_status}")
    print(f"    Is Provisional?           : {api_score.get('is_provisional', True)}")
    print(f"    Overall Claimed Score     : {api_score.get('overall_claimed_score', 0.0):.2f}")
    print(f"    Overall Verified Score    : {api_score.get('overall_verified_score', 0.0):.2f}")

    cat_scores = api_score.get("category_scores", {})
    if cat_scores:
        cat_headers = ["Category", "Raw Claimed", "Weight", "Claimed Weighted", "Verified Pts", "Verified Score"]
        cat_rows = []
        for cat, data in cat_scores.items():
            cat_rows.append([
                cat,
                f"{data.get('raw_claimed_points', 0.0):.1f}",
                f"{data.get('weightage', 0.0):.2f}",
                f"{data.get('raw_weighted_score', 0.0):.2f}",
                f"{data.get('verified_points', 0.0):.1f}",
                f"{data.get('verified_weighted_score', 0.0):.2f}",
            ])
        print(format_table(cat_headers, cat_rows))

    # 5. Human Review & Publication Gate Status
    print("\n[5] Human Review & Governance Gate:")
    review = state.review_decision or {}
    print(f"    Reviewer ID     : {review.get('reviewer_id', 'N/A')}")
    print(f"    Reviewer Role   : {review.get('reviewer_role', 'N/A')}")
    print(f"    Review Decision : {review.get('decision', 'N/A')}")
    print(f"    Reviewer Notes  : {review.get('comments', 'None')}")

    print("\n[6] Final Publication & Dashboard Status:")
    print(f"    Workflow Status    : {state.workflow_status}")
    print(f"    Publication Status : {state.publication_status}")
    if state.report and "artifact_path" in state.report:
        print(f"    Report Artifact    : {state.report['artifact_path']}")


def run_scenario_a() -> Dict[str, Any]:
    """Scenario A: Successful Happy Path with Parallel Collection and HoD Approval."""
    print_banner("SCENARIO A: Full Successful Appraisal Workflow (HoD Approved)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        scenario_name="scenario_a_success",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_HOD_001",
        human_reviewer_role="HoD",
        human_review_decision="APPROVED",
        human_review_comments="All activities verified against institutional records. Recommended for promotion.",
    )
    graph = coordinator.build_graph()
    final_state = graph.run(initial_node_name="profile_intake", state=state)
    display_workflow_results(final_state, graph.execution_trace)
    return {
        "scenario": "Scenario A: Happy Path",
        "expected": "APPROVED_AND_PUBLISHED",
        "actual": final_state.publication_status,
        "passed": final_state.publication_status == "APPROVED_AND_PUBLISHED",
    }


def run_scenario_b() -> Dict[str, Any]:
    """Scenario B: Claim with Missing Evidence (Provisional Score, Publication Blocked)."""
    print_banner("SCENARIO B: Missing Evidence Reference (Publication Blocked)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        include_missing_evidence=True,
        scenario_name="scenario_b_missing_evidence",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_HOD_001",
        human_reviewer_role="HoD",
        human_review_decision="APPROVED",
    )
    graph = coordinator.build_graph()
    final_state = graph.run(initial_node_name="profile_intake", state=state)
    display_workflow_results(final_state, graph.execution_trace)
    passed = (
        final_state.workflow_status == "BLOCKED_ON_EXCEPTIONS"
        and final_state.publication_status == "BLOCKED"
        and final_state.api_score.get("is_provisional") is True
    )
    return {
        "scenario": "Scenario B: Missing Evidence",
        "expected": "BLOCKED",
        "actual": final_state.publication_status,
        "passed": passed,
    }


def run_scenario_c() -> Dict[str, Any]:
    """Scenario C: Claim with Mismatched Evidence (Certificate Belongs to FAC002)."""
    print_banner("SCENARIO C: Mismatched Evidence Faculty Ownership (Publication Blocked)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        include_mismatched_evidence=True,
        scenario_name="scenario_c_mismatched_evidence",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_HOD_001",
        human_reviewer_role="HoD",
        human_review_decision="APPROVED",
    )
    graph = coordinator.build_graph()
    final_state = graph.run(initial_node_name="profile_intake", state=state)
    display_workflow_results(final_state, graph.execution_trace)
    passed = (
        final_state.workflow_status == "BLOCKED_ON_EXCEPTIONS"
        and final_state.publication_status == "BLOCKED"
    )
    return {
        "scenario": "Scenario C: Mismatched Evidence",
        "expected": "BLOCKED",
        "actual": final_state.publication_status,
        "passed": passed,
    }


def run_scenario_d() -> Dict[str, Any]:
    """Scenario D: Human Rejection by Dean (Publication Blocked)."""
    print_banner("SCENARIO D: Human Reviewer Rejection by Dean (Publication Blocked)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        scenario_name="scenario_d_human_rejection",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_DEAN_001",
        human_reviewer_role="Dean",
        human_review_decision="REJECTED",
        human_review_comments="Teaching hours documentation does not meet minimum 120 contact hour requirement.",
    )
    graph = coordinator.build_graph()
    final_state = graph.run(initial_node_name="profile_intake", state=state)
    display_workflow_results(final_state, graph.execution_trace)
    passed = (
        final_state.workflow_status == "REJECTED"
        and final_state.publication_status == "BLOCKED"
    )
    return {
        "scenario": "Scenario D: Dean Rejection",
        "expected": "BLOCKED (REJECTED)",
        "actual": f"{final_state.publication_status} ({final_state.workflow_status})",
        "passed": passed,
    }


def run_scenario_e() -> Dict[str, Any]:
    """Scenario E: Faculty Denies Consent for Research Data Collection."""
    print_banner("SCENARIO E: Faculty Denies Consent for Research Collection")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        consent={"research": False, "teaching_learning": True, "administrative": True},
        scenario_name="scenario_e_consent_denied",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_HOD_001",
        human_reviewer_role="HoD",
        human_review_decision="APPROVED",
    )
    graph = coordinator.build_graph()
    final_state = graph.run(initial_node_name="profile_intake", state=state)
    display_workflow_results(final_state, graph.execution_trace)
    passed = (
        len(final_state.research_activities) == 0
        and len(final_state.teaching_activities) > 0
        and len(final_state.administrative_activities) > 0
    )
    return {
        "scenario": "Scenario E: Research Consent Denied",
        "expected": "Research Skipped (0 records)",
        "actual": f"Research: {len(final_state.research_activities)}, Teaching: {len(final_state.teaching_activities)}",
        "passed": passed,
    }


def run_scenario_f() -> Dict[str, Any]:
    """Scenario F: Review Attempted by Unauthorized Role (Student)."""
    print_banner("SCENARIO F: Review Attempted by Unauthorized Role (Student)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        scenario_name="scenario_f_unauthorized_reviewer",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_STU_999",
        human_reviewer_role="Student_Representative",
        human_review_decision="APPROVED",
        human_review_comments="Student representative sign-off attempt.",
    )
    graph = coordinator.build_graph()
    final_state = graph.run(initial_node_name="profile_intake", state=state)
    display_workflow_results(final_state, graph.execution_trace)
    passed = (
        final_state.workflow_status == "REJECTED"
        and final_state.publication_status == "BLOCKED"
    )
    return {
        "scenario": "Scenario F: Unauthorized Reviewer",
        "expected": "BLOCKED (REJECTED)",
        "actual": f"{final_state.publication_status} ({final_state.workflow_status})",
        "passed": passed,
    }


def main() -> None:
    """Parse CLI arguments and dispatch requested scenario(s)."""
    parser = argparse.ArgumentParser(
        description="Lab 7: Agentic Node Graph – Faculty Appraisal Management System"
    )
    parser.add_argument(
        "--missing-evidence",
        action="store_true",
        help="Run Scenario B: Claim with missing evidence reference",
    )
    parser.add_argument(
        "--mismatched-evidence",
        action="store_true",
        help="Run Scenario C: Claim with mismatched evidence ownership",
    )
    parser.add_argument(
        "--human-rejection",
        action="store_true",
        help="Run Scenario D: Dean exercises governance oversight and rejects report",
    )
    parser.add_argument(
        "--consent-denied",
        action="store_true",
        help="Run Scenario E: Faculty denies consent for Research Collection",
    )
    parser.add_argument(
        "--unauthorized-reviewer",
        action="store_true",
        help="Run Scenario F: Approval attempted by unauthorized role (Student)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Execute all Scenarios A through F and print consolidated summary",
    )

    args = parser.parse_args()

    results: List[Dict[str, Any]] = []

    if args.all:
        results.append(run_scenario_a())
        results.append(run_scenario_b())
        results.append(run_scenario_c())
        results.append(run_scenario_d())
        results.append(run_scenario_e())
        results.append(run_scenario_f())

        print_banner("CONSOLIDATED SUMMARY: ALL SCENARIOS")
        summary_headers = ["Scenario Name", "Expected Status", "Actual Status", "Result"]
        summary_rows = []
        for r in results:
            result_label = "PASS [OK]" if r["passed"] else "FAIL [X]"
            summary_rows.append([
                r["scenario"],
                r["expected"],
                r["actual"],
                result_label,
            ])
        print(format_table(summary_headers, summary_rows))

    elif args.missing_evidence:
        run_scenario_b()
    elif args.mismatched_evidence:
        run_scenario_c()
    elif args.human_rejection:
        run_scenario_d()
    elif args.consent_denied:
        run_scenario_e()
    elif args.unauthorized_reviewer:
        run_scenario_f()
    else:
        # Default: Scenario A
        run_scenario_a()


if __name__ == "__main__":
    main()
