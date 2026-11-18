"""Unit tests for Lab 7 Graph Orchestration Engine.

Verifies node registration, transition routing, conditional branches,
execution tracing, step limits, and exception handling.
"""

from pathlib import Path
import sys
import unittest

# Ensure Lab 7 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from graph.graph_engine import GraphEngine
from graph.node import Node
from graph.state import create_initial_state
from models.schemas import WorkflowState


class TestGraphEngine(unittest.TestCase):
    """Test suite for GraphEngine execution and transitions."""

    def setUp(self) -> None:
        """Create clean state and graph."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        self.graph = GraphEngine(name="PipelineTestGraph")

    def test_linear_graph_execution(self) -> None:
        """Test linear flow executes nodes in sequence."""
        def step_1(state: WorkflowState) -> WorkflowState:
            state.audit_log.append({"step": "1"})
            return state

        def step_2(state: WorkflowState) -> WorkflowState:
            state.audit_log.append({"step": "2"})
            return state

        self.graph.add_node(Node(name="step_1", handler=step_1))
        self.graph.add_node(Node(name="step_2", handler=step_2))
        self.graph.add_transition(from_node="step_1", to_node="step_2")

        res = self.graph.run(initial_node_name="step_1", state=self.state)

        # Check execution trace
        trace_nodes = [t["node_name"] for t in self.graph.execution_trace]
        self.assertEqual(trace_nodes, ["step_1", "step_2"])

    def test_conditional_branching(self) -> None:
        """Test conditional transitions route based on state predicates."""
        def decider(state: WorkflowState) -> WorkflowState:
            state.workflow_status = "BRANCH_B"
            return state

        def path_a(state: WorkflowState) -> WorkflowState:
            state.publication_status = "A_TAKEN"
            return state

        def path_b(state: WorkflowState) -> WorkflowState:
            state.publication_status = "B_TAKEN"
            return state

        self.graph.add_node(Node(name="decider", handler=decider))
        self.graph.add_node(Node(name="path_a", handler=path_a))
        self.graph.add_node(Node(name="path_b", handler=path_b))

        self.graph.add_transition(
            from_node="decider",
            to_node="path_a",
            condition=lambda s: s.workflow_status == "BRANCH_A",
        )
        self.graph.add_transition(
            from_node="decider",
            to_node="path_b",
            condition=lambda s: s.workflow_status == "BRANCH_B",
        )

        res = self.graph.run(initial_node_name="decider", state=self.state)

        self.assertEqual(res.publication_status, "B_TAKEN")
        trace_nodes = [t["node_name"] for t in self.graph.execution_trace]
        self.assertEqual(trace_nodes, ["decider", "path_b"])

    def test_step_limit_prevents_infinite_cycles(self) -> None:
        """Test max_steps prevents infinite loop if cycles exist."""
        def cycle_a(state: WorkflowState) -> WorkflowState:
            return state

        def cycle_b(state: WorkflowState) -> WorkflowState:
            return state

        self.graph.add_node(Node(name="cycle_a", handler=cycle_a))
        self.graph.add_node(Node(name="cycle_b", handler=cycle_b))

        self.graph.add_transition(from_node="cycle_a", to_node="cycle_b")
        self.graph.add_transition(from_node="cycle_b", to_node="cycle_a")

        res = self.graph.run(initial_node_name="cycle_a", state=self.state, max_steps=6)

        self.assertEqual(len(self.graph.execution_trace), 6)

    def test_node_failure_handling(self) -> None:
        """Test that exception inside node sets state to FAILED and records trace."""
        def failing_node(state: WorkflowState) -> WorkflowState:
            raise RuntimeError("Synthetic node failure")

        self.graph.add_node(Node(name="failing_node", handler=failing_node))

        with self.assertRaises(RuntimeError):
            self.graph.run(initial_node_name="failing_node", state=self.state)

        self.assertEqual(self.state.workflow_status, "FAILED")
        self.assertEqual(len(self.graph.execution_trace), 1)
        self.assertEqual(self.graph.execution_trace[0]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
