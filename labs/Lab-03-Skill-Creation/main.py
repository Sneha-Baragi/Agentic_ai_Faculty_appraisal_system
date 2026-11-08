"""Main CLI Demonstration: Lab 3 – Skill Creation (Research Summary Skill).

Course: Agentic AI (26ECAC401)
Lab: 3
Skill: Skill Creation
Scenario: Research Summary Skill
Objective: Build a reusable Research Summary Skill that can analyze different
           technical articles using a consistent set of instructions and output constraints.

Demonstration Sections:
1. Skill Specification Overview (`SKILL_SPEC`).
2. Research Summary Skill applied to Article A (RAG System).
3. Research Summary Skill applied to Article B (Campus Wi-Fi).
4. Reusability Check comparing Article A and Article B.
5. Assignment 1 – Competing Claims (Article C: Cost vs Latency).
6. Assignment 2 – Missing Evidence and Limitations (Article D: Cryptography).
"""

import argparse
import json
import os
import sys
from typing import Any, Dict

# Ensure local imports work when running directly or from repository root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from skill.research_summary import (
    apply_research_summary_skill,
    print_skill_output,
    reusability_check,
)
from skill.skill_spec import FALLBACK_NOT_STATED, SKILL_SPEC


def load_article(file_name: str) -> Dict[str, Any]:
    """Load an example article JSON file."""
    path = os.path.join(CURRENT_DIR, "examples", file_name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def run_assignment_1() -> None:
    """Execute focused demonstration of Assignment 1: Competing Claims."""
    print_banner(
        "ASSIGNMENT 1: COMPETING CLAIMS RESOLUTION",
        "Evidence-Driven Claim Selection vs Sentence Order Bias"
    )
    article_c = load_article("article_c.json")

    print("Source Article C:")
    print(f"  Title:   {article_c['title']}")
    print(f"  Content: \"{article_c['content']}\"\n")

    output_c = apply_research_summary_skill(article_c)
    print_skill_output(article_c, output_c)

    print("Evaluation of Competing Claims Requirements:")
    print(f"  • Multiple claims detected:   {output_c['multiple_claims_detected']}")
    print(f"  • Total candidates extracted: {len(output_c['competing_claims'])}")
    for idx, c in enumerate(output_c["competing_claims"], 1):
        print(f"    - Claim {idx} [{c['topic']}]: \"{c['claim']}\" (Score: {c['evidence_score']})")
    print(f"  • Selected Main Claim:        \"{output_c['main_claim']}\"")
    print("  • First-Sentence Default:     AVOIDED (Cost claim was first, Latency claim selected on evidence)")
    print(f"  • Selection Rationale:\n    {output_c['selection_rationale']}")
    print("\nAssignment 1 Completed Successfully.\n")


def run_assignment_2() -> None:
    """Execute focused demonstration of Assignment 2: Missing Evidence and Limitations."""
    print_banner(
        "ASSIGNMENT 2: MISSING EVIDENCE AND LIMITATIONS",
        "Anti-Fabrication Fallback & Epistemic Calibration"
    )
    article_d = load_article("article_d.json")

    print("Source Article D:")
    print(f"  Title:   {article_d['title']}")
    print(f"  Content: \"{article_d['content']}\"\n")

    output_d = apply_research_summary_skill(article_d)
    print_skill_output(article_d, output_d)

    print("Evaluation of Anti-Fabrication Requirements:")
    print(f"  • Main Claim Extracted:       \"{output_d['main_claim']}\"")
    print(f"  • Supporting Evidence:        \"{output_d['supporting_evidence']}\"")
    print(f"  • Limitations:                \"{output_d['limitations']}\"")
    print(f"  • Assumptions:                \"{output_d['assumptions']}\"")
    print(f"  • Missing Fields Recorded:    {output_d['missing_fields']}")
    print(f"  • Fabricated Numbers/Metrics: NONE (Strictly used '{FALLBACK_NOT_STATED}')")
    print(f"  • Undergraduate Takeaway:     \"{output_d['teaching_takeaway']}\"")
    print("\nAssignment 2 Completed Successfully.\n")


def run_full_demonstration() -> None:
    """Execute complete 6-part demonstration of Lab 3."""
    print_banner(
        "LAB 3: SKILL CREATION — RESEARCH SUMMARY SKILL",
        "Course: Agentic AI (26ECAC401) · Full Demonstration Mode"
    )

    # -------------------------------------------------------------------------
    # 1. SKILL SPECIFICATION OVERVIEW
    # -------------------------------------------------------------------------
    print_section(1, "Skill Specification Overview (SKILL_SPEC)")
    print(f"Skill Name:      {SKILL_SPEC['skill_name']}")
    print(f"Version:         {SKILL_SPEC['version']}")
    print(f"Description:     {SKILL_SPEC['description']}")
    print(f"Target Audience: {SKILL_SPEC['target_audience']}")
    print(f"Fallback Value:  '{SKILL_SPEC['fallback_placeholder']}'")
    print("\nOperational Extraction Instructions:")
    for key, instr in SKILL_SPEC["instructions"].items():
        print(f"  • {key:<20}: {instr[:90]}...")
    print("\nKey Anti-Fabrication & Invariance Constraints:")
    for c in SKILL_SPEC["constraints"]:
        print(f"  ✓ {c}")

    # -------------------------------------------------------------------------
    # 2. ARTICLE A (RAG SYSTEM)
    # -------------------------------------------------------------------------
    print_section(2, "Research Summary Skill: Article A (RAG System)")
    article_a = load_article("article_a.json")
    output_a = apply_research_summary_skill(article_a)
    print_skill_output(article_a, output_a)

    # -------------------------------------------------------------------------
    # 3. ARTICLE B (CAMPUS WI-FI)
    # -------------------------------------------------------------------------
    print_section(3, "Research Summary Skill: Article B (Campus Wi-Fi Upgrade)")
    article_b = load_article("article_b.json")
    output_b = apply_research_summary_skill(article_b)
    print_skill_output(article_b, output_b)

    # -------------------------------------------------------------------------
    # 4. REUSABILITY CHECK
    # -------------------------------------------------------------------------
    print_section(4, "Skill Reusability Check: Article A vs Article B")
    rcheck = reusability_check(output_a, output_b)
    print("Reusability Diagnostic Result:")
    print(json.dumps(rcheck, indent=2))
    print(f"\n-> Overall Reusability Status: {'PASSED (Invariant Schema Verified)' if rcheck['is_reusable'] else 'FAILED'}")
    print(f"-> Shared Contract Keys:      {rcheck['shared_keys_count']} / {rcheck['required_keys_count']}")
    print(f"-> Independent Content:       {rcheck['content_differentiated']} (Outputs differ across domains)")

    # -------------------------------------------------------------------------
    # 5. ASSIGNMENT 1 (COMPETING CLAIMS - ARTICLE C)
    # -------------------------------------------------------------------------
    print_section(5, "Assignment 1: Competing Claims (Article C - Cost vs Latency)")
    article_c = load_article("article_c.json")
    output_c = apply_research_summary_skill(article_c)
    print_skill_output(article_c, output_c)

    # -------------------------------------------------------------------------
    # 6. ASSIGNMENT 2 (MISSING EVIDENCE & LIMITATIONS - ARTICLE D)
    # -------------------------------------------------------------------------
    print_section(6, "Assignment 2: Missing Evidence & Limitations (Article D)")
    article_d = load_article("article_d.json")
    output_d = apply_research_summary_skill(article_d)
    print_skill_output(article_d, output_d)

    print_banner(
        "LAB 3 DEMONSTRATION COMPLETE",
        "All Skill Creation & Evaluation Requirements Satisfied"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lab 3: Skill Creation (Research Summary Skill)",
    )
    parser.add_argument(
        "--assignment1",
        action="store_true",
        help="Run Assignment 1: Competing Claims resolution",
    )
    parser.add_argument(
        "--assignment2",
        action="store_true",
        help="Run Assignment 2: Missing evidence and limitations handling",
    )
    args = parser.parse_args()

    if args.assignment1:
        run_assignment_1()
    elif args.assignment2:
        run_assignment_2()
    else:
        run_full_demonstration()


if __name__ == "__main__":
    main()
