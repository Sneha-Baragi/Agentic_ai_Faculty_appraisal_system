"""Unit tests for AuditLedger agent.

Tests cryptographic SHA-256 hash chaining, genesis block initialization,
chain integrity verification, and tamper detection.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

_LAB_ROOT = Path(__file__).resolve().parent.parent
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from agents.audit_ledger import AuditLedger
from tools.hash_chain import GENESIS_PREV_HASH


class TestAuditLedger(unittest.TestCase):
    """Test suite for Cryptographic Audit Ledger."""

    def setUp(self) -> None:
        self.ledger = AuditLedger()

    def test_empty_ledger_integrity(self) -> None:
        """An empty ledger should evaluate as valid."""
        self.assertEqual(len(self.ledger), 0)
        is_valid, broken_idx, _ = self.ledger.verify_integrity()
        self.assertTrue(is_valid)
        self.assertIsNone(broken_idx)

    def test_single_entry_genesis_link(self) -> None:
        """The first block must link to GENESIS_PREV_HASH."""
        entry = self.ledger.append_entry(
            actor_id="FAC-001",
            role="faculty",
            action="submit_appraisal",
            status="APPROVED",
            payload={"score": 85.0},
        )
        self.assertEqual(len(self.ledger), 1)
        self.assertEqual(entry.sequence_number, 1)
        self.assertEqual(entry.prev_hash, GENESIS_PREV_HASH)
        self.assertEqual(len(entry.record_hash), 64)

        is_valid, broken_idx, _ = self.ledger.verify_integrity()
        self.assertTrue(is_valid)
        self.assertIsNone(broken_idx)

    def test_multi_entry_hash_chaining(self) -> None:
        """Sequential entries must link to the immediate predecessor's record_hash."""
        e1 = self.ledger.append_entry("FAC-01", "faculty", "submit_appraisal", "APPROVED")
        e2 = self.ledger.append_entry("HOD-01", "hod", "review_appraisal", "APPROVED")
        e3 = self.ledger.append_entry("DEAN-01", "dean", "approve_appraisal", "APPROVED")

        self.assertEqual(len(self.ledger), 3)
        self.assertEqual(e1.prev_hash, GENESIS_PREV_HASH)
        self.assertEqual(e2.prev_hash, e1.record_hash)
        self.assertEqual(e3.prev_hash, e2.record_hash)

        is_valid, broken_idx, _ = self.ledger.verify_integrity()
        self.assertTrue(is_valid)
        self.assertIsNone(broken_idx)

    def test_tamper_detection_intermediate_block(self) -> None:
        """Altering a field in an intermediate block must cause verification to fail."""
        self.ledger.append_entry("FAC-01", "faculty", "submit_appraisal", "APPROVED")
        self.ledger.append_entry("HOD-01", "hod", "review_appraisal", "APPROVED")
        self.ledger.append_entry("DEAN-01", "dean", "approve_appraisal", "APPROVED")

        # Corrupt block index 1 (HOD entry)
        self.ledger.tamper_entry(1, "status", "REJECTED")

        is_valid, broken_idx, msg = self.ledger.verify_integrity()
        self.assertFalse(is_valid)
        self.assertEqual(broken_idx, 1)
        self.assertIn("Tampered content at block #2", msg)

    def test_tamper_detection_genesis_block(self) -> None:
        """Altering the genesis block must cause immediate verification failure at index 0."""
        self.ledger.append_entry("FAC-01", "faculty", "submit_appraisal", "APPROVED")
        self.ledger.append_entry("HOD-01", "hod", "review_appraisal", "APPROVED")

        self.ledger.tamper_entry(0, "actor_id", "MALICIOUS_ACTOR")

        is_valid, broken_idx, msg = self.ledger.verify_integrity()
        self.assertFalse(is_valid)
        self.assertEqual(broken_idx, 0)
        self.assertIn("Tampered content at block #1", msg)

    def test_tamper_detection_prev_hash_alteration(self) -> None:
        """Altering a block's prev_hash must trigger a broken hash chain error."""
        self.ledger.append_entry("FAC-01", "faculty", "submit_appraisal", "APPROVED")
        self.ledger.append_entry("HOD-01", "hod", "review_appraisal", "APPROVED")

        fake_hash = "f" * 64
        self.ledger.tamper_entry(1, "prev_hash", fake_hash)

        is_valid, broken_idx, msg = self.ledger.verify_integrity()
        self.assertFalse(is_valid)
        self.assertEqual(broken_idx, 1)
        self.assertIn("prev_hash mismatch", msg)

    def test_save_and_load_persistence(self) -> None:
        """Ledger can be saved to file and reloaded with intact cryptographic verification."""
        self.ledger.append_entry("FAC-01", "faculty", "submit_appraisal", "APPROVED")
        self.ledger.append_entry("HOD-01", "hod", "review_appraisal", "APPROVED")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            self.ledger.save_to_file(tmp_path)

            new_ledger = AuditLedger()
            new_ledger.load_from_file(tmp_path)

            self.assertEqual(len(new_ledger), 2)
            is_valid, broken_idx, _ = new_ledger.verify_integrity()
            self.assertTrue(is_valid)
            self.assertIsNone(broken_idx)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
