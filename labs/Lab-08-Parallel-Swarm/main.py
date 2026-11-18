"""CLI Runner for Lab 8: Parallel Swarm – Faculty Appraisal Management System.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System

Demonstrates genuine parallel swarm execution with:
- Three specialist collector agents (Research, Teaching, Administrative) running concurrently via ThreadPoolExecutor.
- Capturing individual collector metrics, timing overlap, and isolated failure handling.
- Synchronized Swarm Merge stage with duplicate and conflict detection.
- Downstream evidence cross-validation against the institutional evidence registry.
- Deterministic weighted API calculation (Research 40%, Teaching 40%, Admin 20%).
- Versioned, unique appraisal report artifacts in reports/ (no overwriting).
- Human governance review gate (HoD, Dean, IQAC) and publication control.

Usage:
    python main.py                        # Runs Scenario A (Success path)
    python main.py --missing-evidence     # Runs Scenario B (Missing evidence)
    python main.py --mismatched-evidence  # Runs Scenario C (Teaching evidence mismatch)
    python main.py --collector-failure    # Runs Scenario D (One collector fails)
    python main.py --consent-denied       # Runs Scenario E (Research consent denied: consent-limited, publication blocked)
    python main.py --unauthorized-reviewer # Runs Scenario F (Student approval attempt)
    python main.py --human-rejection      # Runs Scenario G (Dean rejection)
    python main.py --all                  # Runs all Scenarios A through G
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = Path(__file__).resolve().parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from agents.coordinator import AURACoordinator
from models.schemas import WorkflowState
from swarm.state import create_initial_state


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


def display_workflow_results(state: WorkflowState) -> None:
    """Display comprehensive swarm execution metrics, merge, validation, scoring, and review status."""
    # 1. Swarm Execution Timeline
    print("\n[1] Parallel Swarm Execution Timeline (ThreadPoolExecutor Concurrency):")
    swarm_results = state.swarm_results or {}
    timeline_headers = ["Collector Role", "Status", "Duration (ms)", "Start Time", "End Time", "Activities"]
    timeline_rows = []
    for role, data in swarm_results.items():
        st = data.get("start_time", "").split("T")[-1][:8] if data.get("start_time") else "-"
        et = data.get("end_time", "").split("T")[-1][:8] if data.get("end_time") else "-"
        timeline_rows.append([
            role,
            data.get("status", "SUCCESS"),
            f"{data.get('duration_ms', 0.0):.1f}",
            st,
            et,
            str(len(data.get("activities", []))),
        ])
    print(format_table(timeline_headers, timeline_rows))

    # 2. Swarm Merge Summary
    merge_data = state.merge_result or {}
    print("\n[2] Synchronized Swarm Merge Summary:")
    print(f"    Merge Status           : {merge_data.get('status', 'N/A')}")
    print(f"    Total Activities Merged: {merge_data.get('total_activities', 0)}")
    print(f"    Failed Collectors      : {merge_data.get('failed_collectors', [])}")
    print(f"    Skipped Collectors     : {merge_data.get('skipped_collectors', [])}")
    print(f"    Duplicates Detected    : {len(merge_data.get('duplicates_detected', []))}")
    print(f"    Conflicts Detected     : {len(merge_data.get('conflicts_detected', []))}")

    # 3. Evidence Validation Summary
    val_activities = state.validated_activities
    exceptions = state.evidence_exceptions
    print("\n[3] Evidence Validation Summary:")
    print(f"    Total Claims Evaluated : {len(val_activities)}")
    print(f"    Verified Claims        : {len(val_activities) - len(exceptions)}")
    print(f"    Exceptions Detected    : {len(exceptions)}")

    if exceptions:
        print("\n    Active Evidence Exceptions:")
        exc_headers = ["Activity ID", "Category", "Points", "Evidence Status", "Notes"]
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
    print(f"    Score Status           : {api_score.get('score_status', 'PROVISIONAL')}")
    print(f"    Score Type             : {api_score.get('score_type', 'FINAL')}")
    print(f"    Is Provisional?        : {api_score.get('is_provisional', True)}")
    print(f"    Is Consent Limited?    : {api_score.get('is_consent_limited', False)}")
    if api_score.get("is_consent_limited"):
        print(f"    Overall Claimed Score  : {api_score.get('overall_claimed_score', 0.0):.2f} [PARTIAL - Excludes Skipped Categories]")
        print(f"    Overall Verified Score : {api_score.get('overall_verified_score', 0.0):.2f} [PARTIAL - Excludes Skipped Categories]")
        print(f"    Scoring Note           : {api_score.get('score_note', '')}")
    else:
        print(f"    Overall Claimed Score  : {api_score.get('overall_claimed_score', 0.0):.2f}")
        print(f"    Overall Verified Score : {api_score.get('overall_verified_score', 0.0):.2f}")

    cat_scores = api_score.get("category_scores", {})
    if cat_scores:
        cat_headers = ["Category", "Status", "Raw Claimed", "Weight", "Claimed Weighted", "Verified Pts", "Verified Score"]
        cat_rows = []
        for cat, data in cat_scores.items():
            status = data.get("status", "VERIFIED")
            raw_pts_val = data.get("raw_claimed_points")
            raw_pts_str = f"{raw_pts_val:.1f}" if raw_pts_val is not None else "N/A (Skipped)"
            raw_wgt_val = data.get("raw_weighted_score")
            raw_wgt_str = f"{raw_wgt_val:.2f}" if raw_wgt_val is not None else "N/A (Skipped)"
            ver_pts_val = data.get("verified_points")
            ver_pts_str = f"{ver_pts_val:.1f}" if ver_pts_val is not None else "N/A (Skipped)"
            ver_wgt_val = data.get("verified_weighted_score")
            ver_wgt_str = f"{ver_wgt_val:.2f}" if ver_wgt_val is not None else "N/A (Skipped)"
            cat_rows.append([
                cat,
                status,
                raw_pts_str,
                f"{data.get('weightage', 0.0):.2f}",
                raw_wgt_str,
                ver_pts_str,
                ver_wgt_str,
            ])
        print(format_table(cat_headers, cat_rows))

    # 5. Human Review Governance Gate
    review = state.review_decision or {}
    print("\n[5] Human Review & Governance Gate:")
    print(f"    Reviewer ID            : {review.get('reviewer_id', 'N/A')}")
    print(f"    Reviewer Role          : {review.get('reviewer_role', 'N/A')}")
    print(f"    Review Decision        : {review.get('decision', 'N/A')}")
    print(f"    Reviewer Comments      : {review.get('comments', 'None')}")

    # 6. Final Publication & Dashboard Status
    print("\n[6] Final Publication & Dashboard Status:")
    print(f"    Workflow Status        : {state.workflow_status}")
    print(f"    Publication Status     : {state.publication_status}")
    if state.report and "artifact_path" in state.report:
        print(f"    Report Artifact        : {state.report['artifact_path']}")


def run_scenario_a() -> Dict[str, Any]:
    """Scenario A: Successful appraisal with all three collectors executing concurrently."""
    print_banner("SCENARIO A: Full Clean Parallel Swarm (HoD Approved)")
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
    final_state = coordinator.run_workflow(state)
    display_workflow_results(final_state)
    passed = (final_state.publication_status == "APPROVED_AND_PUBLISHED")
    return {
        "scenario": "Scenario A: Clean Success",
        "expected": "APPROVED_AND_PUBLISHED",
        "actual": final_state.publication_status,
        "passed": passed,
    }


def run_scenario_b() -> Dict[str, Any]:
    """Scenario B: Research evidence missing; score finalization and publication blocked."""
    print_banner("SCENARIO B: Research Evidence Missing (Publication Blocked)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        test_injection="MISSING_EVIDENCE",
        scenario_name="scenario_b_missing_evidence",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_HOD_001",
        human_reviewer_role="HoD",
        human_review_decision="APPROVED",
    )
    final_state = coordinator.run_workflow(state)
    display_workflow_results(final_state)
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
    """Scenario C: Teaching evidence mismatched; exception routed for review."""
    print_banner("SCENARIO C: Teaching Evidence Mismatch (Publication Blocked)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        test_injection="MISMATCHED_EVIDENCE",
        scenario_name="scenario_c_mismatched_evidence",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_HOD_001",
        human_reviewer_role="HoD",
        human_review_decision="APPROVED",
    )
    final_state = coordinator.run_workflow(state)
    display_workflow_results(final_state)
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
    """Scenario D: One collector fails; other collector outputs preserved and workflow reports incomplete collection."""
    print_banner("SCENARIO D: Specialist Collector Failure (Partial Merge, Preserved Outputs)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        test_injection="FAIL_RESEARCH",
        scenario_name="scenario_d_collector_failure",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_HOD_001",
        human_reviewer_role="HoD",
        human_review_decision="APPROVED",
    )
    final_state = coordinator.run_workflow(state)
    display_workflow_results(final_state)
    passed = (
        final_state.merge_result is not None
        and final_state.merge_result.get("status") == "PARTIAL"
        and "ResearchDataCollectionAgent" in final_state.merge_result.get("failed_collectors", [])
        and len(final_state.merged_activities) > 0
        and final_state.publication_status == "BLOCKED"
    )
    return {
        "scenario": "Scenario D: Collector Failure",
        "expected": "PARTIAL Merge / BLOCKED",
        "actual": f"{final_state.merge_result.get('status')} / {final_state.publication_status}",
        "passed": passed,
    }


def run_scenario_e() -> Dict[str, Any]:
    """Scenario E: Faculty denies consent for one source; category marked consent-limited and ordinary publication blocked."""
    print_banner("SCENARIO E: Research Consent Denied (Consent-Limited, Publication Blocked)")
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
    final_state = coordinator.run_workflow(state)
    display_workflow_results(final_state)
    research_acts = [a for a in final_state.merged_activities if a.get("category") == "Research"]
    api_score = final_state.api_score or {}
    res_cat = api_score.get("category_scores", {}).get("Research", {})

    passed = (
        len(research_acts) == 0
        and len(final_state.merged_activities) > 0
        and res_cat.get("status") == "NOT_COLLECTED_CONSENT_DENIED"
        and res_cat.get("is_verified_zero") is False
        and res_cat.get("raw_claimed_points") is None
        and res_cat.get("verified_points") is None
        and res_cat.get("raw_weighted_score") is None
        and res_cat.get("verified_weighted_score") is None
        and api_score.get("is_provisional") is True
        and api_score.get("score_status") == "CONSENT_LIMITED"
        and final_state.workflow_status == "BLOCKED_ON_CONSENT"
        and final_state.publication_status == "BLOCKED"
    )
    return {
        "scenario": "Scenario E: Consent Denied",
        "expected": "CONSENT_LIMITED / BLOCKED",
        "actual": f"{api_score.get('score_status')} / {final_state.publication_status}",
        "passed": passed,
    }


def run_scenario_f() -> Dict[str, Any]:
    """Scenario F: Unauthorized reviewer attempts approval; request rejected."""
    print_banner("SCENARIO F: Unauthorized Reviewer Role Attempt (Student Representative)")
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
    final_state = coordinator.run_workflow(state)
    display_workflow_results(final_state)
    passed = (
        final_state.workflow_status == "REJECTED"
        and final_state.publication_status == "BLOCKED"
    )
    return {
        "scenario": "Scenario F: Unauthorized Reviewer",
        "expected": "REJECTED / BLOCKED",
        "actual": f"{final_state.workflow_status} / {final_state.publication_status}",
        "passed": passed,
    }


def run_scenario_g() -> Dict[str, Any]:
    """Scenario G: Successful collection and validation followed by human rejection."""
    print_banner("SCENARIO G: Human Reviewer Rejection by Dean (Publication Blocked)")
    state = create_initial_state(
        faculty_id="FAC001",
        faculty_name="Dr. Ananya Sharma",
        appraisal_period="2025-2026",
        requester_role="Faculty",
        scenario_name="scenario_g_human_rejection",
    )
    coordinator = AURACoordinator(
        human_reviewer_id="REV_DEAN_001",
        human_reviewer_role="Dean",
        human_review_decision="REJECTED",
        human_review_comments="Instructional delivery hours documentation does not meet minimum 120 contact hour requirement.",
    )
    final_state = coordinator.run_workflow(state)
    display_workflow_results(final_state)
    passed = (
        final_state.workflow_status == "REJECTED"
        and final_state.publication_status == "BLOCKED"
    )
    return {
        "scenario": "Scenario G: Dean Rejection",
        "expected": "REJECTED / BLOCKED",
        "actual": f"{final_state.workflow_status} / {final_state.publication_status}",
        "passed": passed,
    }


def main() -> None:
    """Parse CLI arguments and dispatch requested scenario(s)."""
    parser = argparse.ArgumentParser(
        description="Lab 8: Parallel Swarm – Faculty Appraisal Management System"
    )
    parser.add_argument(
        "--missing-evidence",
        action="store_true",
        help="Run Scenario B: Research evidence missing",
    )
    parser.add_argument(
        "--mismatched-evidence",
        action="store_true",
        help="Run Scenario C: Teaching evidence category mismatch",
    )
    parser.add_argument(
        "--collector-failure",
        action="store_true",
        help="Run Scenario D: Research collector fails; other outputs preserved",
    )
    parser.add_argument(
        "--consent-denied",
        action="store_true",
        help="Run Scenario E: Research consent denied (consent-limited, publication blocked without override)",
    )
    parser.add_argument(
        "--unauthorized-reviewer",
        action="store_true",
        help="Run Scenario F: Approval attempted by unauthorized role (Student)",
    )
    parser.add_argument(
        "--human-rejection",
        action="store_true",
        help="Run Scenario G: Dean exercises governance oversight and rejects report",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Execute all Scenarios A through G sequentially and display summary table",
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
        results.append(run_scenario_g())

        print_banner("CONSOLIDATED SUMMARY: ALL SCENARIOS (LAB 8)")
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
    elif args.collector_failure:
        run_scenario_d()
    elif args.consent_denied:
        run_scenario_e()
    elif args.unauthorized_reviewer:
        run_scenario_f()
    elif args.human_rejection:
        run_scenario_g()
    else:
        # Default: Scenario A
        run_scenario_a()


if __name__ == "__main__":
    main()
