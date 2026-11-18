"""Node definition for the Agentic Node Graph.

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
"""

from typing import Any, Callable, Dict, List, Optional
from models.schemas import WorkflowState


class Node:
    """Represents a computational or agentic step within the graph workflow."""

    def __init__(
        self,
        name: str,
        handler: Callable[[WorkflowState], WorkflowState],
        description: str = "",
        is_parallel_group_member: bool = False,
        parallel_group_name: Optional[str] = None,
    ) -> None:
        """Initialize graph node.

        Args:
            name: Unique node identifier.
            handler: Callable taking and returning WorkflowState.
            description: Human-readable description of node responsibilities.
            is_parallel_group_member: Whether this node runs concurrently in a parallel group.
            parallel_group_name: Name of the parallel group this node belongs to.
        """
        self.name = name
        self.handler = handler
        self.description = description
        self.is_parallel_group_member = is_parallel_group_member
        self.parallel_group_name = parallel_group_name

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Execute node logic against shared workflow state."""
        return self.handler(state)
