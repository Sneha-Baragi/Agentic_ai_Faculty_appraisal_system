"""PII Redactor Agent.

Detects and redacts sensitive Personally Identifiable Information (PII) including
phone numbers, email addresses, national IDs (Aadhaar, SSN), salary figures, and
student roll numbers.
Pure Python standard library only.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from models.schemas import PIIRedactionResult, PIIType

logger = logging.getLogger(__name__)


class PIIRedactor:
    """Identifies and masks sensitive PII in appraisal claims and academic submissions."""

    # Replacement tokens
    TOKEN_PHONE = "[REDACTED-PHONE]"
    TOKEN_EMAIL = "[REDACTED-EMAIL]"
    TOKEN_AADHAAR_SSN = "[REDACTED-AADHAAR-SSN]"
    TOKEN_SALARY = "[REDACTED-SALARY]"
    TOKEN_STUDENT_ID = "[REDACTED-STUDENT-ID]"

    def __init__(self) -> None:
        """Compile regular expression patterns for PII detection."""
        # 1. Emails: standard RFC 5322 approximation
        self._re_email = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        )

        # 2. Aadhaar: 12 digits grouped (4-4-4) with spaces or hyphens, or SSN (3-2-4)
        self._re_aadhaar = re.compile(
            r"\b(?:\d{4}[ -]\d{4}[ -]\d{4}|\b\d{12}\b)"
        )
        self._re_ssn = re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b"
        )

        # 3. Student Roll Numbers / USN:
        # e.g., 01FE23BCI054, 2BV21CS045, USN: 1MS19CS001, Roll No: CS-2023-01
        self._re_student_id = re.compile(
            r"\b(?:01FE\d{2}[A-Za-z]{3}\d{3}|\d[A-Za-z]{2}\d{2}[A-Za-z]{2}\d{3})\b|"
            r"\b(?:USN|Roll\s*(?:No\.?|Number)?)\s*[:#\-]?\s*([A-Za-z0-9\-]+)\b",
            re.IGNORECASE,
        )

        # 4. Salary / Financial figures:
        # e.g., INR 1,20,000, Rs. 85,000, ₹12,00,000, $5,000, 15 LPA, package of 12 Lakhs
        self._re_salary_explicit = re.compile(
            r"(?:salary|ctc|package|stipend|compensation)\s*(?:of|is|:)?\s*"
            r"(?:INR|Rs\.?|₹|\$)?\s*[\d,]+(?:\.\d+)?\s*(?:LPA|lpa|Lakhs?|lakhs?|Cr)?",
            re.IGNORECASE,
        )
        self._re_currency_amount = re.compile(
            r"(?:INR|Rs\.?|₹|\$)\s*[\d,]+(?:\.\d+)?",
            re.IGNORECASE,
        )
        self._re_lpa_amount = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:LPA|lpa|Lakhs?|lakhs?|Crores?|crores?)\b"
        )

        # 5. Phone numbers:
        # Indian format: +91 9876543210, +91-98765-43210, 09876543210, 9876543210 (10 digits starting 6-9)
        # International format: +1-800-555-0199, (555) 123-4567
        self._re_phone_in = re.compile(
            r"(?:\+91[\s-]?)?(?:0)?[6-9]\d{4}[\s-]?\d{5}\b"
        )
        self._re_phone_intl = re.compile(
            r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        )

    def redact(self, text: str) -> PIIRedactionResult:
        """Scan text and redact all detected sensitive PII entities.

        Args:
            text: Input text containing potential personal information.

        Returns:
            PIIRedactionResult containing original, redacted text, and counts.
        """
        if not text:
            return PIIRedactionResult(
                original_text="",
                redacted_text="",
                redactions_count=0,
                detected_types=[],
            )

        original_text = text
        redacted = text
        detected_types: list[str] = []
        total_redactions = 0

        # 1. Emails
        emails = self._re_email.findall(redacted)
        if emails:
            redacted = self._re_email.sub(self.TOKEN_EMAIL, redacted)
            detected_types.append(PIIType.EMAIL.value)
            total_redactions += len(emails)

        # 2. National IDs (Aadhaar & SSN)
        aadhaar_matches = self._re_aadhaar.findall(redacted)
        if aadhaar_matches:
            redacted = self._re_aadhaar.sub(self.TOKEN_AADHAAR_SSN, redacted)
            if PIIType.AADHAAR_SSN.value not in detected_types:
                detected_types.append(PIIType.AADHAAR_SSN.value)
            total_redactions += len(aadhaar_matches)

        ssn_matches = self._re_ssn.findall(redacted)
        if ssn_matches:
            redacted = self._re_ssn.sub(self.TOKEN_AADHAAR_SSN, redacted)
            if PIIType.AADHAAR_SSN.value not in detected_types:
                detected_types.append(PIIType.AADHAAR_SSN.value)
            total_redactions += len(ssn_matches)

        # 3. Student Roll / USN
        student_matches = self._re_student_id.findall(redacted)
        if student_matches:
            redacted = self._re_student_id.sub(self.TOKEN_STUDENT_ID, redacted)
            detected_types.append(PIIType.STUDENT_ID.value)
            total_redactions += len(student_matches)

        # 4. Salary / Financial
        salary_exp_matches = self._re_salary_explicit.findall(redacted)
        if salary_exp_matches:
            redacted = self._re_salary_explicit.sub(self.TOKEN_SALARY, redacted)
            if PIIType.SALARY.value not in detected_types:
                detected_types.append(PIIType.SALARY.value)
            total_redactions += len(salary_exp_matches)

        lpa_matches = self._re_lpa_amount.findall(redacted)
        if lpa_matches:
            redacted = self._re_lpa_amount.sub(self.TOKEN_SALARY, redacted)
            if PIIType.SALARY.value not in detected_types:
                detected_types.append(PIIType.SALARY.value)
            total_redactions += len(lpa_matches)

        currency_matches = self._re_currency_amount.findall(redacted)
        if currency_matches:
            redacted = self._re_currency_amount.sub(self.TOKEN_SALARY, redacted)
            if PIIType.SALARY.value not in detected_types:
                detected_types.append(PIIType.SALARY.value)
            total_redactions += len(currency_matches)

        # 5. Phone numbers (run after numeric IDs/financials to avoid partial collisions)
        phone_matches = self._re_phone_in.findall(redacted)
        if phone_matches:
            redacted = self._re_phone_in.sub(self.TOKEN_PHONE, redacted)
            if PIIType.PHONE.value not in detected_types:
                detected_types.append(PIIType.PHONE.value)
            total_redactions += len(phone_matches)

        phone_intl_matches = self._re_phone_intl.findall(redacted)
        if phone_intl_matches:
            redacted = self._re_phone_intl.sub(self.TOKEN_PHONE, redacted)
            if PIIType.PHONE.value not in detected_types:
                detected_types.append(PIIType.PHONE.value)
            total_redactions += len(phone_intl_matches)

        logger.debug(
            "PII redaction complete: %d items redacted across categories: %s",
            total_redactions,
            detected_types,
        )

        return PIIRedactionResult(
            original_text=original_text,
            redacted_text=redacted,
            redactions_count=total_redactions,
            detected_types=detected_types,
        )
