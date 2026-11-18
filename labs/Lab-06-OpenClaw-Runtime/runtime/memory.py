"""Memory Layer: Per-User Scoped Memory.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from typing import Any, Dict, List, Optional


class Memory:
    """Manages isolated, per-user memory scopes."""

    def __init__(self) -> None:
        """Initialize empty memory storage for all users."""
        self._storage: Dict[str, Dict[str, Any]] = {}

    def scope(self, user: str) -> Dict[str, Any]:
        """Return the memory dictionary belonging only to the requested user.

        If the user scope does not exist yet, it is created automatically.
        Ensures strict isolation so one user's memory cannot leak into another's.

        Args:
            user: Identifier of the user (e.g. 'uday').

        Returns:
            The mutable dictionary scope for this user.
        """
        if not isinstance(user, str) or not user.strip():
            raise ValueError("User identifier must be a non-empty string.")

        user_key = user.strip()
        if user_key not in self._storage:
            self._storage[user_key] = {}
        return self._storage[user_key]

    def get(self, user: str, key: str, default: Any = None) -> Any:
        """Get a value from a user's memory scope."""
        if not isinstance(user, str):
            return default
        user_key = user.strip()
        if user_key not in self._storage:
            return default
        return self._storage[user_key].get(key, default)

    def set(self, user: str, key: str, value: Any) -> None:
        """Set a value in a user's memory scope."""
        self.scope(user)[key] = value

    def has(self, user: str, key: str) -> bool:
        """Check if a key exists in a user's memory scope without auto-creating scope."""
        if not isinstance(user, str):
            return False
        user_key = user.strip()
        if user_key not in self._storage:
            return False
        return key in self._storage[user_key]

    def clear(self, user: Optional[str] = None) -> None:
        """Clear memory for a specific user, or reset all users if user is None."""
        if user is not None:
            user_key = user.strip()
            self._storage.pop(user_key, None)
        else:
            self._storage.clear()

    def all_users(self) -> List[str]:
        """Return list of all users with active memory scopes."""
        return list(self._storage.keys())
