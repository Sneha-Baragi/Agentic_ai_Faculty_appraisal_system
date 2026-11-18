"""Unit tests for Lab 8 Parallel Swarm Execution.

Verifies:
- All three collectors execute concurrently via ThreadPoolExecutor.
- Actual execution overlap and concurrency efficiency proven by timing.
- Capturing start time, end time, duration in ms, and status per collector.
- Storing outputs in separate state fields before merge.
"""

from pathlib import Path
import sys
import time
import unittest

# Ensure Lab 8 root directory is on sys.path
LAB_ROOT = str(Path(__file__).resolve().parent.parent)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agents.administrative_agent import AdministrativeDataCollectionAgent
from agents.research_agent import ResearchDataCollectionAgent
from agents.teaching_agent import TeachingDataCollectionAgent
from models.schemas import CollectorResult, WorkflowState
from swarm.executor import SwarmExecutor
from swarm.state import create_initial_state


class TestParallelExecution(unittest.TestCase):
    """Test suite for concurrent swarm execution."""

    def setUp(self) -> None:
        """Create clean workflow state and executor."""
        self.state = create_initial_state(
            faculty_id="FAC001",
            faculty_name="Dr. Ananya Sharma",
            appraisal_period="2025-2026",
            requester_role="Faculty",
        )
        self.executor = SwarmExecutor(max_workers=3)
        self.research_agent = ResearchDataCollectionAgent()
        self.teaching_agent = TeachingDataCollectionAgent()
        self.admin_agent = AdministrativeDataCollectionAgent()

    def test_concurrent_execution_of_all_three_collectors(self) -> None:
        """Test all 3 collectors execute and return isolated CollectorResult objects."""
        tasks = {
            "ResearchDataCollectionAgent": self.research_agent.execute,
            "TeachingDataCollectionAgent": self.teaching_agent.execute,
            "AdministrativeDataCollectionAgent": self.admin_agent.execute,
        }

        results = self.executor.execute_swarm(tasks=tasks, state=self.state)

        # All 3 collectors must have responded
        self.assertEqual(len(results), 3)
        self.assertIn("ResearchDataCollectionAgent", results)
        self.assertIn("TeachingDataCollectionAgent", results)
        self.assertIn("AdministrativeDataCollectionAgent", results)

        for role, res in results.items():
            self.assertEqual(res.status, "SUCCESS")
            self.assertGreater(len(res.activities), 0)
            self.assertTrue(len(res.start_time) > 0)
            self.assertTrue(len(res.end_time) > 0)
            self.assertGreater(res.duration_ms, 0.0)

        # Separate state fields must be populated
        self.assertEqual(len(self.state.swarm_results), 3)
        self.assertIn("ResearchDataCollectionAgent", self.state.swarm_results)
        self.assertIn("TeachingDataCollectionAgent", self.state.swarm_results)
        self.assertIn("AdministrativeDataCollectionAgent", self.state.swarm_results)

    def test_concurrency_timing_overlap(self) -> None:
        """Prove genuine execution overlap by measuring total elapsed time for sleeping tasks."""
        def sleeping_task_1(state: WorkflowState) -> CollectorResult:
            time.sleep(0.08)
            return CollectorResult(
                collector_role="SleepWorker1",
                category="Test",
                status="SUCCESS",
                start_time="",
                end_time="",
                duration_ms=0.0,
            )

        def sleeping_task_2(state: WorkflowState) -> CollectorResult:
            time.sleep(0.08)
            return CollectorResult(
                collector_role="SleepWorker2",
                category="Test",
                status="SUCCESS",
                start_time="",
                end_time="",
                duration_ms=0.0,
            )

        def sleeping_task_3(state: WorkflowState) -> CollectorResult:
            time.sleep(0.08)
            return CollectorResult(
                collector_role="SleepWorker3",
                category="Test",
                status="SUCCESS",
                start_time="",
                end_time="",
                duration_ms=0.0,
            )

        tasks = {
            "SleepWorker1": sleeping_task_1,
            "SleepWorker2": sleeping_task_2,
            "SleepWorker3": sleeping_task_3,
        }

        t0 = time.perf_counter()
        results = self.executor.execute_swarm(tasks=tasks, state=self.state)
        elapsed = time.perf_counter() - t0

        # If sequential, 3 * 0.08s = 0.24s.
        # If parallel, ~0.08s - 0.18s.
        self.assertLess(elapsed, 0.22, f"Expected parallel execution <0.22s, took {elapsed:.3f}s")
        self.assertEqual(len(results), 3)

    def test_audit_log_captures_swarm_execution(self) -> None:
        """Test audit log records swarm execution completion with summary details."""
        tasks = {
            "ResearchDataCollectionAgent": self.research_agent.execute,
            "TeachingDataCollectionAgent": self.teaching_agent.execute,
        }
        self.executor.execute_swarm(tasks=tasks, state=self.state)

        actions = [e["action"] for e in self.state.audit_log]
        self.assertIn("SWARM_EXECUTION_COMPLETE", actions)


if __name__ == "__main__":
    unittest.main()
