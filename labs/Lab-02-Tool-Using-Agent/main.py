"""
main.py – Lab 2: Tool-Using Agent (Campus Data Assistant)
=========================================================
Agentic AI (26ECAC401) | Lab 2

This script provides a deterministic CLI demonstration of all three
official reference questions, plus the two assignment extensions.

Usage
-----
Run from the labs/Lab-02-Tool-Using-Agent/ directory:

    python main.py              # deterministic demo (all reference questions)
    python main.py --interactive  # demo + interactive question mode

No external API keys or dependencies are required.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap

# ---------------------------------------------------------------------------
# Path setup – make Lab-02 root importable from anywhere.
# ---------------------------------------------------------------------------
_LAB_ROOT = os.path.dirname(os.path.abspath(__file__))
if _LAB_ROOT not in sys.path:
    sys.path.insert(0, _LAB_ROOT)

from agent.campus_assistant import CampusDataAssistant


# ===========================================================================
# Display helpers
# ===========================================================================

_SEPARATOR = "═" * 72
_THIN_LINE = "─" * 72


def _banner(text: str) -> None:
    print(f"\n{_SEPARATOR}")
    print(f"  {text}")
    print(_SEPARATOR)


def _section(title: str) -> None:
    print(f"\n  {'▶ ' + title}")
    print(f"  {_THIN_LINE}")


def _indent(text: str, prefix: str = "    ") -> None:
    for line in text.splitlines():
        print(prefix + line)


def _print_response(label: str, response: dict) -> None:
    """Pretty-print one agent response."""
    _banner(f"Question {label}")

    print(f"\n  ❓ QUESTION")
    _indent(response["question"])

    print(f"\n  🧠 REASONING")
    _indent(response.get("reasoning", "(none)"))

    trace = response.get("trace", [])
    if trace:
        print(f"\n  🔧 TOOL CALLS ({len(trace)} call{'s' if len(trace) != 1 else ''})")
        for i, entry in enumerate(trace, 1):
            print(f"\n    [{i}] Tool   : {entry['tool']}")
            print(f"        Reason  : {entry['reason']}")
            print(f"        Input   : {json.dumps(entry['inputs'], indent=None)}")
            output_str = json.dumps(entry['output'])
            # Truncate very long outputs for readability
            if len(output_str) > 300:
                output_str = output_str[:297] + "..."
            print(f"        Output  : {output_str}")
            print(f"        Status  : {entry['status'].upper()}")
            print(f"        Time    : {entry['timestamp']}")
    else:
        print(f"\n  🔧 TOOL CALLS: none (no tool needed for this question)")

    print(f"\n  ✅ FINAL ANSWER")
    _indent(response["final_answer"])


def _print_full_trace(all_responses: list[tuple[str, dict]]) -> None:
    """Print a consolidated execution trace across all questions."""
    _banner("COMPLETE EXECUTION TRACE (All Questions)")
    for label, response in all_responses:
        print(f"\n  ── Question {label}: {response['question'][:60]}")
        trace = response.get("trace", [])
        if not trace:
            print("     (No tool calls – handled without tools)")
            continue
        for entry in trace:
            print(f"     tool={entry['tool']}  status={entry['status']}")
            print(f"       reason : {entry['reason'][:80]}")
            print(f"       input  : {json.dumps(entry['inputs'])}")
            out = json.dumps(entry['output'])
            print(f"       output : {out[:120]}{'...' if len(out) > 120 else ''}")


# ===========================================================================
# Deterministic demonstration
# ===========================================================================

def run_demo() -> None:
    """Run all three official reference questions plus Assignment extensions."""

    agent = CampusDataAssistant()
    all_responses: list[tuple[str, dict]] = []

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    print("\n" + "█" * 72)
    print("█" + " " * 70 + "█")
    print("█   LAB 2 – TOOL-USING AGENT  │  Campus Data Assistant           █")
    print("█   Course: Agentic AI (26ECAC401)                               █")
    print("█   Tools: calculator • csv_reader • events_api • notifier       █")
    print("█" + " " * 70 + "█")
    print("█" * 72)

    # -----------------------------------------------------------------------
    # Q1 – Sign-up total and average
    # -----------------------------------------------------------------------
    q1 = agent.answer(
        "How many students signed up across all events in the dataset, and what's the average per event?"
    )
    all_responses.append(("1", q1))
    _print_response("1  –  Sign-Up Total & Average", q1)

    # -----------------------------------------------------------------------
    # Q2 – Hackathon Kickoff location and date
    # -----------------------------------------------------------------------
    q2 = agent.answer("Where and when is the Hackathon Kickoff?")
    all_responses.append(("2", q2))
    _print_response("2  –  Hackathon Kickoff Event Info", q2)

    # -----------------------------------------------------------------------
    # Q3 – Capstone Expo (missing metadata)
    # -----------------------------------------------------------------------
    q3 = agent.answer("Where and when is the Capstone Expo?")
    all_responses.append(("3", q3))
    _print_response("3  –  Capstone Expo (Missing Metadata)", q3)

    # -----------------------------------------------------------------------
    # Assignment 1 – Low-turnout notification demo
    # (Demonstrated by temporarily raising the threshold above the actual
    #  average so the notification path is always exercised in the demo.)
    # -----------------------------------------------------------------------
    _banner("ASSIGNMENT 1  –  Low-Turnout Notification Tool")
    print("""
  Assignment 1 adds a 'send_notification' tool that is called when the
  computed average falls below a threshold (default: 10 sign-ups).

  The current dataset average is 12.33, which is ABOVE the threshold, so
  the notification tool is NOT triggered for the standard data.

  To demonstrate the notification path, we raise the threshold to 15 (above
  the actual average of 12.33), which forces the notification to be drafted.
