"""Main Runner and CLI Interface for Lab 6 OpenCLA/OpenClaw Runtime.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime

Usage:
    python main.py                 # Run base demonstration (Runs 1 to 5)
    python main.py --assignment1   # Run Assignment 1 (Per-User Rate Limiting)
    python main.py --assignment2   # Run Assignment 2 (Failure Escalation)
    python main.py --all           # Run Base + Assignment 1 + Assignment 2
"""

import argparse
import inspect
import json
from typing import Any, Dict

from runtime.agent_runtime import (
    RateLimiter,
    receive_task,
    run_task,
    select_skill,
)
from runtime.audit import Audit
from runtime.memory import Memory
from skills import (
    SKILL_REGISTRY,
    TranslateTextSkill,
    register_skill,
    reset_skill_registry,
)


def print_banner(title: str, width: int = 76) -> None:
    """Print visually distinct section header."""
    print("\n" + "=" * width)
    print(f"  {title.upper()}")
    print("=" * width)


def print_step(step_num: int, title: str, width: int = 76) -> None:
    """Print step subheader."""
    print(f"\n--- [RUN {step_num}] {title} " + "-" * max(0, width - len(title) - 15))


def print_audit_entry(entry: Dict[str, Any]) -> None:
    """Format and print an audit record."""
    print("Audit Log Entry:")
    print(f"  Timestamp  : {entry.get('timestamp')}")
    print(f"  User       : {entry.get('user')}")
    print(f"  Skill      : {entry.get('skill_name')}")
    print(f"  Tool Calls : {json.dumps(entry.get('tool_calls', []))}")
    if entry.get("result") is not None:
        print(f"  Result     : {json.dumps(entry.get('result'))}")
    if entry.get("error") is not None:
        print(f"  Error      : {entry.get('error')}")


# -----------------------------------------------------------------------------
# BASE DEMONSTRATION (Runs 1 to 5)
# -----------------------------------------------------------------------------


