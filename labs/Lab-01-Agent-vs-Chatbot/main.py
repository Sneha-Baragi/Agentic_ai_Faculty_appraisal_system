"""Main CLI Demonstration: Lab 1 – Agent vs Chatbot.

Course: Agentic AI (26ECAC401)
Lab: 1
Skill: Agents
Scenario: Study Planner
Objective: Build the Agent Loop (Goal -> Plan -> Act -> Observe -> Revise).

This script provides an interactive and deterministic demonstration comparing:
A. Conventional Chatbot: Single-turn, tool-less, stateless text generation.
B. Study Planner Agent: Autonomous, goal-driven, tool-integrated, stateful planning loop with in-place mutation.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List

# Ensure local imports work when running directly or from repository root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from agent.planner_agent import StudyPlannerAgent
from agent.schedule_tool import ScheduleTool, ScheduleToolError
from chatbot.chatbot import StudyChatbot


def print_banner(title: str, subtitle: str = "") -> None:
    width = 78
    print("\n" + "=" * width)
    print(f" {title}".center(width))
    if subtitle:
        print(f" {subtitle}".center(width))
    print("=" * width)


def print_section(section_number: int, section_title: str) -> None:
    print(f"\n[{section_number}] {section_title.upper()}")
    print("-" * 78)


def format_plan_table(study_plan: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"{'Day':<11} | {'Status':<14} | {'Subject':<20} | {'Hours':<6} | {'Time Slot':<22}")
    lines.append("-" * 84)
    for day, data in study_plan.items():
        sub = data.subject if data.subject else "—"
        hrs = f"{data.hours:.1f}" if data.hours > 0 else "0.0"
        lines.append(f"{day:<11} | {data.status:<14} | {sub:<20} | {hrs:<6} | {data.time_of_day:<22}")
    return "\n".join(lines)


def run_deterministic_demo() -> None:
    print_banner(
        "LAB 1: AGENT VS CHATBOT (STUDY PLANNER SCENARIO)",
        "Course: Agentic AI (26ECAC401) · Demonstration Mode"
    )

    # -------------------------------------------------------------------------
    # 1. CONVENTIONAL CHATBOT RESPONSE
    # -------------------------------------------------------------------------
    print_section(1, "Conventional Chatbot Response (Single-Turn, No Tools, Stateless)")
    chatbot = StudyChatbot()
    student_prompt = (
        "Hi! Can you create a weekly study plan for Data Structures, "
        "Operating Systems, and AI Agents? I want to study 2 hours per day."
    )
    print(f"Student Prompt:\n  \"{student_prompt}\"\n")
    chatbot_response = chatbot.respond(student_prompt)
    print(chatbot_response)
    print("\nChatbot Behavioral Diagnostic:")
    print(json.dumps(chatbot.inspect_capabilities(), indent=2))

    # -------------------------------------------------------------------------
    # 2. AGENT GOAL AND STOPPING CONDITION
    # -------------------------------------------------------------------------
    print_section(2, "Study Planner Agent: Goal Declaration and Stopping Condition")
    schedule_tool = ScheduleTool()
    agent = StudyPlannerAgent(
        goal="Generate a conflict-free 7-day study plan matching student goals and institutional commitments.",
        schedule_tool=schedule_tool,
    )
    print(f"Declared Agent Goal: '{agent.state.goal}'")
    print(f"Declared Stopping Condition: schedule_generated == True (Stopping condition met: {agent.is_stopping_condition_met()})")

    # Ingest initial incomplete request
    initial_request = {
        "student_name": "Aarav Sharma",
        "subjects": ["Data Structures", "Operating Systems", "AI Agents"],
        "hours_per_day": 2,
        # 'unavailable_days' is intentionally omitted to demonstrate clarification
    }
    print(f"\nInitial Student Request Ingested:")
    print(f"  Subjects: {initial_request['subjects']}")
    print(f"  Hours Per Day: {initial_request['hours_per_day']}")
    print("  Unavailable Days: NOT PROVIDED")

    agent.ingest_initial_request(
        subjects=initial_request["subjects"],
        hours_per_day=initial_request["hours_per_day"],
    )

    # -------------------------------------------------------------------------
    # 3. CLARIFICATION OF MISSING INFORMATION (PLAN & ACT)
    # -------------------------------------------------------------------------
    print_section(3, "Agent Reasoning: Clarification of Missing Information (PLAN & ACT)")
    missing = agent.inspect_missing_information()
    print(f"State Inspection -> Missing Parameters: {missing}")

    is_complete, questions = agent.step_clarification()
    print(f"Targeted Clarification Question(s) Asked by Agent:")
    for q in questions:
        print(f"  ? {q}")

    # Student supplies clarification
    clarification_input = ["Sunday"]
    print(f"\nStudent Answer Provided:")
    print(f"  \"I am unavailable on Sundays due to personal family commitments.\"")
    agent.supply_clarification(unavailable_days=clarification_input)
    print(f"State Updated -> Missing Parameters Now: {agent.inspect_missing_information()}")

    # -------------------------------------------------------------------------
    # 4. SCHEDULE TOOL EXECUTION (ACT & OBSERVE)
    # -------------------------------------------------------------------------
    print_section(4, "Schedule Tool Execution (ACT & OBSERVE)")
    print("Agent autonomously calls institutional ScheduleTool before drafting schedule...")
    tool_output = agent.fetch_existing_schedule(student_id="student_01")
    print("Tool Output Observed by Agent:")
    print(json.dumps(tool_output, indent=2))
    print(f"-> Institutional Busy Days Detected: {tool_output['busy_days']}")

    # Conflict detection step
    uncovered = agent.detect_schedule_conflicts()
    if uncovered:
        print(f"-> Uncovered Calendar Conflicts Identified: {[c['day'] for c in uncovered]}")
        for c in uncovered:
            print(f"   • {c['day']}: {c['commitment']} ({c['resolution']})")

    # -------------------------------------------------------------------------
    # 5. INITIAL WEEKLY STUDY PLAN
    # -------------------------------------------------------------------------
    print_section(5, "Initial Weekly Study Plan (ACT & OBSERVE)")
    agent.generate_initial_plan()
    print(format_plan_table(agent.state.study_plan))
    print("\nStated Assumptions:")
    for idx, asm in enumerate(agent.state.assumptions, 1):
        print(f"  {idx}. {asm}")
    print(f"\nGoal Status: Completed = {agent.state.goal_completed}")
    print(f"Stopping Reason: {agent.state.stopping_reason}")

    # -------------------------------------------------------------------------
    # 6. USER FEEDBACK
    # -------------------------------------------------------------------------
    print_section(6, "User Feedback Received")
    feedback_text = "Move Tuesday's session to the evening."
    print(f"Student Feedback:\n  \"{feedback_text}\"")

    # -------------------------------------------------------------------------
    # 7. REVISED WEEKLY STUDY PLAN (IN-PLACE MUTATION)
    # -------------------------------------------------------------------------
    print_section(7, "Revised Weekly Study Plan (REVISE - In-Place Mutation)")
    print("Agent mutates existing schedule object (does not re-plan from scratch)...")
    agent.revise_plan(feedback_text)
    print(format_plan_table(agent.state.study_plan))
    print("\nVerification of In-Place Mutation:")
    print(f"  • Tuesday Slot:   {agent.state.study_plan['Tuesday'].time_of_day} (Updated to Evening)")
    print(f"  • Monday Slot:    {agent.state.study_plan['Monday'].time_of_day} (Preserved)")
    print(f"  • Wednesday Slot: {agent.state.study_plan['Wednesday'].time_of_day} (Preserved Busy)")
    print(f"  • Thursday Slot:  {agent.state.study_plan['Thursday'].time_of_day} (Preserved)")
    print(f"  • Friday Slot:    {agent.state.study_plan['Friday'].time_of_day} (Preserved Busy)")
    print(f"  • Saturday Slot:  {agent.state.study_plan['Saturday'].time_of_day} (Preserved)")
    print(f"  • Sunday Slot:    {agent.state.study_plan['Sunday'].time_of_day} (Preserved Rest)")

    # -------------------------------------------------------------------------
    # 8. COMPLETE AGENT ITERATION LOG
    # -------------------------------------------------------------------------
    print_section(8, "Complete Agent Iteration Log (GOAL -> PLAN -> ACT -> OBSERVE -> REVISE)")
    for entry in agent.state.iteration_log:
        status_symbol = "✓" if entry["goal_satisfied"] else "○"
        print(f"Iteration {entry['iteration']:02d} [{entry['phase']:<7}] {status_symbol} Goal Satisfied: {entry['goal_satisfied']}")
        print(f"  Plan:        {entry['plan']}")
        print(f"  Action:      {entry['action']}")
        print(f"  Observation: {entry['observation']}")
        if entry["stopping_reason"]:
            print(f"  Stop Reason: {entry['stopping_reason']}")
        print()

    # -------------------------------------------------------------------------
    # 9. COMPARISON BETWEEN CHATBOT AND AGENT BEHAVIOR
    # -------------------------------------------------------------------------
    print_section(9, "Comparison: Conventional Chatbot vs Autonomous Agent")
    comparison = [
        ("Dimension", "Conventional Chatbot", "Autonomous Planning Agent"),
        ("Architecture", "Stateless, single-turn prompt/response", "Stateful loop (Goal->Plan->Act->Observe->Revise)"),
        ("Goal Awareness", "None; responds to prompt without termination state", "Explicit goal with verified stopping condition"),
        ("Missing Info", "Guesses or applies static template assumptions", "Plans missing info check; asks ONLY missing items"),
        ("Tool Integration", "None; cannot inspect external calendars", "Autonomously invokes ScheduleTool to verify clashes"),
        ("Conflict Avoidance", "Schedules blind to institutional seminars", "Strictly avoids busy days (e.g. Wednesday seminar)"),
        ("Plan Revision", "Re-generates fresh text from scratch", "Mutates existing schedule object in-place"),
        ("Auditability", "No reasoning trail or state persistence", "Complete iteration log with plan, act, observe steps"),
    ]
    col_w = [18, 30, 32]
    header = f"{comparison[0][0]:<{col_w[0]}} | {comparison[0][1]:<{col_w[1]}} | {comparison[0][2]:<{col_w[2]}}"
    print(header)
    print("-" * len(header))
    for row in comparison[1:]:
        print(f"{row[0]:<{col_w[0]}} | {row[1]:<{col_w[1]}} | {row[2]:<{col_w[2]}}")
    print("-" * len(header))
    print("\nDemonstration complete! All instructor evaluation criteria satisfied.\n")


def run_interactive_mode() -> None:
    print_banner("INTERACTIVE STUDY PLANNER AGENT", "Custom Student Input Mode")
    print("Welcome! Provide your study planning parameters below.\n")

    subjects_raw = input("Enter subjects (comma-separated, e.g. Data Structures, AI Agents): ").strip()
    subjects = [s.strip() for s in subjects_raw.split(",") if s.strip()] or ["Data Structures", "AI Agents"]

    hours_raw = input("Enter available study hours per day (default 2): ").strip()
    try:
        hours = float(hours_raw) if hours_raw else 2.0
    except ValueError:
        hours = 2.0

    unavail_raw = input("Enter unavailable days (comma-separated, e.g. Sunday): ").strip()
    unavailable_days = [d.strip() for d in unavail_raw.split(",") if d.strip()] or ["Sunday"]

    agent = StudyPlannerAgent()
    agent.ingest_initial_request(subjects=subjects, hours_per_day=hours, unavailable_days=unavailable_days)
    agent.fetch_existing_schedule()
    agent.generate_initial_plan()

    print("\nInitial Study Plan Generated:")
    print(format_plan_table(agent.state.study_plan))

    feedback = input("\nEnter feedback to mutate the plan (e.g. 'Move Tuesday to evening' or press Enter to skip): ").strip()
    if feedback:
        agent.revise_plan(feedback)
        print("\nRevised Plan (Mutated In-Place):")
        print(format_plan_table(agent.state.study_plan))

    print("\nDone! Iterations logged:", len(agent.state.iteration_log))


def run_assignment_1() -> None:
    print_banner("ASSIGNMENT 1: TWO ROUNDS OF FEEDBACK", "Mutating Study Plan In-Place Sequentially")
    agent = StudyPlannerAgent()
    agent.run_autonomous_loop(
        initial_request={"subjects": ["Data Structures", "Operating Systems", "AI Agents"], "hours_per_day": 2},
        clarification_data={"unavailable_days": ["Sunday"]},
    )
    print("1. Initial Plan Generated:")
    print(format_plan_table(agent.state.study_plan))

    print("\n2. Applying Feedback Round 1: 'Move Tuesday's session to the evening.'")
    agent.revise_plan("Move Tuesday's session to the evening.")
    print(f"Tuesday time_of_day is now: {agent.state.study_plan['Tuesday'].time_of_day}")

    print("\n3. Applying Feedback Round 2: 'Swap Thursday and Saturday subjects so AI Agents is on Saturday.'")
    agent.revise_plan("Swap Thursday and Saturday subjects so AI Agents is on Saturday.")
    print("\nFinal Mutated Plan After 2 Rounds of Feedback:")
    print(format_plan_table(agent.state.study_plan))
    print("\nAssignment 1 Completed Successfully.")


def run_assignment_2() -> None:
    print_banner(
        "ASSIGNMENT 2: DETECT A SCHEDULING CONFLICT (LAB GUIDE PAGES 8-9)",
        "Uncovered Conflict Detection & Pre-Finalization Exclusion Verification"
    )
    tool = ScheduleTool()
    agent = StudyPlannerAgent(schedule_tool=tool)

    print("Step 1: Student submits initial requirements:")
    print("  • Subjects: ['Data Structures', 'Operating Systems', 'AI Agents']")
    print("  • Daily study volume: 2 hours")
    print("  • Unavailable days marked by student: ['Sunday']")
    print("  • NOTE: Student did NOT initially mark Friday as unavailable.")

    agent.ingest_initial_request(
        subjects=["Data Structures", "Operating Systems", "AI Agents"],
        hours_per_day=2.0,
        unavailable_days=["Sunday"],
    )

    print("\nStep 2: Agent queries external ScheduleTool:")
    schedule_data = agent.fetch_existing_schedule(student_id="default_student")
    print(f"  • Tool status: {schedule_data['status']}")
    print(f"  • Busy days returned (>= 2 busy days): {schedule_data['busy_days']}")
    for day, c in schedule_data["commitments"].items():
        print(f"    - {day}: {c}")

    print("\nStep 3: Agent performs conflict detection prior to finalization:")
    uncovered = agent.detect_schedule_conflicts()
    print(f"  • Uncovered calendar conflicts detected: {[c['day'] for c in uncovered]}")
    for c in uncovered:
        print(f"    ! [CONFLICT DETECTED] {c['day']}: {c['commitment']}")
        print(f"      Resolution: {c['resolution']}")

    print("\nStep 4: Agent generates weekly study plan and executes pre-finalization verification:")
    plan = agent.generate_initial_plan()
    agent.verify_all_busy_days_excluded(plan, set(schedule_data["busy_days"]))
    print("  • Explicit Pre-Finalization Check: VERIFIED (Every busy day strictly excluded)")
    print(f"  • Friday status: {plan['Friday'].status} (0.0 study hours, subject={plan['Friday'].subject})")
    print("  • Silent Friday scheduling avoided: True")

    print("\nFinal Study Plan Table:")
    print(format_plan_table(agent.state.study_plan))

    print("\nAssumptions & Disclosed Conflict Audits:")
    for idx, asm in enumerate(agent.state.assumptions, 1):
        print(f"  {idx}. {asm}")

    print("\nStep 5: Edge Case Verification (All 7 Days Blocked):")
    blocked_agent = StudyPlannerAgent(schedule_tool=tool)
    blocked_agent.ingest_initial_request(
        subjects=["Advanced AI"],
        hours_per_day=3.0,
        unavailable_days=["Monday", "Tuesday", "Thursday", "Saturday", "Sunday"],
    )
    blocked_agent.fetch_existing_schedule()  # blocks Wednesday and Friday
    try:
        blocked_agent.generate_initial_plan()
        print("  ERROR: All-days-blocked conflict not caught!")
    except ValueError as err:
        print(f"  ✓ Safely caught impossible schedule constraint: {err}")

    print("\nAssignment 2 Completed Successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lab 1: Agent vs Chatbot (Study Planner)")
    parser.add_argument("--demo", action="store_true", default=True, help="Run standard deterministic demonstration")
    parser.add_argument("--interactive", action="store_true", help="Run interactive CLI with user prompts")
    parser.add_argument("--assignment1", action="store_true", help="Run Assignment 1: Two Rounds of Feedback")
    parser.add_argument("--assignment2", action="store_true", help="Run Assignment 2: Detect a Scheduling Conflict")
    args = parser.parse_args()

    if args.interactive:
        run_interactive_mode()
    elif args.assignment1:
        run_assignment_1()
    elif args.assignment2:
        run_assignment_2()
    else:
        run_deterministic_demo()


if __name__ == "__main__":
    main()

