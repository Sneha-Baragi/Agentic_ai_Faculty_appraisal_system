"""Unit tests for Edge Cases and Robustness.

Tests boundary conditions, unicode normalization, malformed inputs,
extreme score values, and security limits.
"""
from __future__ import annotations

import unittest
from pathlib import Path
import sys

_LAB_ROOT = Path(__file__).resolve().parent.parent
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from agents.audit_ledger import AuditLedger
from agents.pii_redactor import PIIRedactor
from agents.prompt_guard import PromptGuard
from governance.governance_engine import GovernanceEngine
from models.schemas import Action, Role, SecurityContext
from tools.sanitizers import normalize_unicode, sanitize_input_text


class TestEdgeCases(unittest.TestCase):
    """Test suite for edge cases and input boundary conditions."""

    def test_unicode_normalization_and_obfuscation(self) -> None:
        """Full-width unicode characters and accents are normalized to NFKC."""
        # Full-width 'admin' characters
        full_width_admin = "ａｄｍｉｎ"
        norm = normalize_unicode(full_width_admin)
        self.assertEqual(norm, "admin")

        # Mixed control characters
        raw = "Teaching claims\x00\x08 with null byte"
        clean = sanitize_input_text(raw)
        self.assertEqual(clean, "Teaching claims with null byte")

    def test_html_script_injection_sanitization(self) -> None:
        """Embedded script tags and onload handlers are completely stripped."""
        text = "Taught course <script>alert('xss')</script> in Operating Systems."
        clean = sanitize_input_text(text)
        self.assertNotIn("<script>", clean)
        self.assertNotIn("alert('xss')", clean)

    def test_maximum_input_length_clamping(self) -> None:
        """Excessively long text is truncated to the safety boundary."""
        huge_text = "A" * 15000
        clean = sanitize_input_text(huge_text, max_length=5000)
        self.assertEqual(len(clean), 5000)

    def test_score_boundary_clamping(self) -> None:
        """Negative scores or scores exceeding 100 are clamped to [0.0, 100.0]."""
        engine = GovernanceEngine()
        ctx = SecurityContext(actor_id="FAC-001", role=Role.FACULTY)

        # Negative score
        rep_neg = engine.process_request(
            context=ctx,
            action=Action.SUBMIT_APPRAISAL,
            payload={"self_appraisal_score": -25.0},
        )
        self.assertEqual(rep_neg.execution_result.get("verified_score"), 0.0)

        # Excessive score
        rep_high = engine.process_request(
            context=ctx,
            action=Action.SUBMIT_APPRAISAL,
            payload={"self_appraisal_score": 150.0},
        )
        self.assertEqual(rep_high.execution_result.get("verified_score"), 100.0)

    def test_audit_ledger_tamper_out_of_bounds(self) -> None:
        """Tampering with an out-of-bounds index or non-existent attribute raises an error."""
        ledger = AuditLedger()
        ledger.append_entry("FAC-01", "faculty", "submit_appraisal", "APPROVED")

        with self.assertRaises(IndexError):
            ledger.tamper_entry(99, "status", "ALTERED")

        with self.assertRaises(AttributeError):
            ledger.tamper_entry(0, "non_existent_attribute", "VALUE")

    def test_pii_no_crash_on_none_or_empty(self) -> None:
        """PIIRedactor handles None or empty string gracefully."""
        redactor = PIIRedactor()
        res_none = redactor.redact("")
        self.assertEqual(res_none.redactions_count, 0)
        self.assertEqual(res_none.redacted_text, "")

    def test_unknown_action_handled_gracefully(self) -> None:
        """Unknown action strings return a clean REJECTED report without crashing."""
        engine = GovernanceEngine()
        ctx = SecurityContext(actor_id="FAC-001", role=Role.FACULTY)
        rep = engine.process_request(ctx, "completely_invalid_action_name")
        self.assertEqual(rep.status, "REJECTED")
        self.assertFalse(rep.rbac_allowed)


if __name__ == "__main__":
    unittest.main()
