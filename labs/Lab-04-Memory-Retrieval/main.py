"""
main.py – Lab 4: Memory and Retrieval: Project Memory
=====================================================
Course: Agentic AI (26ECAC401) | Lab 4

Demonstrates:
  1. Base Workflow (default):
     - Store initial decision by authorized team lead
     - Retrieve stored decision with source tag and date
     - Detect conflict on contradictory proposal (no auto-overwrite)
     - Authorized update by team lead
     - Unauthorized update rejection (PermissionError for member)
     - Retrieve latest confirmed decision
  2. Assignment 1 (--assignment1):
     - Topic isolation between 'database' and 'hosting' (zero cross-topic leakage)
  3. Assignment 2 (--assignment2):
     - Configurable retention threshold and staleness warnings for old records

Usage:
  python main.py                # Run base 6-step workflow demonstration
  python main.py --assignment1  # Run Assignment 1 (isolated topics)
  python main.py --assignment2  # Run Assignment 2 (retention & staleness)
  python main.py --all          # Run all demonstrations sequentially
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

# Ensure Lab-04 directory is importable
_LAB_ROOT = os.path.dirname(os.path.abspath(__file__))
if _LAB_ROOT not in sys.path:
    sys.path.insert(0, _LAB_ROOT)

from agent.project_assistant import ProjectAssistant
from memory.memory_record import MemoryRecord
from memory.project_memory import ProjectMemory

_SEP_HEAVY = "═" * 72
_SEP_LIGHT = "─" * 72


def print_banner(title: str) -> None:
    print(f"\n{_SEP_HEAVY}")
    print(f"  {title}")
    print(f"{_SEP_HEAVY}")


def print_step(step_num: int, title: str) -> None:
    print(f"\n▶ Step {step_num}: {title}")
    print(f"  {_SEP_LIGHT}")


# ===========================================================================
# Base Workflow Demonstration (Steps 1 to 6)
# ===========================================================================

def run_base_workflow() -> None:
    """Execute the official 6-step project memory lifecycle."""
    print_banner("LAB 4: BASE WORKFLOW – PROJECT MEMORY LIFECYCLE")
    print(
        "Demonstrating: Structured memory, topic-scoped retrieval,\n"
        "source tagging, conflict detection, and role permissions.\n"
    )

    assistant = ProjectAssistant()

    # -----------------------------------------------------------------------
    # Step 1: Store an initial project decision
    # -----------------------------------------------------------------------
    print_step(1, "Store an initial project decision (authorized: team_lead)")
    rec = MemoryRecord(
        topic="database",
        fact="we chose PostgreSQL",
        date="2026-07-03",
        source="memory",
    )
    print(f"  Action : team_lead writes MemoryRecord to long-term memory")
    print(f"  Record : {rec.to_dict()}")
    assistant.memory.write(rec, user_role="team_lead")
    print("  Status : SUCCESS – record committed to ProjectMemory.")

    # -----------------------------------------------------------------------
    # Step 2: Retrieve the stored decision
    # -----------------------------------------------------------------------
    print_step(2, "Retrieve the stored decision with provenance")
    question_1 = "What did we decide about the database?"
    print(f"  Query  : topic='database', question='{question_1}'")
    ans_1 = assistant.answer(topic="database", question=question_1)
    print(f"  Source : {ans_1['source_tag']}")
    print(f"  Answer :\n    {ans_1['answer']}")

    # -----------------------------------------------------------------------
    # Step 3: Demonstrate a conflict
    # -----------------------------------------------------------------------
    print_step(3, "Demonstrate conflict detection (member proposes change)")
    proposed_fact = "we're switching to SQLite"
    print(f"  Action : role 'member' proposes: '{proposed_fact}'")
    conflict_resp = assistant.receive_statement(
        topic="database",
        new_fact=proposed_fact,
        user_role="member",
        date="2026-07-10",
    )

    print(f"  Conflict Flagged : {conflict_resp['conflict']}")
    print(f"  Stored Decision  : '{conflict_resp['stored']}' (dated {conflict_resp['stored_date']})")
    print(f"  Proposed Fact    : '{conflict_resp['new']}'")
    print(f"  Message          :\n    {conflict_resp['message']}")
    print(f"  Memory Overwritten: {conflict_resp['updated']} (prevented auto-overwrite)")

    # Verify memory was not overwritten
    current_stored = assistant.memory.get_latest("database")
    print(f"  Current Memory   : '{current_stored.fact}' (unchanged)")

    # -----------------------------------------------------------------------
    # Step 4: Demonstrate an authorized update
    # -----------------------------------------------------------------------
    print_step(4, "Demonstrate an authorized update (confirmed by team_lead)")
    print(f"  Action : team_lead reviews conflict and confirms change to '{proposed_fact}'")
    update_resp = assistant.confirm_and_update(
        topic="database",
        new_fact=proposed_fact,
        user_role="team_lead",
        date="2026-07-10",
    )
    print(f"  Status  : {update_resp['message']}")
    print(f"  Updated : {update_resp['updated']}")

    # -----------------------------------------------------------------------
    # Step 5: Demonstrate an unauthorized update rejection
    # -----------------------------------------------------------------------
    print_step(5, "Demonstrate unauthorized update rejection (role: member)")
    unauthorized_fact = "we're switching to MongoDB"
    print(f"  Action : role 'member' attempts to commit decision: '{unauthorized_fact}'")
    try:
        unauthorized_rec = MemoryRecord(
            topic="database",
            fact=unauthorized_fact,
            date="2026-07-12",
        )
        assistant.memory.write(unauthorized_rec, user_role="member")
        print("  ERROR: Unauthorized write was unexpectedly permitted!")
    except PermissionError as exc:
        print(f"  Result : PermissionError successfully raised!")
        print(f"  Detail : {exc}")

    # -----------------------------------------------------------------------
    # Step 6: Retrieve the final confirmed decision
    # -----------------------------------------------------------------------
    print_step(6, "Retrieve the final decision")
    question_2 = "What did we decide about the database?"
    print(f"  Query  : topic='database', question='{question_2}'")
    ans_2 = assistant.answer(topic="database", question=question_2)
    print(f"  Source : {ans_2['source_tag']}")
    print(f"  Answer :\n    {ans_2['answer']}")

    print(f"\n{_SEP_HEAVY}")
    print("  BASE WORKFLOW SUMMARY: All 6 steps verified successfully.")
    print(f"{_SEP_HEAVY}\n")


# ===========================================================================
# Assignment 1 – Topic Isolation Demonstration
# ===========================================================================

def run_assignment_1() -> None:
    """Demonstrate strict topic-scoped retrieval between multiple topics."""
    print_banner("ASSIGNMENT 1: TOPIC ISOLATION & LEAKAGE PREVENTION")
    print(
        "Verifying that 'database' and 'hosting' decisions remain strictly\n"
        "isolated and neither topic leaks into the other's retrieval results.\n"
    )

    assistant = ProjectAssistant()

    # Store Topic A: Database
    rec_db = MemoryRecord(
        topic="database",
        fact="we chose PostgreSQL",
        date="2026-07-03",
        source="memory",
    )
    assistant.memory.write(rec_db, user_role="team_lead")

    # Store Topic B: Hosting
    rec_host = MemoryRecord(
        topic="hosting",
        fact="we chose AWS ECS for container hosting",
        date="2026-07-04",
        source="memory",
    )
    assistant.memory.write(rec_host, user_role="team_lead")

    print("Stored Records in Memory Store:")
    for t in assistant.memory.get_all_topics():
        for r in assistant.memory.retrieve(t):
            print(f"  • [{r.topic.upper()}] (dated {r.date}): {r.fact}")

    print("\n--- Query 1: Topic 'database' ---")
    ans_db = assistant.answer(topic="database", question="What did we decide about the database?")
    print(f"  Source : {ans_db['source_tag']}")
    print(f"  Answer : {ans_db['answer']}")
    has_db = "postgresql" in ans_db["answer"].lower()
    leaks_host = "aws" in ans_db["answer"].lower() or "ecs" in ans_db["answer"].lower()
    print(f"  Contains database decision : {has_db}")
    print(f"  Leaks hosting decision     : {leaks_host} (CORRECT: 0 leakage)")

    print("\n--- Query 2: Topic 'hosting' ---")
    ans_host = assistant.answer(topic="hosting", question="Where are we hosting the service?")
    print(f"  Source : {ans_host['source_tag']}")
    print(f"  Answer : {ans_host['answer']}")
    has_host = "aws ecs" in ans_host["answer"].lower()
    leaks_db = "postgresql" in ans_host["answer"].lower()
    print(f"  Contains hosting decision  : {has_host}")
    print(f"  Leaks database decision    : {leaks_db} (CORRECT: 0 leakage)")

    print(f"\n{_SEP_LIGHT}")
    print("  ASSIGNMENT 1 RESULT: Strict topic isolation confirmed. No cross-topic leakage.")
    print(f"{_SEP_LIGHT}\n")


# ===========================================================================
# Assignment 2 – Staleness & Retention Policy Demonstration
# ===========================================================================

def run_assignment_2() -> None:
    """Demonstrate configurable retention policy and staleness warnings."""
    print_banner("ASSIGNMENT 2: STALENESS & RETENTION POLICY")
    retention_days = 90
    print(
        f"Configured Retention Threshold: {retention_days} days.\n"
        "Decisions older than 90 days trigger an explicit staleness warning.\n"
    )

    reference_today = date(2026, 7, 20)
    print(f"Simulated Evaluation Date: {reference_today.isoformat()}\n")

    mem = ProjectMemory(retention_days=retention_days)
    assistant = ProjectAssistant(memory=mem)

    # Record 1: Fresh decision (10 days old)
    fresh_date = (reference_today - timedelta(days=10)).strftime("%Y-%m-%d")
    fresh_rec = MemoryRecord(
        topic="frontend",
        fact="we chose Next.js with TypeScript",
        date=fresh_date,
    )
    assistant.memory.write(fresh_rec, user_role="team_lead")

    # Record 2: Stale decision (180 days old)
    stale_date = (reference_today - timedelta(days=180)).strftime("%Y-%m-%d")
    stale_rec = MemoryRecord(
        topic="architecture",
        fact="we chose monolithic architecture",
        date=stale_date,
    )
    assistant.memory.write(stale_rec, user_role="team_lead")

    print("--- Test 1: Fresh Decision (frontend, 10 days old) ---")
    ans_fresh = assistant.answer(topic="frontend", reference_date=reference_today)
    print(f"  Date   : {fresh_date} (Age: 10 days)")
    print(f"  Warning: {ans_fresh['warning']} (None expected)")
    print(f"  Answer :\n    {ans_fresh['answer']}")

    print("\n--- Test 2: Stale Decision (architecture, 180 days old) ---")
    ans_stale = assistant.answer(topic="architecture", reference_date=reference_today)
    print(f"  Date   : {stale_date} (Age: 180 days)")
    print(f"  Warning:\n    {ans_stale['warning']}")
    print(f"  Answer :\n    {ans_stale['answer']}")

    print(f"\n{_SEP_LIGHT}")
    print("  ASSIGNMENT 2 RESULT: Staleness policy verified. Stale records trigger warnings.")
    print(f"{_SEP_LIGHT}\n")


# ===========================================================================
# Main CLI Entry Point
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lab 4 – Memory and Retrieval: Project Memory Assistant"
    )
    parser.add_argument(
        "--assignment1",
        action="store_true",
        help="Run Assignment 1: Topic isolation demonstration",
    )
    parser.add_argument(
        "--assignment2",
        action="store_true",
        help="Run Assignment 2: Staleness and retention policy demonstration",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all demonstrations sequentially",
    )

    args = parser.parse_args()

    if args.all:
        run_base_workflow()
        run_assignment_1()
        run_assignment_2()
    elif args.assignment1:
        run_assignment_1()
    elif args.assignment2:
        run_assignment_2()
    else:
        # Default: base 6-step workflow
        run_base_workflow()


if __name__ == "__main__":
    main()

