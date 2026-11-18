"""Agents package for Lab 8 - Parallel Swarm."""

from agents.administrative_agent import AdministrativeDataCollectionAgent
from agents.api_calculation_agent import APICalculationAgent
from agents.coordinator import AURACoordinator
from agents.evidence_validation_agent import EvidenceValidationAgent
from agents.human_review_agent import HumanReviewAgent
from agents.report_generation_agent import ReportGenerationAgent
from agents.research_agent import ResearchDataCollectionAgent
from agents.teaching_agent import TeachingDataCollectionAgent

__all__ = [
    "AdministrativeDataCollectionAgent",
    "APICalculationAgent",
    "AURACoordinator",
    "EvidenceValidationAgent",
    "HumanReviewAgent",
    "ReportGenerationAgent",
    "ResearchDataCollectionAgent",
    "TeachingDataCollectionAgent",
]
