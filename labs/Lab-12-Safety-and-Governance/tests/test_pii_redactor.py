"""Unit tests for PIIRedactor agent.

Tests detection and masking of phone numbers, emails, Aadhaar/SSN, salary figures,
and student roll numbers.
"""
from __future__ import annotations

import unittest
from pathlib import Path
import sys

_LAB_ROOT = Path(__file__).resolve().parent.parent
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from agents.pii_redactor import PIIRedactor
from models.schemas import PIIType


class TestPIIRedactor(unittest.TestCase):
    """Test suite for PII detection and redaction."""

    def setUp(self) -> None:
        self.redactor = PIIRedactor()

    def test_clean_text_no_redaction(self) -> None:
        """Text without sensitive PII remains unmodified."""
        text = "Conducted workshops on distributed computing and cloud security."
        res = self.redactor.redact(text)
        self.assertEqual(res.original_text, text)
        self.assertEqual(res.redacted_text, text)
        self.assertEqual(res.redactions_count, 0)
        self.assertEqual(len(res.detected_types), 0)

    def test_email_redaction(self) -> None:
        """Emails must be replaced with [REDACTED-EMAIL]."""
        text = "Contact Dr. Kulkarni at anita.kulkarni@institution.ac.in or test.user@gmail.com for details."
        res = self.redactor.redact(text)
        self.assertNotIn("anita.kulkarni@institution.ac.in", res.redacted_text)
        self.assertNotIn("test.user@gmail.com", res.redacted_text)
        self.assertIn(PIIRedactor.TOKEN_EMAIL, res.redacted_text)
        self.assertEqual(res.redactions_count, 2)
        self.assertIn(PIIType.EMAIL.value, res.detected_types)

    def test_phone_number_redaction(self) -> None:
        """Indian and international phone numbers must be replaced with [REDACTED-PHONE]."""
        text = (
            "Reach out to +91 9845012345 or +91-91234-56789. "
            "Alternate number: 9876543210. US partner: +1 (555) 234-5678."
        )
        res = self.redactor.redact(text)
        self.assertNotIn("+91 9845012345", res.redacted_text)
        self.assertNotIn("9876543210", res.redacted_text)
        self.assertIn(PIIRedactor.TOKEN_PHONE, res.redacted_text)
        self.assertGreaterEqual(res.redactions_count, 3)
        self.assertIn(PIIType.PHONE.value, res.detected_types)

    def test_aadhaar_and_ssn_redaction(self) -> None:
        """Aadhaar (4-4-4) and SSN (3-2-4) must be replaced with [REDACTED-AADHAAR-SSN]."""
        text = "Faculty Aadhaar: 4532 8901 2345. Exchange visitor SSN: 123-45-6789."
        res = self.redactor.redact(text)
        self.assertNotIn("4532 8901 2345", res.redacted_text)
        self.assertNotIn("123-45-6789", res.redacted_text)
        self.assertIn(PIIRedactor.TOKEN_AADHAAR_SSN, res.redacted_text)
        self.assertEqual(res.redactions_count, 2)
        self.assertIn(PIIType.AADHAAR_SSN.value, res.detected_types)

    def test_salary_and_financial_redaction(self) -> None:
        """Salary expressions like INR 1,20,000, 15 LPA, Rs. 85,000 must be masked."""
        text = (
            "Annual salary of 15 LPA with consultancy fee of INR 1,20,000 "
            "and overseas grant of $5,000."
        )
        res = self.redactor.redact(text)
        self.assertNotIn("15 LPA", res.redacted_text)
        self.assertNotIn("INR 1,20,000", res.redacted_text)
        self.assertNotIn("$5,000", res.redacted_text)
        self.assertIn(PIIRedactor.TOKEN_SALARY, res.redacted_text)
        self.assertGreaterEqual(res.redactions_count, 2)
        self.assertIn(PIIType.SALARY.value, res.detected_types)

    def test_student_roll_and_usn_redaction(self) -> None:
        """Student university seat numbers (USN) and roll numbers must be masked."""
        text = "Supervised student 01FE23BCI054 and USN: 2BV21CS045 on final year demo."
        res = self.redactor.redact(text)
        self.assertNotIn("01FE23BCI054", res.redacted_text)
        self.assertNotIn("2BV21CS045", res.redacted_text)
        self.assertIn(PIIRedactor.TOKEN_STUDENT_ID, res.redacted_text)
        self.assertGreaterEqual(res.redactions_count, 2)
        self.assertIn(PIIType.STUDENT_ID.value, res.detected_types)

    def test_composite_pii_redaction(self) -> None:
        """Mixed text containing multiple PII categories should all be masked."""
        text = (
            "Student Rahul (USN: 01FE23BCI012, phone +91 9845011223) hired at 12 LPA. "
            "Supervisor Dr. Kulkarni (Aadhaar 4532 8901 2345) verified."
        )
        res = self.redactor.redact(text)
        self.assertNotIn("+91 9845011223", res.redacted_text)
        self.assertNotIn("4532 8901 2345", res.redacted_text)
        self.assertNotIn("12 LPA", res.redacted_text)
        self.assertNotIn("01FE23BCI012", res.redacted_text)
        self.assertGreaterEqual(len(res.detected_types), 3)


if __name__ == "__main__":
    unittest.main()
