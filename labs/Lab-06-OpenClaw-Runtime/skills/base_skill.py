"""Base Skill Interface.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List


class BaseSkill(ABC):
    """Abstract base class for all OpenClaw skills."""

    name: str = "base_skill"

    def __init__(self) -> None:
        """Initialize skill with empty tool call history."""
        self.tool_calls: List[Dict[str, Any]] = []

    def record_tool_call(
        self, tool_name: str, args: Dict[str, Any], output: Any
    ) -> Dict[str, Any]:
        """Record an invoked tool call and its result."""
        call_entry = {
            "tool": tool_name,
            "args": dict(args),
            "output": output,
        }
        self.tool_calls.append(call_entry)
        return call_entry

    @abstractmethod
    def execute(
        self,
        task: Any,
        user: str,
        memory_scope: Dict[str, Any],
        tools: Dict[str, Callable[..., Any]],
    ) -> Dict[str, Any]:
        """Execute the skill on the supplied task.

        Args:
            task: Task payload containing input parameters.
            user: Name of the current invoking user.
            memory_scope: Mutable dictionary scope for this user.
            tools: Registry of callable tools available to the runtime.

        Returns:
            Structured dictionary result.

        Raises:
            Exception: Propagates any domain or tool execution error.
        """
        pass
