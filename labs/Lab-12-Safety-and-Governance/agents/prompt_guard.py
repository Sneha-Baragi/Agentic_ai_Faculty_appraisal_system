"""Prompt Injection Defense & Input Guardrail Agent.

Inspects incoming prompts and claims text against adversarial injection attacks,
jailbreaks, privilege escalations, delimiter injections, and target manipulation.
Pure Python standard library only.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from models.schemas import GuardrailResult, ThreatLevel
from tools.sanitizers import sanitize_input_text

logger = logging.getLogger(__name__)


class PromptGuard:
    """Evaluates input prompts and appraisal submissions for adversarial manipulation."""

    # Directive override patterns (attempting to override system prompts)
    _DIRECTIVE_OVERRIDE_PATTERNS = [
        r"\bignore\s+(?:all\s+)?(?:(?:previous|prior|above|system|policy)\s+)*(?:instructions|guidelines|rules|prompts)\b",
        r"\bdisregard\s+(?:all\s+)?(?:(?:previous|prior|system|policy)\s+)*(?:guidelines|rules|instructions)\b",
        r"\bbypass\s+(?:all\s+)?(?:rules|restrictions|guardrails|safety|limits)\b",
        r"\boverride\s+(?:system|safety|admin)\s+(?:prompt|directives|controls)\b",
        r"\bforget\s+(?:your\s+)?(?:instructions|role|constraints)\b",
        r"\bnew\s+system\s+prompt\b",
        r"\bsystem\s+directive\s*:\s*ignore\b",
    ]

    # Role confusion / privilege escalation patterns
    _ROLE_CONFUSION_PATTERNS = [
        r"\byou\s+are\s+now\s+(?:an?\s+)?(?:unrestricted|root|sudo|admin|superadmin|god\s*mode)\b",
        r"\bsimulate\s+(?:sudo|root|administrator|admin\s+mode)\b",
        r"\bact\s+as\s+(?:root|unrestricted\s+ai|jailbroken\s+assistant|DAN)\b",
        r"\bswitch\s+role\s+to\s+admin(?:istrator)?\b",
        r"\bjailbreak\b",
        r"\bdeveloper\s+mode\s+(?:enabled|activated)\b",
        r"\benable\s+unrestricted\s+mode\b",
    ]

    # Delimiter / structure injection patterns
    _DELIMITER_INJECTION_PATTERNS = [
        r"-{3,}\s*BEGIN\s+(?:ADMIN|SYSTEM|OVERRIDE|ROOT)\b",
        r"<\s*(?:system|admin|override|control)\s*>",
        r"<\s*/\s*(?:system|user|assistant)\s*>",
        r"```\s*(?:json|system)\s*\{[^}]*\"role\"\s*:\s*\"admin\"",
        r"\[\s*SYSTEM\s*INSTRUCTION\s*\]",
        r"<!--\s*system:\s*override\s*-->",
    ]

    # Target manipulation patterns (forcing scores / outcomes)
    _TARGET_MANIPULATION_PATTERNS = [
        r"\b(?:award|assign|grant|give|set)\s+(?:100|full|maximum|max)\s+(?:api\s+)?(?:points|score|marks)\b",
        r"\bforce\s+(?:grade|score|rating)\s+(?:to\s+)?(?:A\+|100|maximum|exceptional)(?:\b|(?<=\+))",
        r"\bassign\s+100\s+api\s+points\b",
        r"\boverride\s+score\s+to\s+(?:100|max)\b",
        r"\bgrant\s+full\s+marks\s+without\s+verification\b",
        r"\bmark\s+(?:all\s+)?criteria\s+as\s+(?:passed|100%|complete)\b",
    ]

    # SQL / Command injection patterns
    _CODE_INJECTION_PATTERNS = [
        r"(?:;\s*DROP\s+TABLE\b|;\s*DELETE\s+FROM\b|UNION\s+SELECT\b|'\s*OR\s+'1'='1)",
        r"(?:__import__\s*\(\s*['\"]os['\"]\s*\)|subprocess\.Popen|exec\s*\(|eval\s*\()",
    ]

    def __init__(self, sanitize_inputs: bool = True) -> None:
        """Initialize PromptGuard and compile pattern sets.

        Args:
            sanitize_inputs: Whether to sanitize inputs before checking.
        """
        self.sanitize_inputs = sanitize_inputs
        self._compiled_directives = [
            re.compile(p, re.IGNORECASE) for p in self._DIRECTIVE_OVERRIDE_PATTERNS
        ]
        self._compiled_role_confusion = [
            re.compile(p, re.IGNORECASE) for p in self._ROLE_CONFUSION_PATTERNS
        ]
        self._compiled_delimiters = [
            re.compile(p, re.IGNORECASE) for p in self._DELIMITER_INJECTION_PATTERNS
        ]
        self._compiled_manipulations = [
            re.compile(p, re.IGNORECASE) for p in self._TARGET_MANIPULATION_PATTERNS
        ]
        self._compiled_injections = [
            re.compile(p, re.IGNORECASE) for p in self._CODE_INJECTION_PATTERNS
        ]

    def evaluate(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        """Evaluate input text against injection heuristics.

        Args:
            text: Input prompt, claims text, or user remarks.
            context: Optional contextual parameters (e.g. actor_id, role).

        Returns:
            GuardrailResult with allowed status, threat level, and violation details.
        """
        if not text or not text.strip():
            return GuardrailResult(
                allowed=True,
                threat_level=ThreatLevel.SAFE,
                violations=[],
                details={"matched_patterns": 0, "categories": []},
            )

        target_text = sanitize_input_text(text) if self.sanitize_inputs else text
        violations: list[str] = []
        categories: list[str] = []

        # Check directive overrides
        for regex in self._compiled_directives:
            match = regex.search(target_text)
            if match:
                violations.append(f"Directive override attempt detected: '{match.group(0)}'")
                categories.append("directive_override")
                break

        # Check role confusion
        for regex in self._compiled_role_confusion:
            match = regex.search(target_text)
            if match:
                violations.append(f"Role escalation/confusion attempt detected: '{match.group(0)}'")
                categories.append("role_confusion")
                break

        # Check delimiter injection
        for regex in self._compiled_delimiters:
            match = regex.search(target_text)
            if match:
                violations.append(f"Delimiter/Prompt injection structure detected: '{match.group(0)}'")
                categories.append("delimiter_injection")
                break

        # Check target manipulation
        for regex in self._compiled_manipulations:
            match = regex.search(target_text)
            if match:
                violations.append(f"Target score/grade manipulation detected: '{match.group(0)}'")
                categories.append("target_manipulation")
                break

        # Check code/SQL injection
        for regex in self._compiled_injections:
            match = regex.search(target_text)
            if match:
                violations.append(f"Suspicious executable/SQL injection detected: '{match.group(0)}'")
                categories.append("code_injection")
                break

        # Determine threat level and verdict
        if not violations:
            logger.debug("PromptGuard evaluation passed cleanly (SAFE).")
            return GuardrailResult(
                allowed=True,
                threat_level=ThreatLevel.SAFE,
                violations=[],
                details={"matched_patterns": 0, "categories": []},
            )

        logger.warning(
            "PromptGuard flagged %d violations (MALICIOUS). Violations: %s",
            len(violations),
            violations,
        )
        return GuardrailResult(
            allowed=False,
            threat_level=ThreatLevel.MALICIOUS,
            violations=violations,
            details={
                "matched_patterns": len(violations),
                "categories": categories,
            },
        )
