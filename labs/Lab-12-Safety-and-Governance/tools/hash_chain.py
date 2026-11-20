"""Cryptographic hashing and blockchain-inspired hash chaining utilities.

Pure Python standard library only (hashlib, json).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_PREV_HASH: str = "0" * 64


def compute_sha256(data: str | bytes) -> str:
    """Compute the SHA-256 hexadecimal digest of input data.

    Args:
        data: String or bytes to hash.

    Returns:
        64-character lowercase hexadecimal hash.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical_json(data: Any) -> str:
    """Serialize data into canonical JSON for deterministic cryptographic hashing.

    Keys are sorted, whitespace is minimized (no spaces around separators),
    and Unicode is preserved in deterministic UTF-8.

    Args:
        data: Arbitrary serializable object.

    Returns:
        Deterministic canonical JSON string.
    """
    return json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def compute_payload_hash(payload: Any) -> str:
    """Compute a deterministic SHA-256 hash for an arbitrary payload.

    Args:
        payload: String, dict, list, or dataclass.

    Returns:
        64-character SHA-256 hash.
    """
    if payload is None:
        return compute_sha256("")
    if isinstance(payload, (str, bytes)):
        return compute_sha256(payload)
    if hasattr(payload, "to_dict"):
        payload = payload.to_dict()
    return compute_sha256(canonical_json(payload))


def compute_block_hash(
    sequence_number: int,
    timestamp: str,
    actor_id: str,
    role: str,
    action: str,
    status: str,
    payload_hash: str,
    prev_hash: str,
) -> str:
    """Compute cryptographic block hash linking an audit record to its predecessor.

    Format:
        sha256("{seq}:{timestamp}:{actor}:{role}:{action}:{status}:{payload_hash}:{prev_hash}")

    Args:
        sequence_number: 1-indexed sequential block number.
        timestamp: ISO 8601 UTC timestamp string.
        actor_id: Identifier of the invoking actor.
        role: Security role of the actor.
        action: Governed action name.
        status: Status outcome (e.g. APPROVED, BLOCKED, REJECTED).
        payload_hash: SHA-256 hash of the request/response payload.
        prev_hash: SHA-256 hash of the preceding block (or GENESIS_PREV_HASH).

    Returns:
        64-character SHA-256 hexadecimal hash.
    """
    raw = (
        f"{sequence_number}:{timestamp}:{actor_id}:{role}:"
        f"{action}:{status}:{payload_hash}:{prev_hash}"
    )
    return compute_sha256(raw)