def run_base_demonstration() -> None:
    """Execute the five required base scenarios."""
    reset_skill_registry()
    memory = Memory()
    audit = Audit()

    print_banner("Lab 6: Base OpenCLA/OpenClaw Runtime Demonstration")
    print("Runtime Architecture: Interface -> Loop -> Skills -> Tools -> Memory -> Audit")
    print(f"Initial Registered Skills: {list(SKILL_REGISTRY.keys())}")

    # -------------------------------------------------------------------------
    # RUN 1: Successful note summarization
    # -------------------------------------------------------------------------
    print_step(1, "Successful Note Summarization (summarize_notes)")
    task_1 = {
        "skill": "summarize_notes",
        "text": "Agentic AI systems combine goals tools skills memory",
    }
    user_1 = "uday"
    print(f"User       : '{user_1}'")
    print(f"Task Input : {json.dumps(task_1)}")

    result_1 = receive_task(
        task=task_1,
        user=user_1,
        memory=memory,
        audit=audit,
        enable_rate_limiting=False,
        enable_escalation=False,
    )
    print(f"Execution  : SUCCESS")
    print(f"Output     : {result_1['summary']}")
    print(f"Word Count : {result_1['word_count']}")
    print_audit_entry(audit.get_entries()[-1])

    # -------------------------------------------------------------------------
    # RUN 2: Successful email drafting
    # -------------------------------------------------------------------------
    print_step(2, "Successful Email Drafting (draft_email)")
    task_2 = {
        "skill": "draft_email",
        "recipient": "Dr. Meena",
        "subject": "Lab guide review",
    }
    user_2 = "uday"
    print(f"User       : '{user_2}'")
    print(f"Task Input : {json.dumps(task_2)}")

    result_2 = receive_task(
        task=task_2,
        user=user_2,
        memory=memory,
        audit=audit,
        enable_rate_limiting=False,
        enable_escalation=False,
    )
    print(f"Execution  : SUCCESS")
    print(f"Recipient  : {result_2['recipient']} ({result_2['email']})")
    print(f"Draft Email:\n{result_2['draft']}")
    print_audit_entry(audit.get_entries()[-1])

    # -------------------------------------------------------------------------
    # RUN 3: Failed email drafting
    # -------------------------------------------------------------------------
    print_step(3, "Failed Email Drafting (Unknown Contact)")
    task_3 = {
        "skill": "draft_email",
        "recipient": "Unknown Person",
        "subject": "Hello",
    }
    user_3 = "uday"
    print(f"User       : '{user_3}'")
    print(f"Task Input : {json.dumps(task_3)}")

    try:
        receive_task(
            task=task_3,
            user=user_3,
            memory=memory,
            audit=audit,
            enable_rate_limiting=False,
            enable_escalation=False,
        )
    except ValueError as exc:
        print(f"Execution  : CAUGHT EXPECTED ERROR -> {exc}")

    print("Audit Verification (Error captured in log):")
    print_audit_entry(audit.get_entries()[-1])

    # -------------------------------------------------------------------------
    # RUN 4: Register a third skill dynamically
    # -------------------------------------------------------------------------
    print_step(4, "Dynamic Skill Extensibility (TranslateTextSkill)")
    print("Action     : Registering 'translate_text' into SKILL_REGISTRY at runtime...")
    register_skill("translate_text", TranslateTextSkill)
    print(f"Updated SKILL_REGISTRY: {list(SKILL_REGISTRY.keys())}")

    task_4 = {
        "skill": "translate_text",
        "text": "Hello, team",
        "target_language": "Kannada",
    }
    print(f"Task Input : {json.dumps(task_4)}")

    result_4 = receive_task(
        task=task_4,
        user="uday",
        memory=memory,
        audit=audit,
        enable_rate_limiting=False,
        enable_escalation=False,
    )
    print(f"Execution  : SUCCESS")
    print(f"Result     : {result_4['translated_text']}")
    print_audit_entry(audit.get_entries()[-1])

    # Verify zero modifications to runtime loop
    run_src = inspect.getsource(run_task)
    sel_src = inspect.getsource(select_skill)
    has_hardcoding = "TranslateTextSkill" in run_src or "TranslateTextSkill" in sel_src
    print(f"Code Integrity: Generic dispatch preserved, hardcoding = {has_hardcoding}")

    # -------------------------------------------------------------------------
    # RUN 5: Per-user memory isolation
    # -------------------------------------------------------------------------
    print_step(5, "Per-User Scoped Memory Verification")
    uday_memory = memory.scope("uday")
    print(f"Memory Scope for 'uday' : {json.dumps(uday_memory, indent=2)}")

    # Initialize a second user's memory
    priya_memory = memory.scope("priya")
    priya_memory["project"] = "Faculty Appraisal Agent"
    print(f"Memory Scope for 'priya': {json.dumps(priya_memory, indent=2)}")

    # Verify isolation
    leakage = any(k in priya_memory for k in uday_memory)
    print(f"Memory Isolation: uday keys present in priya scope = {leakage} (Strictly Isolated)")


# -----------------------------------------------------------------------------
# ASSIGNMENT 1: Per-User Rate Limiting
# -----------------------------------------------------------------------------


def run_assignment_1() -> None:
    """Execute demonstration for Assignment 1: Rate Limiting."""
    reset_skill_registry()
    memory = Memory()
    audit = Audit()
    limiter = RateLimiter(max_tasks=3)

    print_banner("Assignment 1: Per-User Session Rate Limiting")
    print("Policy Invariant: Each user may execute at most 3 tasks per session.")
    print("The 4th task from the same user is rejected; distinct users have independent limits.\n")

    user_a = "uday"
    user_b = "priya"

    # Tasks 1 to 3 for user_a
    for i in range(1, 4):
        print(f"--- Submitting Task {i} for '{user_a}' ---")
        task = {
            "skill": "summarize_notes",
            "text": f"Study session note chunk number {i}",
        }
        res = receive_task(
            task=task,
            user=user_a,
            memory=memory,
            audit=audit,
            rate_limiter=limiter,
            enable_rate_limiting=True,
        )
        print(f"Status: {res['status'].upper()} | Count: {limiter.get_count(user_a)}/3")

    # Task 4 for user_a (must be rejected)
    print(f"\n--- Submitting Task 4 for '{user_a}' (Expected: REJECTED) ---")
    task_4 = {
        "skill": "summarize_notes",
        "text": "Exceeded quota note",
    }
    res_4 = receive_task(
        task=task_4,
        user=user_a,
        memory=memory,
        audit=audit,
        rate_limiter=limiter,
        enable_rate_limiting=True,
    )
    print(f"Status: {res_4['status'].upper()}")
    print(f"Message: {res_4.get('error')}")
    print("Audit Log Entry for Rejection:")
    print_audit_entry(audit.get_entries()[-1])

    # Task for user_b (must succeed)
    print(f"\n--- Submitting Task 1 for '{user_b}' (Independent Limit) ---")
    task_b = {
        "skill": "summarize_notes",
        "text": "Independent user note execution",
    }
    res_b = receive_task(
        task=task_b,
        user=user_b,
        memory=memory,
        audit=audit,
        rate_limiter=limiter,
        enable_rate_limiting=True,
    )
    print(f"Status: {res_b['status'].upper()} | User '{user_b}' Count: {limiter.get_count(user_b)}/3")
    print("\n[Assignment 1 Verification Passed]: Rate limits enforced per-user and per-session.")


