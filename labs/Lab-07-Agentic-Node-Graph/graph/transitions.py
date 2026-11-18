"""Conditional transitions and routing logic for the graph engine.

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
"""

from typing import Callable, Optional
from models.schemas import WorkflowState


class Transition:
    """Represents a state transition rule connecting graph nodes."""

    def __init__(
        self,
        from_node: str,
        to_node: str,
        condition: Optional[Callable[[WorkflowState], bool]] = None,
        name: str = "",
    ) -> None:
        """Initialize transition.

        Args:
            from_node: Source node identifier.
            to_node: Destination node identifier.
            condition: Predicate function evaluating if this edge should be traversed.
            name: Readable label for this routing branch.
        """
        self.from_node = from_node
        self.to_node = to_node
        self.condition = condition if condition is not None else (lambda state: True)
        self.name = name or f"{from_node}->{to_node}"

    def can_transition(self, state: WorkflowState) -> bool:
        """Evaluate if the transition condition is satisfied."""
        return bool(self.condition(state))
