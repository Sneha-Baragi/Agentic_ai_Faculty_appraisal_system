"""Data models and schemas for Lab 9: Deep Research Agent.

Defines strongly typed structures for source fixtures, structured evidence rows,
cross-source agreements, genuine contradictions, evidence gaps, quality-weighting
metrics, and the final five-stage topic briefing report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class QualityTier(str, Enum):
    """Evidence quality tiers per official Agentic AI Lab Guide."""
    TIER_1 = "Tier 1: Peer-reviewed research"
    TIER_2 = "Tier 2: Independent benchmark"
    TIER_3 = "Tier 3: Vendor engineering blog"


TIER_WEIGHTS: dict[QualityTier, float] = {
    QualityTier.TIER_1: 1.0,
    QualityTier.TIER_2: 0.7,
    QualityTier.TIER_3: 0.4,
}


@dataclass
class SourceDocument:
    """Represents a retrieved source document.
    
    All demonstration sources are explicitly marked with synthetic/mock flags.
    S4 is explicitly designated as a synthetic demonstration fixture not independently verified.
    """
    source_id: str
    title: str
    date: str
    author: str
    organization: str
    source_type: str
    tier: QualityTier
    tier_weight: float
    content: str
    key_claim: str
    evidence: str
    limitation: str
    relevance: str
    is_synthetic: bool = True
    verification_status: str = "mock_demonstration_fixture"
    source_origin: str = "local_fixture"

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["tier"] = self.tier.value
        return res


@dataclass
class EvidenceRow:
    """Six-field structured evidence extraction per official Lab 9 requirements."""
    source_id: str
    source_date: str
    author_organization: str
    key_claim: str
    evidence: str
    limitation: str
    relevance: str
    tier: str
    tier_weight: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgreementRecord:
    """Consensus finding shared across two or more independent sources."""
    topic: str
    supporting_sources: list[str]
    consensus_statement: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConflictRecord:
    """Direct contradiction between sources (distinguished from an evidence gap).
    
    Per Assignment 1, genuine conflicts between S1 and S4 are analyzed with
    methodology, domain, and dataset-size root causes.
    """
    source_a: str
    source_b: str
    metric: str
    claim_a: str
    claim_b: str
    conflict_type: str  # "GENUINE_CONTRADICTION" vs "EVIDENCE_GAP"
    contradiction_reasons: dict[str, str]
    severity: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceGap:
    """Missing or unstated information in a source."""
    source_id: str
    gap_type: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationMetrics:
    """Quality-weighted synthesis metrics.
    
    POLICY DISCLAIMER:
    These formulas represent project-defined demonstration policies for agentic
    reasoning and evaluation. They are not official UGC or regulatory formulas,
    nor do they represent mathematically validated probabilities.
    """
    eqi: float
    severity_max: float
    reliability_score: float
    status: str
    human_review_required: bool
    policy_disclaimer: str = (
        "Demonstration Policy Disclaimer: EQI and Reliability metrics are project-defined "
        "heuristic demonstration policies for agentic evaluation, not official mathematical "
        "probabilities or regulatory standards."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BriefingReport:
    """Complete 5-stage AI Topic Briefing artifact."""
    research_question: str
    source_list: list[dict[str, Any]]
    evidence_table: list[dict[str, Any]]
    agreements: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    evidence_gaps: list[dict[str, Any]]
    evaluation_metrics: dict[str, Any]
    executive_summary: str
    recommended_next_questions: list[str]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