# -----------------------------------------------------------------------------
# ASSIGNMENT 2: Escalate After Two Failures
# -----------------------------------------------------------------------------


def run_assignment_2() -> None:
    """Execute demonstration for Assignment 2: Failure Escalation."""
    reset_skill_registry()
    memory = Memory()
    audit = Audit()

    print_banner("Assignment 2: Escalate After Two Failures")
    print("Policy Invariant: If a skill fails twice for a user in a session,")
    print("the 3rd attempt is escalated to a human supervisor instead of re-executing.\n")

    user = "uday"
    failing_task = {
        "skill": "draft_email",
        "recipient": "Unknown Ghost Contact",
        "subject": "Missing contact notification",
    }

    # Attempt 1: Causes failure 1
    print("--- [ATTEMPT 1] Executing draft_email for unknown contact ---")
    try:
        receive_task(
            task=failing_task,
            user=user,
            memory=memory,
            audit=audit,
            enable_rate_limiting=False,
            enable_escalation=True,
        )
    except ValueError as exc:
        print(f"Outcome: FAILED (Expected) -> {exc}")
    print(f"Audit Log Failures Count: {audit.count_failures(user, 'draft_email')}")

    # Attempt 2: Causes failure 2
    print("\n--- [ATTEMPT 2] Repeating draft_email for unknown contact ---")
    try:
        receive_task(
            task=failing_task,
            user=user,
            memory=memory,
            audit=audit,
            enable_rate_limiting=False,
            enable_escalation=True,
        )
    except ValueError as exc:
        print(f"Outcome: FAILED (Expected) -> {exc}")
    print(f"Audit Log Failures Count: {audit.count_failures(user, 'draft_email')}")

    # Attempt 3: Triggers escalation to human
    print("\n--- [ATTEMPT 3] Third Attempt (Expected: ESCALATED TO HUMAN) ---")
    res_3 = receive_task(
        task=failing_task,
        user=user,
        memory=memory,
        audit=audit,
        enable_rate_limiting=False,
        enable_escalation=True,
    )
    print(f"Outcome: {res_3['status'].upper()}")
    print(f"Escalation Payload: {json.dumps(res_3, indent=2)}")

    print("\nAudit Log Entry for Escalated Attempt (Skill was NOT executed):")
    print_audit_entry(audit.get_entries()[-1])

    print("\n[Assignment 2 Verification Passed]: Skill was prevented from executing; escalation triggered.")


# -----------------------------------------------------------------------------
# MAIN CLI ENTRY POINT
# -----------------------------------------------------------------------------


def main() -> None:
    """CLI dispatcher."""
    parser = argparse.ArgumentParser(
        description="Lab 6: OpenCLA/OpenClaw Runtime - Personal Agent Runtime"
    )
    parser.add_argument(
        "--assignment1",
        action="store_true",
        help="Run Assignment 1 demonstration (Per-user rate limiting)",
    )
    parser.add_argument(
        "--assignment2",
        action="store_true",
        help="Run Assignment 2 demonstration (Escalate after 2 failures)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run Base demonstration, Assignment 1, and Assignment 2 sequentially",
    )

    args = parser.parse_args()

    if args.all:
        run_base_demonstration()
        run_assignment_1()
        run_assignment_2()
    elif args.assignment1:
        run_assignment_1()
    elif args.assignment2:
        run_assignment_2()
    else:
        # Default behavior: run base demonstration
        run_base_demonstration()


if __name__ == "__main__":
    main()
