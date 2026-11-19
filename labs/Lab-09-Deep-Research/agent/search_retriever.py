"""Search and Retrieval module for Lab 9 Deep Research Agent.

Loads structured source fixtures locally and filters them based on research queries.
Strictly distinguishes mock demonstration fixtures from live external retrieval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models.schemas import QualityTier, SourceDocument, TIER_WEIGHTS


class SearchRetriever:
    """Retrieves source documents from local verified fixtures.
    
    IMPORTANT: Zero network requests are made. All fixtures are explicitly
    tagged as mock/synthetic demonstration data to maintain academic integrity.
    """

    def __init__(self, data_path: str | Path | None = None) -> None:
        if data_path is None:
            data_path = Path(__file__).resolve().parent.parent / "data" / "sources.json"
        self.data_path = Path(data_path)
        self._corpus: dict[str, SourceDocument] = {}
        self._load_corpus()

    def _load_corpus(self) -> None:
        if not self.data_path.exists():
            raise FileNotFoundError(f"Source corpus not found at {self.data_path}")
        with open(self.data_path, "r", encoding="utf-8") as f:
            raw_sources = json.load(f)

        for item in raw_sources:
            tier_enum = QualityTier(item["tier"])
            tier_weight = TIER_WEIGHTS.get(tier_enum, item.get("tier_weight", 0.5))
            doc = SourceDocument(
                source_id=item["source_id"],
                title=item["title"],
                date=item["date"],
                author=item.get("author") or "not stated in source",
                organization=item.get("organization") or "not stated in source",
                source_type=item["source_type"],
                tier=tier_enum,
                tier_weight=tier_weight,
                content=item["content"],
                key_claim=item["key_claim"],
                evidence=item["evidence"],
                limitation=item["limitation"],
                relevance=item["relevance"],
                is_synthetic=item.get("is_synthetic", True),
                verification_status=item.get(
                    "verification_status", "mock_demonstration_fixture"
                ),
                source_origin=item.get("source_origin", "local_fixture"),
            )
            self._corpus[doc.source_id] = doc

    def get_all_sources(self) -> list[SourceDocument]:
        """Return all available source documents in the fixture corpus."""
        return list(self._corpus.values())

    def get_by_ids(self, source_ids: list[str]) -> list[SourceDocument]:
        """Retrieve specific source documents by their unique identifiers (e.g., ['S1', 'S2'])."""
        res: list[SourceDocument] = []
        for sid in source_ids:
            if sid in self._corpus:
                res.append(self._corpus[sid])
        return res

    def search(self, query: str, limit: int = 10) -> list[SourceDocument]:
        """Perform deterministic keyword filtering across title, key claim, and content."""
        query_terms = [q.lower() for q in query.split() if len(q) > 2]
        if not query_terms:
            return list(self._corpus.values())[:limit]

        scored: list[tuple[int, SourceDocument]] = []
        for doc in self._corpus.values():
            searchable_text = f"{doc.title} {doc.key_claim} {doc.content} {doc.relevance}".lower()
            score = sum(1 for term in query_terms if term in searchable_text)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: (x[0], x[1].tier_weight), reverse=True)
        return [doc for _, doc in scored[:limit]]
