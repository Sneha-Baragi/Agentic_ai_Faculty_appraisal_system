"""Reusable Skill Specification: Research Summary Skill.

Course: Agentic AI (26ECAC401)
Lab: 3 - Skill Creation
Scenario: Research Summary Skill

This module defines the formal specification (`SKILL_SPEC`) for the Research Summary
Skill. The specification serves as an invariant, reusable contract governing how
technical articles are analyzed, how claims and evidence are extracted, how limitations
are surfaced, and how structured summaries are generated without domain bias or hallucination.
"""

from typing import Any, Dict, List

# Invariant placeholder used whenever required information is absent from the source
FALLBACK_NOT_STATED: str = "not stated in source"

SKILL_SPEC: Dict[str, Any] = {
    "skill_name": "research_summary",
    "version": "1.0.0",
    "description": (
        "A reusable analytical skill that parses technical research articles and produces "
        "a standardized research summary comprising main claim, supporting evidence, "
        "limitations, assumptions, undergraduate pedagogical takeaway, structured table, "
        "and a concise ~100-word narrative synthesis."
    ),
    "author": "Agentic AI Course (26ECAC401)",
    "target_audience": "Undergraduate Computer Science & Engineering Students",
    # -------------------------------------------------------------------------
    # OPERATIONAL EXTRACTION INSTRUCTIONS
    # -------------------------------------------------------------------------
    "instructions": {
        "article_title": (
            "Extract or verify the title of the article. If no title is supplied, "
            "generate a concise, descriptive title grounded strictly in the source subject matter."
        ),
        "main_claim": (
            "Identify the central thesis, primary performance metric, or primary finding "
            "asserted in the text. Look for assertive verbs (e.g., 'reduces', 'increased', 'improves', "
            "'achieved', 'guarantees'). If multiple competing claims are present across the text, "
            "evaluate the available empirical evidence for each claim and select the most "
            "evidence-supported claim rather than blindly selecting the first mentioned sentence."
        ),
        "supporting_evidence": (
            "Extract empirical data, quantitative measurements, sample sizes, benchmark datasets, "
            "monitoring instruments, or experimental duration validating the main claim. "
            "Ensure numerical figures and units (e.g., '41%', '200 held-out questions', 'two weeks') "
            "are faithfully captured. If no empirical validation or measurements are provided in the source, "
            f"strictly return '{FALLBACK_NOT_STATED}'."
        ),
        "limitations": (
            "Identify explicit boundary conditions, unmeasured scopes, dataset constraints, or generalizability "
            "hazards acknowledged in the article (e.g., 'single-domain dataset', 'did not include measurements "
            "from other campus buildings'). If no limitations are explicitly articulated in the text, "
            f"strictly return '{FALLBACK_NOT_STATED}'."
        ),
        "assumptions": (
            "Identify prerequisite conditions or operational contexts presumed to hold in the study "
            "(e.g., representative baseline, stationary traffic distributions). Only extract assumptions "
            f"that are directly corroborated by the text; otherwise return '{FALLBACK_NOT_STATED}'."
        ),
        "teaching_takeaway": (
            "Formulate an actionable, pedagogical lesson tailored for undergraduate computer science and "
            "engineering students. Connect the findings to core principles of empirical methodology, "
            "validation across operating environments, or critical appraisal of technical assertions."
        ),
        "structured_table": (
            "Format the extracted dimensions into a clean, markdown-compatible comparison table "
            "capturing Dimension, Extracted Content, and Source Grounding Status."
        ),
        "summary": (
            "Synthesize a coherent, objective narrative summary of approximately 100 words "
            "(target range: 85-120 words). The summary must logically connect context, claim, "
            "supporting evidence, acknowledged limitation, and the undergraduate takeaway."
        ),
    },
    # -------------------------------------------------------------------------
    # GOVERNANCE CONSTRAINTS AND ANTI-HALLUCINATION RULES
    # -------------------------------------------------------------------------
    "constraints": [
        "Constraint 1 (Anti-Fabrication): Do not invent, extrapolate, or manufacture numbers, "
        "percentages, benchmark datasets, participant counts, or durations not present in the source.",
        f"Constraint 2 (Explicit Fallback): If evidence, limitations, or assumptions are missing from "
        f"the source text, represent them strictly as '{FALLBACK_NOT_STATED}'. Never fill blanks with plausible assumptions.",
        "Constraint 3 (Epistemic Calibration): Do not represent uncertain, projected, or qualified claims "
        "(e.g., 'projected to cut', 'may not generalize') as proven universal facts.",
        "Constraint 4 (Schema Invariance): Every processed article must return the identical set of "
        "structured output keys regardless of topic, length, or completeness.",
        "Constraint 5 (Evidence-Driven Resolution): When competing claims exist, the agent must perform "
        "evidence scoring, select the best-supported claim, and transparently document the selection rationale.",
        "Constraint 6 (Pedagogical Grounding): Teaching takeaways must relate directly to the relationship "
        "between the extracted claim and its boundary limitations.",
    ],
    # -------------------------------------------------------------------------
    # REQUIRED OUTPUT CONTRACT SCHEMA
    # -------------------------------------------------------------------------
    "required_output_schema": [
        "article_title",
        "main_claim",
        "supporting_evidence",
        "limitations",
        "assumptions",
        "teaching_takeaway",
        "summary",
        "word_count_summary",
        "structured_table",
        "multiple_claims_detected",
        "competing_claims",
        "selection_rationale",
        "source_grounding_verified",
        "missing_fields",
    ],
    "fallback_placeholder": FALLBACK_NOT_STATED,
}

