"""Parallel Swarm Executor using Python concurrent.futures.ThreadPoolExecutor.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional

from models.schemas import CollectorResult, WorkflowState


class SwarmExecutor:
    """Dispatches independent specialist agents concurrently and collects isolated results."""

    def __init__(self, max_workers: int = 4) -> None:
        """Initialize swarm executor with thread pool worker capacity."""
        self.max_workers = max_workers

    def execute_swarm(
        self,
        tasks: Dict[str, Callable[[WorkflowState], CollectorResult]],
        state: WorkflowState,
    ) -> Dict[str, CollectorResult]:
        """Execute all collector tasks concurrently.

        Requirements enforced:
        - All tasks submitted independently; none depends on another collector's output.
        - Genuine concurrent execution via ThreadPoolExecutor.
        - Isolates failures: an exception in one collector does not terminate or discard others.
        - Records start time, completion time, duration in ms, and execution status.
        - Outputs remain indexed by collector role and separate until the merge stage.

        Args:
            tasks: Dict mapping collector_role -> callable worker taking state and returning CollectorResult.
            state: WorkflowState context passed to collectors.

        Returns:
            Dict mapping collector_role -> CollectorResult.
        """
        results: Dict[str, CollectorResult] = {}

        def _worker_wrapper(role: str, worker: Callable[[WorkflowState], CollectorResult]) -> CollectorResult:
            t0 = time.perf_counter()
            start_ts = datetime.now(timezone.utc).isoformat()
            try:
                res = worker(state)
                # Ensure timing fields are populated if not set by worker
                if not res.start_time:
                    res.start_time = start_ts
                if not res.end_time:
                    res.end_time = datetime.now(timezone.utc).isoformat()
                if res.duration_ms <= 0.0:
                    res.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                return res
            except Exception as exc:
                dur = round((time.perf_counter() - t0) * 1000, 2)
                end_ts = datetime.now(timezone.utc).isoformat()
                return CollectorResult(
                    collector_role=role,
                    category=role.replace("DataCollectionAgent", "").replace("Agent", ""),
                    status="FAILED",
                    start_time=start_ts,
                    end_time=end_ts,
                    duration_ms=dur,
                    activities=[],
                    error=str(exc),
                )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_role = {
                executor.submit(_worker_wrapper, role, worker): role
                for role, worker in tasks.items()
            }
            for future in as_completed(future_to_role):
                role = future_to_role[future]
                try:
                    result = future.result()
                    results[role] = result
                except Exception as exc:
                    # Defensive fallback in case thread pool itself raises
                    results[role] = CollectorResult(
                        collector_role=role,
                        category="Unknown",
                        status="FAILED",
                        start_time=datetime.now(timezone.utc).isoformat(),
                        end_time=datetime.now(timezone.utc).isoformat(),
                        duration_ms=0.0,
                        activities=[],
                        error=str(exc),
                    )

        # Store in separate state fields before merge stage
        state.swarm_results = {role: res.to_dict() for role, res in results.items()}

        state.add_audit_entry(
            node_name="SwarmExecutor",
            action="SWARM_EXECUTION_COMPLETE",
            details={
                "collectors_dispatched": list(tasks.keys()),
                "collector_statuses": {role: res.status for role, res in results.items()},
                "failed_count": sum(1 for res in results.values() if res.status == "FAILED"),
                "skipped_count": sum(1 for res in results.values() if res.status == "SKIPPED"),
                "successful_count": sum(1 for res in results.values() if res.status == "SUCCESS"),
            },
            status="WARNING" if any(res.status == "FAILED" for res in results.values()) else "SUCCESS",
        )

        return results
