"""
memory_record.py
================
Structured schema for memory entries in the Project Memory Assistant.

Each stored decision or fact is represented as an instance of MemoryRecord
rather than a plain unvalidated string. This ensures every factual entry has
an explicit topic, verified content, timestamp date, and provenance source tag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MemoryRecord:
    """
    Structured representation of a project memory item.

    Attributes:
        topic:  The project area or domain (e.g. 'database', 'hosting').
        fact:   The decision or factual statement recorded.
        date:   ISO date string (YYYY-MM-DD) when the decision was recorded.
        source: Provenance tag; defaults to 'memory' for long-term stored items.
    """

    topic: str
    fact: str
    date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    source: str = "memory"

    def __post_init__(self) -> None:
        """Validate input types and values upon initialization."""
        if not isinstance(self.topic, str) or not self.topic.strip():
            raise ValueError("MemoryRecord 'topic' must be a non-empty string.")
        if not isinstance(self.fact, str) or not self.fact.strip():
            raise ValueError("MemoryRecord 'fact' must be a non-empty string.")
        if not isinstance(self.date, str) or not self.date.strip():
            raise ValueError("MemoryRecord 'date' must be a non-empty string.")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("MemoryRecord 'source' must be a non-empty string.")

        # Normalize topic and whitespace
        self.topic = self.topic.strip().lower()
        self.fact = self.fact.strip()
        self.date = self.date.strip()
        self.source = self.source.strip()

    def to_dict(self) -> dict[str, str]:
        """Serialize memory record to a standard dictionary."""
        return {
            "topic": self.topic,
            "fact": self.fact,
            "date": self.date,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRecord:
        """Deserialize a dictionary into a MemoryRecord instance."""
        return cls(
            topic=data["topic"],
            fact=data["fact"],
            date=data.get(
                "date", datetime.now(timezone.utc).strftime("%Y-%m-%d")
            ),
            source=data.get("source", "memory"),
        )

