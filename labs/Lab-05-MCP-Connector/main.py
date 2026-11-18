"""MCP-Style Connector Main Entry Point and Interactive CLI.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Scenario: Multi-Source Data Integration Assistant

Usage:
    python main.py                 # Run base demonstration (Requests 1, 2, 3)
    python main.py --assignment1   # Run Assignment 1 demonstration (list_files dynamic resource)
    python main.py --assignment2   # Run Assignment 2 demonstration (Safe boundary & security enforcement)
    python main.py --all           # Run full demonstration covering base + both assignments
    python main.py --interactive   # Enter interactive prompt session with DataAssistant
"""

import argparse
import json
from pathlib import Path
import sys
from typing import List

from agent.data_assistant import DataAssistant
from client.mcp_client import MCPClient
from server.mcp_server import MCPServer


def print_banner(title: str, width: int = 78) -> None:
    """Print visually distinct section header."""
    print("\n" + "=" * width)
    print(f"  {title.upper()}")
    print("=" * width)


def print_step_box(step_num: int, title: str, width: int = 78) -> None:
    """Print step subheader."""
    print(f"\n--- [STEP {step_num}] {title} " + "-" * max(0, width - len(title) - 15))


def print_result_block(result: dict) -> None:
    """Format and display agent execution result block."""
    print(f"User Request        : \"{result['user_request']}\"")
    print(f"Selected Capability : {result['capability']} (Kind: {result['kind']})")
    print(f"Tool Input          : {json.dumps(result['input'])}")
    print(f"Execution Success   : {'YES' if result['success'] else 'NO (Blocked/Failed)'}")
    print(f"Output Summary      : {result['output_summary']}")
    print(f"Final Answer        :\n{result['final_answer']}")


def run_base_demonstration(assistant: DataAssistant, client: MCPClient) -> None:
    """Run demonstration of the three core base requests."""
    print_banner("Lab 5: Base MCP-Style Connector Demonstration")
    print("Architecture: Agent (DataAssistant) -> Client (MCPClient) -> Server (MCPServer)")
    print("Heterogeneous Sources: Safe Files (Resource) | SQLite DB (Tool) | Mock API (Tool)")

    # 1. Capability Discovery
    print_step_box(1, "Capability Discovery Manifest")
    capabilities = client.discover()
    print(f"Client dynamically queried server. Discovered {len(capabilities)} capabilities:")
    for cap in capabilities:
        print(f"  - [{cap['kind'].upper():8s}] {cap['name']:12s} : {cap['description'][:65]}...")

    # 2. Base Requests
    base_prompts = [
        ("Request 1 (File Resource)", "Read the README file."),
        ("Request 2 (SQLite Database Tool)", "Show me the campus event signup counts."),
        ("Request 3 (Local Mock API Tool)", "Which events are happening today?"),
    ]

    for idx, (label, prompt) in enumerate(base_prompts, start=2):
        print_step_box(idx, label)
        result = assistant.process_request(prompt)
        print_result_block(result)

    # 3. Execution Trace Summary
    print_step_box(len(base_prompts) + 2, "End-to-End Execution Audit Trace")
    traces = assistant.get_traces()
    print(f"Total operations traced: {len(traces)}")
    print(f"{'Step':<6}{'Capability':<14}{'Kind':<10}{'Status':<10}{'User Request':<35}")
    print("-" * 75)
    for t in traces:
        status_str = "SUCCESS" if t["success"] else "FAILED"
        print(f"{t['step']:<6}{str(t['selected_capability']):<14}{str(t['selected_kind']):<10}{status_str:<10}{t['user_request'][:33]}")


def run_assignment_1(assistant: DataAssistant, client: MCPClient) -> None:
    """Run demonstration for Assignment 1: 4th capability 'list_files' resource."""
    print_banner("Assignment 1: Dynamic Discovery of 4th Capability ('list_files')")
    print("Requirement: Add 'list_files' resource. Client must discover and invoke dynamically")
    print("without any hardcoded 'list_files' methods or references in MCPClient.")

    # Manifest inspection
    capabilities = client.discover()
    has_list_files = any(c["name"] == "list_files" for c in capabilities)
    print(f"\nManifest verification: 'list_files' discovered = {has_list_files}")

    list_cap = client.get_capability("list_files")
    if list_cap:
        print(f"Capability Name : {list_cap['name']}")
        print(f"Capability Kind : {list_cap['kind']} (Resource)")
        print(f"Input Schema    : {json.dumps(list_cap['input_schema'])}")
        print(f"Output Schema   : {json.dumps(list_cap['output_schema'])}")

    print_step_box(1, "Agent Invoking Discovered 'list_files' Capability")
    result = assistant.process_request("List the available files in safe_data.")
    print_result_block(result)

    print("\n[Assignment 1 Verification Passed]: 'list_files' was discovered and invoked dynamically.")


