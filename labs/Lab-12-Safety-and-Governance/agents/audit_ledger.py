"""Cryptographic Tamper-Evident Audit Ledger.

Maintains an immutable SHA-256 hash-chained sequence of audit events.
Any tampering with intermediate blocks or records is immediately detectable.
Pure Python standard library only.
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

from models.schemas import AuditEntry
from tools.hash_chain import (
    GENESIS_PREV_HASH,
    compute_block_hash,
    compute_payload_hash,
)

logger = logging.getLogger(__name__)


class AuditLedger:
    """Tamper-evident audit ledger backed by cryptographic SHA-256 hash chaining."""

    def __init__(self) -> None:
        """Initialize an empty audit ledger."""
        self._entries: list[AuditEntry] = []

    @property
    def entries(self) -> list[AuditEntry]:
        """Return a copy of all audit entries."""
        return list(self._entries)

    def __len__(self) -> int:
        """Return total number of entries in the ledger."""
        return len(self._entries)

    def append_entry(
        self,
        actor_id: str,
        role: str,
        action: str,
        status: str,
        payload: Any = None,
        payload_hash: str | None = None,
        timestamp: str | None = None,
    ) -> AuditEntry:
        """Append a new audit entry to the cryptographic hash chain.

        Args:
            actor_id: Identifier of the invoking actor.
            role: Security role of the actor.
            action: Governed action name.
            status: Status outcome (e.g. APPROVED, BLOCKED, REJECTED).
            payload: Optional payload object to hash.
            payload_hash: Precomputed payload hash if available.
            timestamp: Optional ISO 8601 UTC timestamp.

        Returns:
            The newly created :class:`~models.schemas.AuditEntry`.
        """
        sequence_number = len(self._entries) + 1
        if timestamp is None:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if payload_hash is None:
            payload_hash = compute_payload_hash(payload)

        # Hash of preceding entry, or genesis block
        if not self._entries:
            prev_hash = GENESIS_PREV_HASH
        else:
            prev_hash = self._entries[-1].record_hash

        record_hash = compute_block_hash(
            sequence_number=sequence_number,
            timestamp=timestamp,
            actor_id=actor_id,
            role=role,
            action=action,
            status=status,
            payload_hash=payload_hash,
            prev_hash=prev_hash,
        )

        entry = AuditEntry(
            sequence_number=sequence_number,
            timestamp=timestamp,
            actor_id=actor_id,
            role=role,
            action=action,
            status=status,
            payload_hash=payload_hash,
            prev_hash=prev_hash,
            record_hash=record_hash,
        )
        self._entries.append(entry)
        logger.debug(
            "Audit record #%d added [Hash: %s...%s]",
            sequence_number,
            record_hash[:8],
            record_hash[-8:],
        )
        return entry

    def verify_integrity(self) -> tuple[bool, int | None, str]:
        """Verify the integrity of the entire cryptographic ledger chain.

        Checks:
        1. Genesis block has prev_hash == GENESIS_PREV_HASH.
        2. Block i has prev_hash == block i-1 record_hash.
        3. Block i recalculates to the exact recorded record_hash.

        Returns:
            Tuple of (is_valid: bool, broken_at_index: int | None, message: str).
            If valid, broken_at_index is None. If tampered, broken_at_index
            identifies the zero-based index of the corrupted entry.
        """
        if not self._entries:
            return True, None, "Ledger is empty (intact)."

        for i, entry in enumerate(self._entries):
            # 1. Verify prev_hash link
            expected_prev = GENESIS_PREV_HASH if i == 0 else self._entries[i - 1].record_hash
            if entry.prev_hash != expected_prev:
                msg = (
                    f"Broken hash chain at block #{entry.sequence_number} (index {i}): "
                    f"prev_hash mismatch! Found '{entry.prev_hash}', expected '{expected_prev}'."
                )
                logger.error(msg)
                return False, i, msg

            # 2. Recompute record_hash from current contents
            recalculated_hash = compute_block_hash(
                sequence_number=entry.sequence_number,
                timestamp=entry.timestamp,
                actor_id=entry.actor_id,
                role=entry.role,
                action=entry.action,
                status=entry.status,
                payload_hash=entry.payload_hash,
                prev_hash=entry.prev_hash,
            )

            if entry.record_hash != recalculated_hash:
                msg = (
                    f"Tampered content at block #{entry.sequence_number} (index {i}): "
                    f"record_hash mismatch! Stored '{entry.record_hash}', recomputed '{recalculated_hash}'."
                )
                logger.error(msg)
                return False, i, msg

        success_msg = f"Audit ledger integrity verified ({len(self._entries)} blocks intact)."
        logger.info(success_msg)
        return True, None, success_msg

    def tamper_entry(self, index: int, field_name: str, new_value: Any) -> None:
        """Intentionally modify an entry attribute without updating hashes.

        Used strictly for demonstration and testing of tamper-evident security.

        Args:
            index: Zero-based index of entry to corrupt.
            field_name: Attribute name on :class:`~models.schemas.AuditEntry`.
            new_value: New malicious or altered value.

        Raises:
            IndexError: If index is out of bounds.
            AttributeError: If field_name does not exist on AuditEntry.
        """
        if index < 0 or index >= len(self._entries):
            raise IndexError(f"Entry index {index} out of range (0..{len(self._entries)-1})")
        entry = self._entries[index]
        if not hasattr(entry, field_name):
            raise AttributeError(f"AuditEntry has no attribute '{field_name}'")
        setattr(entry, field_name, new_value)
        logger.warning(
            "TAMPER DEMO: Altered entry index %d field '%s' -> '%s'",
            index,
            field_name,
            new_value,
        )

    def save_to_file(self, path: Path | str) -> None:
        """Persist all audit entries to a JSON file.

        Args:
            path: Destination file path.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self._entries]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Audit ledger saved to %s (%d entries).", target, len(data))

    def load_from_file(self, path: Path | str) -> None:
        """Load audit entries from a JSON file and verify chain integrity.

        Args:
            path: Source JSON file path.

        Raises:
            ValueError: If the file is malformed or chain integrity fails.
        """
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"Audit file not found: {target}")

        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries: list[AuditEntry] = []
        for item in data:
            entries.append(AuditEntry(**item))

        self._entries = entries
        is_valid, broken_idx, msg = self.verify_integrity()
        if not is_valid:
            raise ValueError(f"Loaded audit ledger failed integrity verification: {msg}")
        logger.info("Loaded and verified %d audit entries from %s.", len(entries), target)
