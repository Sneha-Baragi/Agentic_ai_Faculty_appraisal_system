"""Audit Layer: Operational and Compliance Logging.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class Audit:
    """Records chronological, immutable-style audit logs of all task executions."""

    def __init__(self) -> None:
        """Initialize empty audit trail."""
        self._logs: List[Dict[str, Any]] = []

    def log(
        self,
        task: Any,
        skill_name: str,
        tool_calls: List[Dict[str, Any]],
        result: Any = None,
        error: Optional[str] = None,
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an execution attempt in the audit log.

        Every audit entry records:
        - ISO-formatted UTC timestamp
        - User identifier
        - Original task payload
        - Skill name
        - List of tool calls executed
        - Result payload (if successful)
        - Error message (if failed)

        Args:
            task: Original task payload submitted by the user.
            skill_name: Name of the invoked skill.
            tool_calls: Tool invocations performed during task processing.
            result: Result payload from successful execution.
            error: Error message string if execution failed.
            user: Identifier of the invoking user.

        Returns:
            The created audit record dictionary.
        """
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "task": task,
            "skill_name": skill_name,
            "tool_calls": list(tool_calls) if tool_calls else [],
            "result": result,
            "error": str(error) if error is not None else None,
        }
        self._logs.append(entry)
        return entry

    def get_entries(self) -> List[Dict[str, Any]]:
        """Return all recorded audit log entries."""
        return list(self._logs)

    def count_failures(self, user: str, skill_name: str) -> int:
        """Count previous failure entries in the audit log for a specific user and skill.

        Assignment 2 requirement:
        Use the existing audit log to count previous error entries for the same
        user/skill combination without maintaining separate hidden failure-count state.

        Args:
            user: Identifier of the user.
            skill_name: Name of the skill.

        Returns:
            Number of previous failed attempts (entries with non-null error).
        """
        target_user = user.strip() if isinstance(user, str) else user
        count = 0
        for entry in self._logs:
            if (
                entry.get("user") == target_user
                and entry.get("skill_name") == skill_name
                and entry.get("error") is not None
            ):
                count += 1
        return count

    def clear(self) -> None:
        """Reset the audit trail."""
        self._logs.clear()
