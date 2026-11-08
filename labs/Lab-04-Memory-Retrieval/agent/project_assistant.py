"""
project_assistant.py
====================
Project Memory Assistant coordinating:
  1. Short-term memory – current-session facts (session_facts)
  2. Long-term memory  – stored project decisions (ProjectMemory)
  3. Source-tagged answers – explicit provenance for every statement
  4. Conflict detection – flagging contradictions before any memory update
  5. Permission enforcement – delegating writes to ProjectMemory
  6. Staleness warnings – alerting users to decisions past the retention window
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from memory.memory_record import MemoryRecord
from memory.project_memory import ProjectMemory


class ProjectAssistant:
    """
    Assistant that remembers decisions across sessions while isolating
    short-term session state from long-term verified memory.
    """

    def __init__(self, memory: ProjectMemory | None = None) -> None:
        """
        Initialize the ProjectAssistant.

        Args:
            memory: Optional ProjectMemory instance; creates a fresh store if None.
        """
        self.memory = memory if memory is not None else ProjectMemory()
        # Short-term memory: session-only facts partitioned by topic
        self.session_facts: dict[str, str] = {}

    # -----------------------------------------------------------------------
    # Short-term session memory management
    # -----------------------------------------------------------------------

    def set_session_fact(self, topic: str, fact: str) -> None:
        """
        Record a transient fact in current session memory (short-term).

        Session facts exist only for the lifetime of the session and do not
        modify long-term stored decisions.
        """
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("Topic must be a non-empty string.")
        if not isinstance(fact, str) or not fact.strip():
            raise ValueError("Fact must be a non-empty string.")

        self.session_facts[topic.strip().lower()] = fact.strip()

    def clear_session_facts(self) -> None:
        """Reset current session memory without touching long-term memory."""
        self.session_facts.clear()

    # -----------------------------------------------------------------------
    # Answering queries with source tagging and staleness checks
    # -----------------------------------------------------------------------

    def answer(
        self,
        topic: str,
        question: str = "",
        reference_date: Any = None,
    ) -> dict[str, Any]:
        """
        Answer a question about a specific topic using available memory layers.

        Behavior:
          1. Scopes lookup strictly to the requested topic (no leakage).
          2. Checks short-term session state separately from long-term memory.
          3. Evaluates long-term memory records for provenance and staleness.
          4. Tags every factual statement with its exact source:
             - '[current_session]' for session-level state
             - '[memory, dated YYYY-MM-DD]' for long-term records
          5. Prepends a staleness warning if the decision exceeds retention_days.
          6. Returns an explicit 'no stored decision' message if neither exists.

        Args:
            topic:          The topic to query (e.g. 'database', 'hosting').
            question:       The user's natural language question (optional).
            reference_date: Optional reference date for staleness evaluation.

        Returns:
            A structured dict containing topic, question, answer, source,
            source_tag, record, and warning metadata.
        """
        if not isinstance(topic, str) or not topic.strip():
            return {
                "topic": "",
                "question": question,
                "answer": "Please provide a valid topic to search memory.",
                "source": "none",
                "source_tag": "[none]",
                "record": None,
                "session_fact": None,
                "warning": None,
            }

        norm_topic = topic.strip().lower()

        # Layer 1: Check short-term current session state
        session_fact = self.session_facts.get(norm_topic)

        # Layer 2: Retrieve latest long-term stored record
        latest_record = self.memory.get_latest(norm_topic)

        # Case A: Both session fact and stored decision exist
        # Report current session state first, citing the background stored memory
        if session_fact is not None and latest_record is not None:
            warning = self.memory.get_staleness_warning(latest_record, reference_date)
            parts: list[str] = []
            if warning:
                parts.append(warning)
            parts.append(
                f"[current_session] Current session note: {session_fact}"
            )
            parts.append(
                f"[memory, dated {latest_record.date}] "
                f"Per a decision on {latest_record.date}, {latest_record.fact}."
            )
            answer_text = "\n".join(parts)
            return {
                "topic": norm_topic,
                "question": question,
                "answer": answer_text,
                "source": "current_session+memory",
                "source_tag": f"[current_session] & [memory, dated {latest_record.date}]",
                "record": latest_record.to_dict(),
                "session_fact": session_fact,
                "warning": warning,
            }

        # Case B: Current session fact only
        if session_fact is not None and latest_record is None:
            answer_text = (
                f"[current_session] In the current session, we noted: {session_fact}."
            )
            return {
                "topic": norm_topic,
                "question": question,
                "answer": answer_text,
                "source": "current_session",
                "source_tag": "[current_session]",
                "record": None,
                "session_fact": session_fact,
                "warning": None,
            }

        # Case C: Long-term stored memory only
        if latest_record is not None:
            warning = self.memory.get_staleness_warning(latest_record, reference_date)
            statement = (
                f"[memory, dated {latest_record.date}] "
                f"Per a decision on {latest_record.date}, {latest_record.fact}."
            )
            if warning:
                answer_text = f"{warning}\n{statement}"
            else:
                answer_text = statement

            return {
                "topic": norm_topic,
                "question": question,
                "answer": answer_text,
                "source": "memory",
                "source_tag": f"[memory, dated {latest_record.date}]",
                "record": latest_record.to_dict(),
                "session_fact": None,
                "warning": warning,
            }

        # Case D: No information available
        answer_text = (
            f"I have no stored decision or current session state for '{norm_topic}'."
        )
        return {
            "topic": norm_topic,
            "question": question,
            "answer": answer_text,
            "source": "none",
            "source_tag": "[none]",
            "record": None,
            "session_fact": None,
            "warning": None,
        }

    # -----------------------------------------------------------------------
    # Statement intake and conflict detection
    # -----------------------------------------------------------------------

    def receive_statement(
        self,
        topic: str,
        new_fact: str,
        user_role: str,
        date: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a new statement proposed by a team member.

        Workflow:
          1. Retrieve the latest confirmed record for the topic.
          2. Compare the proposed new_fact with the existing stored decision.
          3. If they differ, detect a conflict:
             - Return structured conflict payload.
             - Include old fact, old date, and proposed fact.
             - Prompt for confirmation.
             - DO NOT overwrite existing memory.
          4. If no conflict exists (or no prior record exists):
             - Write through permission-controlled memory layer.
             - If role is unauthorized, raises PermissionError.
             - Return success payload.

        Args:
            topic:     The project topic.
            new_fact:  The newly proposed statement.
            user_role: The role of the user proposing the statement.
            date:      Optional date override (defaults to current UTC date).

        Returns:
            Structured dict describing outcome (conflict or written).
        """
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("Topic must be a non-empty string.")
        if not isinstance(new_fact, str) or not new_fact.strip():
            raise ValueError("new_fact must be a non-empty string.")

        norm_topic = topic.strip().lower()
        cleaned_fact = new_fact.strip()
        record_date = (
            date.strip()
            if isinstance(date, str) and date.strip()
            else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )

        latest_record = self.memory.get_latest(norm_topic)

        # Conflict check: existing record has a different fact
        if latest_record is not None and not self._facts_equivalent(
            latest_record.fact, cleaned_fact
        ):
            return {
                "conflict": True,
                "topic": norm_topic,
                "stored": latest_record.fact,
                "stored_date": latest_record.date,
                "new": cleaned_fact,
                "user_role": user_role,
                "message": (
                    f"Conflict detected for '{norm_topic}': stored decision from "
                    f"{latest_record.date} is '{latest_record.fact}', but proposed "
                    f"fact is '{cleaned_fact}'. Please confirm if the stored "
                    f"memory should be updated."
                ),
                "updated": False,
            }

        # No conflict (first record or identical statement): attempt write
        new_record = MemoryRecord(
            topic=norm_topic,
            fact=cleaned_fact,
            date=record_date,
            source="memory",
        )

        # Role authorization check is enforced by ProjectMemory.write()
        self.memory.write(new_record, user_role=user_role)

        return {
            "conflict": False,
            "topic": norm_topic,
            "stored": cleaned_fact,
            "stored_date": record_date,
            "new": cleaned_fact,
            "user_role": user_role,
            "message": (
                f"Decision for '{norm_topic}' successfully recorded in "
                f"long-term memory."
            ),
            "updated": True,
        }

    def confirm_and_update(
        self,
        topic: str,
        new_fact: str,
        user_role: str,
        date: str | None = None,
    ) -> dict[str, Any]:
        """
        Explicitly confirm and resolve a conflict, updating long-term memory.

        Enforces that only authorized roles (e.g. team_lead) can commit
        the update.

        Args:
            topic:     The project topic.
            new_fact:  The confirmed decision text.
            user_role: Role of the confirming user (must be authorized).
            date:      Optional date string (defaults to today).

        Returns:
            Structured confirmation payload.
        """
        norm_topic = topic.strip().lower()
        cleaned_fact = new_fact.strip()
        record_date = (
            date.strip()
            if isinstance(date, str) and date.strip()
            else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )

        record = MemoryRecord(
            topic=norm_topic,
            fact=cleaned_fact,
            date=record_date,
            source="memory",
        )

        # Permission check happens here
        self.memory.write(record, user_role=user_role)

        return {
            "conflict": False,
            "topic": norm_topic,
            "stored": cleaned_fact,
            "stored_date": record_date,
            "new": cleaned_fact,
            "user_role": user_role,
            "message": (
                f"Conflict resolved. Updated decision for '{norm_topic}' committed "
                f"to long-term memory by '{user_role}' on {record_date}."
            ),
            "updated": True,
        }

    # -----------------------------------------------------------------------
    # Helper methods
    # -----------------------------------------------------------------------

    @staticmethod
    def _facts_equivalent(fact1: str, fact2: str) -> bool:
        """Case- and punctuation-insensitive fact comparison."""
        def normalize(text: str) -> str:
            chars = [c.lower() for c in text if c.isalnum() or c.isspace()]
            return " ".join("".join(chars).split())

        return normalize(fact1) == normalize(fact2)

