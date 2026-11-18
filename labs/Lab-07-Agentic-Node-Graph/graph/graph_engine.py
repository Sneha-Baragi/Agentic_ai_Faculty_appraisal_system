"""Graph Orchestration Engine.

Course: Agentic AI (26ECAC401)
Lab: 7 - Agentic Node Graph
Scenario: Faculty Appraisal Management System

Orchestrates sequential, parallel, and conditional execution of specialized agents.
Uses concurrent.futures.ThreadPoolExecutor for parallel node groups.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional, Set

from graph.node import Node
from graph.transitions import Transition
from models.schemas import WorkflowState


class GraphEngine:
    """Hybrid sequential and parallel workflow execution engine."""

    def __init__(self, name: str = "FacultyAppraisalGraph") -> None:
        """Initialize graph orchestration engine."""
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self.transitions: List[Transition] = []
        self.parallel_groups: Dict[str, List[str]] = {}
        self.execution_trace: List[Dict[str, Any]] = []

    def add_node(self, node: Node) -> None:
        """Register a node in the graph.

        If node is marked as member of a parallel group, registers it into the group.
        """
        self.nodes[node.name] = node
        if node.is_parallel_group_member and node.parallel_group_name:
            if node.parallel_group_name not in self.parallel_groups:
                self.parallel_groups[node.parallel_group_name] = []
            if node.name not in self.parallel_groups[node.parallel_group_name]:
                self.parallel_groups[node.parallel_group_name].append(node.name)

    def add_transition(
        self,
        from_node: str,
        to_node: str,
        condition: Optional[Callable[[WorkflowState], bool]] = None,
        name: str = "",
    ) -> None:
        """Add a directed conditional edge between two nodes."""
        trans = Transition(from_node=from_node, to_node=to_node, condition=condition, name=name)
        self.transitions.append(trans)

    def get_next_node(self, current_node_name: str, state: WorkflowState) -> Optional[str]:
        """Find the next node according to registered transitions whose conditions match."""
        for trans in self.transitions:
            if trans.from_node == current_node_name and trans.can_transition(state):
                return trans.to_node
        return None

    def execute_parallel_group(
        self, group_name: str, state: WorkflowState
    ) -> WorkflowState:
        """Execute all nodes in a parallel group concurrently using ThreadPoolExecutor.

        Records each parallel agent's start time, completion time, status, and output summary.
        Merges results into shared state.
        """
        if group_name not in self.parallel_groups:
            raise KeyError(f"Parallel group '{group_name}' is not registered.")

        node_names = self.parallel_groups[group_name]
        start_ts = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()

        def _worker_wrapper(node_name: str) -> Dict[str, Any]:
            node = self.nodes[node_name]
            w_t0 = time.perf_counter()
            w_start = datetime.now(timezone.utc).isoformat()
            try:
                # Execute agent on isolated copy or state reference
                # Note: node handlers return sub-results or modified state
                res_state = node.execute(state)
                w_dur = (time.perf_counter() - w_t0) * 1000
                w_end = datetime.now(timezone.utc).isoformat()
                return {
                    "node_name": node_name,
                    "status": "SUCCESS",
                    "start_time": w_start,
                    "end_time": w_end,
                    "duration_ms": round(w_dur, 2),
                    "returned_state": res_state,
                    "error": None,
                }
            except Exception as exc:
                w_dur = (time.perf_counter() - w_t0) * 1000
                w_end = datetime.now(timezone.utc).isoformat()
                return {
                    "node_name": node_name,
                    "status": "FAILED",
                    "start_time": w_start,
                    "end_time": w_end,
                    "duration_ms": round(w_dur, 2),
                    "returned_state": None,
                    "error": str(exc),
                }

        # True parallel execution using thread pool
        parallel_results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(node_names)) as executor:
            future_map = {executor.submit(_worker_wrapper, name): name for name in node_names}
            for future in as_completed(future_map):
                res = future.result()
                parallel_results.append(res)

        total_dur = (time.perf_counter() - t0) * 1000
        end_ts = datetime.now(timezone.utc).isoformat()

        # Update coordinator parallel collection status in state
        collection_summary: Dict[str, Any] = {}
        for r in parallel_results:
            n_name = r["node_name"]
            collection_summary[n_name] = {
                "status": r["status"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "duration_ms": r["duration_ms"],
                "error": r["error"],
            }
            # Record in execution trace
            self.execution_trace.append({
                "step": len(self.execution_trace) + 1,
                "node_name": n_name,
                "execution_mode": "PARALLEL",
                "parallel_group": group_name,
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "duration_ms": r["duration_ms"],
                "status": r["status"],
                "error": r["error"],
            })

        state.collection_status = collection_summary
        state.add_audit_entry(
            node_name=f"ParallelGroup:{group_name}",
            action="PARALLEL_JOIN_COMPLETE",
            details={
                "nodes": node_names,
                "total_duration_ms": round(total_dur, 2),
                "summary": collection_summary,
            },
            status="SUCCESS",
        )
        return state

    def run(
        self,
        initial_node_name: str,
        state: WorkflowState,
        max_steps: int = 20,
    ) -> WorkflowState:
        """Run workflow from initial node until no further transition exists or max steps reached."""
        current_node_name: Optional[str] = initial_node_name
        steps = 0
        visited: List[str] = []

        while current_node_name and steps < max_steps:
            steps += 1
            node = self.nodes.get(current_node_name)
            if not node:
                state.workflow_status = "ERROR"
                state.add_audit_entry(
                    node_name=current_node_name,
                    action="NODE_NOT_FOUND",
                    status="FAILED",
                )
                break

            visited.append(current_node_name)
            t0 = time.perf_counter()
            start_ts = datetime.now(timezone.utc).isoformat()

            try:
                state = node.execute(state)
                dur = (time.perf_counter() - t0) * 1000
                end_ts = datetime.now(timezone.utc).isoformat()
                self.execution_trace.append({
                    "step": len(self.execution_trace) + 1,
                    "node_name": current_node_name,
                    "execution_mode": "SEQUENTIAL",
                    "start_time": start_ts,
                    "end_time": end_ts,
                    "duration_ms": round(dur, 2),
                    "status": "SUCCESS",
                    "error": None,
                })
            except Exception as exc:
                dur = (time.perf_counter() - t0) * 1000
                end_ts = datetime.now(timezone.utc).isoformat()
                self.execution_trace.append({
                    "step": len(self.execution_trace) + 1,
                    "node_name": current_node_name,
                    "execution_mode": "SEQUENTIAL",
                    "start_time": start_ts,
                    "end_time": end_ts,
                    "duration_ms": round(dur, 2),
                    "status": "FAILED",
                    "error": str(exc),
                })
                state.workflow_status = "FAILED"
                state.add_audit_entry(
                    node_name=current_node_name,
                    action="EXECUTION_EXCEPTION",
                    details={"error": str(exc)},
                    status="FAILED",
                )
                raise

            # Stop if terminal state reached
            if state.workflow_status in ("APPROVED_AND_PUBLISHED", "TERMINATED", "REJECTED"):
                break

            # Find next transition
            current_node_name = self.get_next_node(current_node_name, state)

        return state