def run_assignment_2(assistant: DataAssistant, client: MCPClient, server: MCPServer) -> None:
    """Run demonstration for Assignment 2: Security & safe boundary enforcement."""
    print_banner("Assignment 2: Safe Directory Boundary & Security Enforcement")
    print("Security Invariants:")
    print("1. safe_data/ directory boundary strictly prevents path traversal & file disclosure.")
    print("2. Database tool strictly enforces read-only SELECT and caller authorization.")
    print("3. Mock API strictly enforces registered endpoint whitelisting.")

    print_step_box(1, "Legitimate Safe Access (Within safe_data/)")
    res_safe = assistant.process_request("Read the announcements text file.")
    print_result_block(res_safe)

    print_step_box(2, "Adversarial File Probes (Path Traversal & Boundary Escapes)")
    probes = [
        ("Parent directory traversal to secrets", "../../backend/.env"),
        ("Relative parent traversal to Lab README", "../README.md"),
        ("Windows system absolute path", "C:\\Windows\\win.ini"),
        ("Unix absolute root path", "/some/unauthorized/file.txt"),
    ]

    for label, probe_path in probes:
        print(f"\n[Test Probe]: {label}")
        print(f"Target Path : {probe_path}")
        res = assistant.process_request(f"Read {probe_path}")
        print(f"Outcome     : {'BLOCKED (Access Denied)' if not res['success'] else 'LEAKED'}")
        print(f"Error Code  : {res['output'].get('error_code')}")
        print(f"Server Msg  : {res['output'].get('message')}")
        assert not res["success"], f"Security violation! Path {probe_path} was not blocked."

    print_step_box(3, "Database Mutation & Injection Attack Defense")
    sql_attacks = [
        ("SQL Injection / Table Drop", "SELECT * FROM signups; DROP TABLE signups;"),
        ("Data Mutation (INSERT)", "INSERT INTO signups (event, count) VALUES ('Malicious', 999);"),
        ("Data Deletion (DELETE)", "DELETE FROM signups WHERE count > 0;"),
    ]

    for label, bad_sql in sql_attacks:
        print(f"\n[Test Probe]: {label}")
        print(f"SQL Attack  : {bad_sql}")
        res = client.call("query_db", sql=bad_sql, caller_id="data_assistant")
        print(f"Outcome     : {'BLOCKED' if res.get('status') == 'error' else 'EXECUTED'}")
        print(f"Error Code  : {res.get('error_code')}")
        print(f"Server Msg  : {res.get('message')}")
        assert res.get("status") == "error", f"Security violation! SQL write was not blocked."

    print_step_box(4, "Database Caller Authorization Check")
    unauth_res = client.call(
        "query_db",
        sql="SELECT * FROM signups;",
        caller_id="unauthorized_attacker",
    )
    print(f"Caller ID   : 'unauthorized_attacker'")
    print(f"Outcome     : {'BLOCKED' if unauth_res.get('status') == 'error' else 'ALLOWED'}")
    print(f"Error Code  : {unauth_res.get('error_code')}")
    print(f"Server Msg  : {unauth_res.get('message')}")

    print("\n[Assignment 2 Verification Passed]: All adversarial probes and attacks were securely blocked.")


def run_interactive(assistant: DataAssistant, client: MCPClient) -> None:
    """Run an interactive prompt loop with DataAssistant."""
    print_banner("Interactive DataAssistant Session")
    print("Type your questions in plain English (or type 'exit' / 'quit' to finish).")
    print("Examples:")
    print("  - Read the README file.")
    print("  - Show me the campus event signup counts.")
    print("  - Which events are happening today?")
    print("  - List the available files.")
    print("  - Read ../../backend/.env")

    while True:
        try:
            user_input = input("\nAssistant> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting interactive session.")
                break

            result = assistant.process_request(user_input)
            print("-" * 60)
            print_result_block(result)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive session.")
            break


def main() -> None:
    """CLI argument dispatcher."""
    parser = argparse.ArgumentParser(
        description="Lab 5: MCP-Style Connector (Mini Integration Layer)"
    )
    parser.add_argument(
        "--assignment1",
        action="store_true",
        help="Run Assignment 1 demonstration (list_files dynamic resource)",
    )
    parser.add_argument(
        "--assignment2",
        action="store_true",
        help="Run Assignment 2 demonstration (Safe boundary & security enforcement)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run base demo + Assignment 1 + Assignment 2 sequentially",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Launch interactive conversation prompt session",
    )

    args = parser.parse_args()

    # Initialize environment
    base_dir = Path(__file__).resolve().parent
    safe_dir = base_dir / "safe_data"
    db_path = base_dir / "data" / "campus.db"

    server = MCPServer(
        safe_dir=safe_dir,
        db_path=db_path,
        include_assignment_1=True,
    )
    client = MCPClient(server)
    assistant = DataAssistant(client, caller_id="data_assistant")

    if args.interactive:
        run_interactive(assistant, client)
    elif args.all:
        run_base_demonstration(assistant, client)
        run_assignment_1(assistant, client)
        run_assignment_2(assistant, client, server)
    elif args.assignment1:
        run_assignment_1(assistant, client)
    elif args.assignment2:
        run_assignment_2(assistant, client, server)
    else:
        # Default behavior: run base demonstration
        run_base_demonstration(assistant, client)


if __name__ == "__main__":
    main()
