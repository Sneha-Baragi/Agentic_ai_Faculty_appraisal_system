"""Deep Research Agent Orchestrator for Lab 9.

Implements the official five-stage workflow:
Research Question -> Search -> Extract -> Compare -> Synthesize

Produces structured BriefingReport artifacts and formatted Markdown / JSON outputs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.comparator import EvidenceComparator
from agent.extractor import EvidenceExtractor
from agent.search_retriever import SearchRetriever
from agent.synthesizer import EvidenceSynthesizer
from models.schemas import BriefingReport, SourceDocument


class DeepResearchAgent:
    """Master agent coordinating the five-stage deep research and evidence synthesis workflow."""

    def __init__(self, data_path: str | Path | None = None) -> None:
        self.retriever = SearchRetriever(data_path=data_path)
        self.extractor = EvidenceExtractor()
        self.comparator = EvidenceComparator()
        self.synthesizer = EvidenceSynthesizer()

    def conduct_research(
        self,
        research_question: str,
        source_ids: list[str] | None = None,
        search_query: str | None = None,
    ) -> BriefingReport:
        """Execute the five-stage research workflow."""
        # Stage 1 & 2: Search & Retrieval
        if source_ids:
            docs = self.retriever.get_by_ids(source_ids)
        elif search_query:
            docs = self.retriever.search(search_query)
        else:
            docs = self.retriever.get_all_sources()

        # Stage 3: Extraction
        evidence_rows = self.extractor.extract_table(docs)

        # Stage 4: Cross-Source Comparison
        agreements, conflicts, gaps = self.comparator.compare(evidence_rows)

        # Stage 5: Quality-Weighted Synthesis
        metrics = self.synthesizer.compute_metrics(evidence_rows, conflicts)
        summary = self.synthesizer.generate_executive_summary(
            research_question, evidence_rows, agreements, conflicts, gaps, metrics
        )
        next_questions = self.synthesizer.generate_recommended_next_questions(
            evidence_rows, conflicts
        )

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return BriefingReport(
            research_question=research_question,
            source_list=[d.to_dict() for d in docs],
            evidence_table=[r.to_dict() for r in evidence_rows],
            agreements=[a.to_dict() for a in agreements],
            contradictions=[c.to_dict() for c in conflicts],
            evidence_gaps=[g.to_dict() for g in gaps],
            evaluation_metrics=metrics.to_dict(),
            executive_summary=summary,
            recommended_next_questions=next_questions,
            generated_at=now_iso,
        )

    def format_markdown(self, report: BriefingReport) -> str:
        """Render a readable GitHub Flavored Markdown document from a BriefingReport."""
        lines: list[str] = []
        lines.append(f"# AI Topic Briefing: {report.research_question}")
        lines.append(f"\n*Generated at:* `{report.generated_at}`")
        lines.append("\n---\n")

        # Executive Summary
        lines.append("## 1. Executive Summary\n")
        lines.append(report.executive_summary)
        lines.append("\n---\n")

        # Six-Field Evidence Table
        lines.append("## 2. Six-Field Evidence Comparison Table\n")
        lines.append(
            "| Source ID | Tier & Weight | Date | Author / Organization | Key Claim | Evidence | Limitation | Relevance |"
        )
        lines.append(
            "|:---:|:---:|:---:|:---|:---|:---|:---|:---|"
        )
        for row in report.evidence_table:
            sid = row["source_id"]
            tier_info = f"{row['tier'].split(':')[0]} ({row['tier_weight']})"
            date = row["source_date"]
            author = row["author_organization"]
            claim = row["key_claim"]
            ev = row["evidence"]
            lim = row["limitation"]
            rel = row["relevance"]
            lines.append(
                f"| **{sid}** | {tier_info} | {date} | {author} | {claim} | {ev} | {lim} | {rel} |"
            )
        lines.append("\n---\n")

        # Cross-Source Analysis: Agreements
        lines.append("## 3. Cross-Source Analysis\n")
        lines.append("### 3.1 Agreements & Consensuses\n")
        if report.agreements:
            for i, ag in enumerate(report.agreements, 1):
                sources_str = ", ".join(f"`[{s}]`" for s in ag["supporting_sources"])
                lines.append(f"- **{ag['topic']}** (Sources: {sources_str}): {ag['consensus_statement']}")
        else:
            lines.append("- *No multi-source agreements detected.*")
        lines.append("")

        # Genuine Contradictions (Assignment 1)
        lines.append("### 3.2 Genuine Contradictions (Assignment 1)\n")
        if report.contradictions:
            for cf in report.contradictions:
                lines.append(f"- **Conflict:** `[{cf['source_a']}]` vs `[{cf['source_b']}]` on *{cf['metric']}*")
                lines.append(f"  - **`[{cf['source_a']}]` Claim:** {cf['claim_a']}")
                lines.append(f"  - **`[{cf['source_b']}]` Claim:** {cf['claim_b']}")
                lines.append(f"  - **Conflict Type:** `{cf['conflict_type']}` (Distinguished from an evidence gap)")
                lines.append("  - **Methodological Root Causes:**")
                for cause, explanation in cf["contradiction_reasons"].items():
                    lines.append(f"    - *{cause.replace('_', ' ').title()}:* {explanation}")
                lines.append(f"  - **Contradiction Severity:** `{cf['severity']}` (Tier 1 vs Tier 1 conflict)")
        else:
            lines.append("- *Zero direct contradictions identified.*")
        lines.append("")

        # Evidence Gaps
        lines.append("### 3.3 Evidence Gaps\n")
        if report.evidence_gaps:
            for gap in report.evidence_gaps:
                lines.append(f"- **`[{gap['source_id']}]` {gap['gap_type']}:** {gap['description']}")
        else:
            lines.append("- *No evidence gaps logged.*")
        lines.append("\n---\n")

        # Quality-Weighted Evaluation (Assignment 2)
        metrics = report.evaluation_metrics
        lines.append("## 4. Evidence-Quality Tiering & Evaluation (Assignment 2)\n")
        lines.append(f"- **Corpus Evidence Quality Index (EQI):** `{metrics['eqi']} / 1.0`")
        lines.append(f"- **Maximum Contradiction Severity:** `{metrics['severity_max']}`")
        lines.append(f"- **Synthesis Reliability Score:** `{round(metrics['reliability_score'] * 100, 2)}%`")
        lines.append(f"- **Synthesis Status:** `{metrics['status']}`")
        lines.append(f"- **Human-in-the-Loop Review Flag:** `{'MANDATORY' if metrics['human_review_required'] else 'OPTIONAL'}`")
        lines.append(f"\n> [!NOTE]\n> {metrics['policy_disclaimer']}\n")
        lines.append("---\n")

        # Recommended Next Questions
        lines.append("## 5. Recommended Next Questions\n")
        for i, q in enumerate(report.recommended_next_questions, 1):
            lines.append(f"{i}. {q}")
        lines.append("")

        return "\n".join(lines)

    def save_report(
        self, report: BriefingReport, output_dir: str | Path | None = None
    ) -> tuple[Path, Path]:
        """Save report as markdown and JSON artifacts in the reports directory."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "reports"
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in report.research_question[:30]).strip("_")

        md_file = out_path / f"briefing_{slug}_{timestamp}.md"
        json_file = out_path / f"briefing_{slug}_{timestamp}.json"

        md_content = self.format_markdown(report)
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        return md_file, json_file
