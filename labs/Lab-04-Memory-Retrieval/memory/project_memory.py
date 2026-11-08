"""
project_memory.py
=================
Long-term memory store for project decisions with:
  1. Topic-scoped retrieval (prevents cross-topic memory leakage)
  2. Role-based write permission enforcement (only authorized roles may write)
  3. Staleness and retention policies (Assignment 2)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable

from memory.memory_record import MemoryRecord


# Only team_lead is authorized to write to long-term memory
ALLOWED_WRITERS: set[str] = {"team_lead"}


class ProjectMemory:
    """
    Manages long-term project memory with topic partitioning,
    permission checks, and retention rules.
    """

    ALLOWED_WRITERS: set[str] = ALLOWED_WRITERS
    DEFAULT_AUTHORIZED_ROLES: set[str] = ALLOWED_WRITERS

    def __init__(
        self,
        retention_days: int | None = None,
        authorized_roles: Iterable[str] | None = None,
    ) -> None:
        """
        Initialize the project memory store.

        Args:
            retention_days: Max age in days before a decision is deemed stale.
                            If None, staleness checks are disabled.
            authorized_roles: Set of role names allowed to write to memory.
        """
        # Internal storage: partitioned by normalized topic -> list of records
        self._store: dict[str, list[MemoryRecord]] = {}

        self.retention_days = retention_days
        if authorized_roles is not None:
            self.authorized_roles = {r.strip().lower() for r in authorized_roles}
        else:
            self.authorized_roles = set(self.ALLOWED_WRITERS)

    # -----------------------------------------------------------------------
    # Write operations
    # -----------------------------------------------------------------------

    def write(self, record: MemoryRecord, user_role: str) -> None:
        """
        Persist a structured MemoryRecord into long-term memory.

        Args:
            record:    The MemoryRecord to store.
            user_role: The role of the user attempting the write.

        Raises:
            PermissionError: If user_role is not in authorized_roles.
            TypeError:       If record is not an instance of MemoryRecord.
            ValueError:      If record content is invalid.
        """
        if not isinstance(record, MemoryRecord):
            raise TypeError(
                f"Expected MemoryRecord instance, got {type(record).__name__}."
            )

        normalized_role = (
            user_role.strip().lower() if isinstance(user_role, str) else ""
        )
        if normalized_role not in self.authorized_roles:
            raise PermissionError(
                f"Permission denied: role '{user_role}' is not authorized "
                f"to write to long-term memory. Authorized roles: "
                f"{sorted(self.authorized_roles)}."
            )

        topic = record.topic.strip().lower()
        if topic not in self._store:
            self._store[topic] = []

        self._store[topic].append(record)

    # -----------------------------------------------------------------------
    # Retrieval operations
    # -----------------------------------------------------------------------

    def retrieve(self, topic: str) -> list[MemoryRecord]:
        """
        Retrieve all memory records matching the requested topic.

        This provides topic-scoped retrieval: records from other topics
        are never returned or leaked.

        Args:
            topic: The topic name to look up (case-insensitive).

        Returns:
            A list of matching MemoryRecord objects, ordered chronologically.
            Returns an empty list if no records exist for the topic.
        """
        if not isinstance(topic, str):
            return []

        normalized_topic = topic.strip().lower()
        records = self._store.get(normalized_topic, [])
        # Return a shallow copy of the list to prevent external modification
        return list(records)

    def get_latest(self, topic: str) -> MemoryRecord | None:
        """
        Retrieve the latest confirmed MemoryRecord for a topic, or None.
        """
        records = self.retrieve(topic)
        return records[-1] if records else None

    def get_all_topics(self) -> list[str]:
        """Return a sorted list of all topics with stored records."""
        return sorted(self._store.keys())

    def clear(self) -> None:
        """Clear all stored memory records (primarily for testing)."""
        self._store.clear()

    # -----------------------------------------------------------------------
    # Assignment 2 – Staleness & Retention Policy
    # -----------------------------------------------------------------------

    def check_staleness(
        self,
        record: MemoryRecord,
        reference_date: str | date | datetime | None = None,
    ) -> tuple[bool, int]:
        """
        Determine if a memory record is stale according to retention_days.

        Args:
            record:         The MemoryRecord to evaluate.
            reference_date: Optional reference date to compare against.
                            Defaults to the current date.

        Returns:
            A tuple of (is_stale: bool, age_days: int).
            If retention_days is None, is_stale is always False.
        """
        if self.retention_days is None:
            return False, 0

        # Parse reference date
        if reference_date is None:
            ref_dt = datetime.now(timezone.utc).date()
        elif isinstance(reference_date, datetime):
            ref_dt = reference_date.date()
        elif isinstance(reference_date, date):
            ref_dt = reference_date
        elif isinstance(reference_date, str):
            ref_dt = datetime.strptime(
                reference_date.strip()[:10], "%Y-%m-%d"
            ).date()
        else:
            ref_dt = datetime.now(timezone.utc).date()

        # Parse record date
        try:
            rec_dt = datetime.strptime(record.date.strip()[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            # If date cannot be parsed, conservatively treat as not stale
            return False, 0

        age_days = (ref_dt - rec_dt).days
        if age_days < 0:
            age_days = 0

        is_stale = age_days > self.retention_days
        return is_stale, age_days

    def get_staleness_warning(
        self,
        record: MemoryRecord,
        reference_date: str | date | datetime | None = None,
    ) -> str | None:
        """
        Generate a warning message if the record is stale, or None if fresh.
        """
        is_stale, age_days = self.check_staleness(record, reference_date)
        if is_stale:
            return (
                f"Warning: This decision is from {age_days} days ago and "
                f"may be out of date (retention threshold: {self.retention_days} days)."
            )
        return None

