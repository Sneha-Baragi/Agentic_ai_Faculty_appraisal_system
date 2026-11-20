#!/usr/bin/env python3
"""Interactive CLI Runner for Lab 9: Deep Research Agent.

Course: Agentic AI (26ECAC401)
Lab 9: Deep Research Agent – AI Topic Briefing

Executes the five-stage workflow:
Research Question -> Search -> Extract -> Compare -> Synthesize
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

from agent.deep_research_agent import DeepResearchAgent


def run_scenario(
    agent: DeepResearchAgent,
    topic_id: str,
    research_question: str,
    source_ids: list[str],
    save_reports: bool = True,
) -> None:
    print("\n" + "=" * 80)
    print(f"RUNNING SCENARIO: {topic_id}")
    print(f"Research Question: {research_question}")
    print(f"Sources Included: {', '.join(source_ids)}")
    print("=" * 80)

    report = agent.conduct_research(
        research_question=research_question, source_ids=source_ids
    )

    md = agent.format_markdown(report)
    print("\n" + md)

    if save_reports:
        md_file, json_file = agent.save_report(report)
        print(f"\n[Artifact Generated] Markdown: {md_file.name}")
        print(f"[Artifact Generated] JSON:     {json_file.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lab 9 Deep Research Agent – AI Topic Briefing"
    )
    parser.add_argument(
        "--scenario",
        choices=["all", "topic_01", "topic_02", "topic_03"],
        default="all",
        help="Scenario to execute (default: all)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save markdown/JSON reports to disk",
    )
    args = parser.parse_args()

    examples_path = LAB_ROOT / "examples" / "sample_topics.json"
    with open(examples_path, "r", encoding="utf-8") as f:
        topics = json.load(f)

    agent = DeepResearchAgent()
    save_reports = not args.no_save

    if args.scenario == "all":
        print("\n=== EXECUTING ALL LAB 9 DEMONSTRATION SCENARIOS ===")
        for t in topics:
            run_scenario(
                agent=agent,
                topic_id=t["topic_id"],
                research_question=t["research_question"],
                source_ids=t["include_sources"],
                save_reports=save_reports,
            )
    else:
        matched = [t for t in topics if t["topic_id"] == args.scenario]
        if matched:
            t = matched[0]
            run_scenario(
                agent=agent,
                topic_id=t["topic_id"],
                research_question=t["research_question"],
                source_ids=t["include_sources"],
                save_reports=save_reports,
            )
        else:
            print(f"Scenario {args.scenario} not found.")


if __name__ == "__main__":
    main()
