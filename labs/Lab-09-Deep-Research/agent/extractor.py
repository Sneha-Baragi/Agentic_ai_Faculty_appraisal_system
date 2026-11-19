"""Evidence Extraction module for Lab 9 Deep Research Agent.

Extracts the six required fields from source documents:
1. Source Date
2. Author / Organization
3. Key Claim
4. Evidence
5. Limitation
6. Relevance
"""

from __future__ import annotations

from typing import Any

from models.schemas import EvidenceRow, SourceDocument


class EvidenceExtractor:
    """Extracts structured evidence rows from source documents without data fabrication."""

    def extract_row(self, doc: SourceDocument) -> EvidenceRow:
        """Extract a six-field structured EvidenceRow from a SourceDocument."""
        # Clean and validate date
        source_date = doc.date.strip() if doc.date else "not stated in source"

        # Combine author and organization accurately
        author = doc.author.strip() if doc.author else "not stated in source"
        org = doc.organization.strip() if doc.organization else "not stated in source"

        if author != "not stated in source" and org != "not stated in source":
            author_org = f"{author} ({org})"
        elif author != "not stated in source":
            author_org = author
        elif org != "not stated in source":
            author_org = org
        else:
            author_org = "not stated in source"

        key_claim = doc.key_claim.strip() if doc.key_claim else "not stated in source"
        evidence = doc.evidence.strip() if doc.evidence else "not stated in source"
        limitation = doc.limitation.strip() if doc.limitation else "not stated in source"
        relevance = doc.relevance.strip() if doc.relevance else "not stated in source"

        return EvidenceRow(
            source_id=doc.source_id,
            source_date=source_date,
            author_organization=author_org,
            key_claim=key_claim,
            evidence=evidence,
            limitation=limitation,
            relevance=relevance,
            tier=doc.tier.value,
            tier_weight=doc.tier_weight,
        )

    def extract_table(self, docs: list[SourceDocument]) -> list[EvidenceRow]:
        """Extract evidence rows across a collection of source documents."""
        return [self.extract_row(d) for d in docs]
