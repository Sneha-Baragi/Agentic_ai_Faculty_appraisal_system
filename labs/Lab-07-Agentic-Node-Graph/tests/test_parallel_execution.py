"""Unit tests for Lab 7 parallel execution engine.

Verifies true concurrent execution of collection agents using ThreadPoolExecutor,
recording of per-node duration, timestamps, status, and state merging.
"""

from pathlib import Path
import sys
import time
import unittest

# Ensure Lab 7 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.administrative_agent import AdministrativeAgent
from agents.research_agent import ResearchAgent
from agents.teaching_agent import TeachingAgent
from graph.graph_engine import GraphEngine
from graph.node import Node
from graph.state import create_initial_state
from models.schemas import WorkflowState


class TestParallelExecution(unittest.TestCase):
    """Test suite for concurrent execution in GraphEngine."""

    def setUp(self) -> None:
        """Create graph and initial state."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Jane Doe",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        self.graph = GraphEngine(name="TestParallelGraph")

        # Register parallel collection nodes
        self.research_agent = ResearchAgent()
        self.teaching_agent = TeachingAgent()
        self.admin_agent = AdministrativeAgent()

        self.graph.add_node(
            Node(
                name="research_collection",
                handler=self.research_agent.execute,
                is_parallel_group_member=True,
                parallel_group_name="parallel_collection",
            )
        )
        self.graph.add_node(
            Node(
                name="teaching_collection",
                handler=self.teaching_agent.execute,
                is_parallel_group_member=True,
                parallel_group_name="parallel_collection",
            )
        )
        self.graph.add_node(
            Node(
                name="administrative_collection",
                handler=self.admin_agent.execute,
                is_parallel_group_member=True,
                parallel_group_name="parallel_collection",
            )
        )

    def test_parallel_group_registration(self) -> None:
        """Test nodes are correctly registered into the parallel group."""
        self.assertIn("parallel_collection", self.graph.parallel_groups)
        group = self.graph.parallel_groups["parallel_collection"]
        self.assertEqual(len(group), 3)
        self.assertIn("research_collection", group)
        self.assertIn("teaching_collection", group)
        self.assertIn("administrative_collection", group)

    def test_parallel_execution_and_state_merging(self) -> None:
        """Test concurrent execution populates state for all three collection agents."""
        updated_state = self.graph.execute_parallel_group("parallel_collection", self.state)

        # All three collections should be populated
        self.assertGreater(len(updated_state.research_activities), 0)
        self.assertGreater(len(updated_state.teaching_activities), 0)
        self.assertGreater(len(updated_state.administrative_activities), 0)

        # Collection status dictionary must contain all 3 nodes
        status_map = updated_state.collection_status
        self.assertIn("research_collection", status_map)
        self.assertIn("teaching_collection", status_map)
        self.assertIn("administrative_collection", status_map)

        for node_name in ["research_collection", "teaching_collection", "administrative_collection"]:
            node_status = status_map[node_name]
            self.assertEqual(node_status["status"], "SUCCESS")
            self.assertIn("start_time", node_status)
            self.assertIn("end_time", node_status)
            self.assertIn("duration_ms", node_status)

        # Audit log must contain PARALLEL_JOIN_COMPLETE
        actions = [entry["action"] for entry in updated_state.audit_log]
        self.assertIn("PARALLEL_JOIN_COMPLETE", actions)

    def test_concurrent_timing_efficiency(self) -> None:
        """Test parallel execution runs simultaneously rather than sequentially."""
        timing_graph = GraphEngine(name="TimingTestGraph")

        def delayed_task_1(state: WorkflowState) -> WorkflowState:
            time.sleep(0.08)
            return state

        def delayed_task_2(state: WorkflowState) -> WorkflowState:
            time.sleep(0.08)
            return state

        def delayed_task_3(state: WorkflowState) -> WorkflowState:
            time.sleep(0.08)
            return state

        timing_graph.add_node(
            Node(name="task_1", handler=delayed_task_1, is_parallel_group_member=True, parallel_group_name="delay_group")
        )
        timing_graph.add_node(
            Node(name="task_2", handler=delayed_task_2, is_parallel_group_member=True, parallel_group_name="delay_group")
        )
        timing_graph.add_node(
            Node(name="task_3", handler=delayed_task_3, is_parallel_group_member=True, parallel_group_name="delay_group")
        )

        t0 = time.perf_counter()
        timing_graph.execute_parallel_group("delay_group", self.state)
        elapsed = time.perf_counter() - t0

        # If sequential, 3 * 0.08s = 0.24s.
        # If parallel, ~0.08-0.18s.
        self.assertLess(elapsed, 0.22, f"Expected parallel execution <0.22s, but took {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