""")

    agent_a1 = CampusDataAssistant()
    agent_a1.LOW_TURNOUT_THRESHOLD = 15.0  # raised above 12.33 to trigger the notification demo
    q_a1 = agent_a1.answer(
        "How many students signed up across all events in the dataset, and what's the average per event?"
    )
    all_responses.append(("A1", q_a1))

    trace_a1 = q_a1.get("trace", [])
    notify_calls = [e for e in trace_a1 if e["tool"] == "send_notification"]
    if notify_calls:
        entry = notify_calls[0]
        print(f"  ✉  Notification drafted (threshold = {agent_a1.LOW_TURNOUT_THRESHOLD}):")
        _indent(entry["output"].get("message", "(no message)"))
    else:
        print("  ℹ  Notification not triggered (average is above the threshold).")

    # -----------------------------------------------------------------------
    # Assignment 2 – Technical events average
    # -----------------------------------------------------------------------
    q_a2 = agent.answer("What's the average sign-up for technical events only?")
    all_responses.append(("A2", q_a2))
    _print_response("ASSIGNMENT 2  –  Technical Events Average", q_a2)

    # -----------------------------------------------------------------------
    # No-tool question demo
    # -----------------------------------------------------------------------
    q_nt = agent.answer("Hello, what can you help me with?")
    all_responses.append(("NT", q_nt))
    _print_response("NO-TOOL  –  Greeting (no tool needed)", q_nt)

    # -----------------------------------------------------------------------
    # Complete execution trace
    # -----------------------------------------------------------------------
    _print_full_trace(all_responses)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    _banner("SUMMARY")
    print("""
  Reference question results:
    Q1  Total sign-ups  : 74   (tool chain: read_csv → calculator(sum))
    Q1  Average          : 12.33 (tool chain: read_csv → calculator(average))
    Q1  Number of events : 6     (across all events in the dataset)
    Q2  Hackathon Kickoff: Innovation Lab on 2026-07-05
    Q3  Capstone Expo    : No metadata available (honest response)

  Tool registry:
    ┌─────────────────────┬─────────────────────────────────────────────────┐
    │ Tool name           │ When called                                     │
    ├─────────────────────┼─────────────────────────────────────────────────┤
    │ read_csv            │ Sign-up count / category questions              │
    │ calculator          │ Any arithmetic (sum or average)                 │
    │ get_event_info      │ Event date / location questions                 │
    │ send_notification   │ Average below threshold (Assignment 1)          │
    └─────────────────────┴─────────────────────────────────────────────────┘

  Run tests:
    python -m unittest discover -s tests -v
""")


# ===========================================================================
# Interactive mode
# ===========================================================================

def run_interactive() -> None:
    """Allow the user to type free-form questions."""
    _banner("INTERACTIVE MODE  –  Campus Data Assistant")
    print("""
  Type a question and press Enter. Type 'quit' or 'exit' to leave.

  Example questions:
    How many students signed up across all events in the dataset?
    Where and when is the Hackathon Kickoff?
    Where and when is the Capstone Expo?
    What's the average sign-up for technical events only?
    Hello, what can you help me with?
""")
    agent = CampusDataAssistant()
    while True:
        try:
            question = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break
        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("  Goodbye!")
            break
        response = agent.answer(question)
        print(f"\n  Agent: {response['final_answer']}\n")
        trace = response.get("trace", [])
        if trace:
            print(f"  [Trace: {len(trace)} tool call(s) – "
                  f"{', '.join(e['tool'] for e in trace)}]")
        print()


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    interactive = "--interactive" in sys.argv or "-i" in sys.argv
    run_demo()
    if interactive:
        run_interactive()

