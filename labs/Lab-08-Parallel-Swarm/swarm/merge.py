"""Swarm Merge and Synchronization Stage.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from typing import Any, Dict, List, Optional, Set

from models.schemas import MergeResult, WorkflowState


class SwarmMerge:
    """Synchronizes, validates, and merges isolated outputs from the parallel swarm."""

    EXPECTED_COLLECTORS = [
        "ResearchDataCollectionAgent",
        "TeachingDataCollectionAgent",
        "AdministrativeDataCollectionAgent",
    ]

    def merge(self, state: WorkflowState) -> WorkflowState:
        """Merge isolated collector results into a synchronized unified collection.

        Requirements enforced:
        - Verifies that all expected agents have returned a valid result or explicit error.
        - Combines the normalized activity collections.
        - Preserves originating agent (`collector_role`) and source metadata (`source_system`).
        - Detects duplicate activity IDs and conflicting claims across collectors.
        - Never silently overwrites one agent's output with another.
        - Reports missing or failed collection results.
        - Passes merged activities to downstream validation only after join is complete.

        Args:
            state: WorkflowState containing populated swarm_results.

        Returns:
            Updated WorkflowState with merged_activities and merge_result.
        """
        swarm_results = state.swarm_results or {}

        # 1. Verify expected collectors
        failed_collectors: List[str] = []
        skipped_collectors: List[str] = []
        successful_collectors: List[str] = []
        missing_collectors: List[str] = []

        for expected_role in self.EXPECTED_COLLECTORS:
            if expected_role not in swarm_results:
                missing_collectors.append(expected_role)
                continue

            res = swarm_results[expected_role]
            status = res.get("status")
            if status == "FAILED":
                failed_collectors.append(expected_role)
            elif status == "SKIPPED":
                skipped_collectors.append(expected_role)
            elif status == "SUCCESS":
                successful_collectors.append(expected_role)
            else:
                failed_collectors.append(expected_role)

        # 2. Combine activities with duplicate and conflict detection
        seen_activity_ids: Dict[str, Dict[str, Any]] = {}
        duplicates_detected: List[Dict[str, Any]] = []
        conflicts_detected: List[Dict[str, Any]] = []
        merged_activities: List[Dict[str, Any]] = []

        for role_name in self.EXPECTED_COLLECTORS:
            if role_name not in swarm_results:
                continue

            collector_data = swarm_results[role_name]
            if collector_data.get("status") != "SUCCESS":
                continue

            activities = collector_data.get("activities", [])
            for act in activities:
                act_copy = dict(act)
                # Ensure originating role and source metadata are preserved
                act_copy["collector_role"] = role_name
                act_id = act_copy.get("activity_id")

                if act_id in seen_activity_ids:
                    # Duplicate detected
                    prior_act = seen_activity_ids[act_id]
                    duplicates_detected.append({
                        "activity_id": act_id,
                        "first_collector": prior_act.get("collector_role"),
                        "duplicate_collector": role_name,
                        "title": act_copy.get("title"),
                    })

                    # Check for conflicting claims
                    if (
                        prior_act.get("category") != act_copy.get("category")
                        or prior_act.get("claimed_points") != act_copy.get("claimed_points")
                        or prior_act.get("title") != act_copy.get("title")
                    ):
                        conflicts_detected.append({
                            "activity_id": act_id,
                            "first_claim": {
                                "collector": prior_act.get("collector_role"),
                                "category": prior_act.get("category"),
                                "claimed_points": prior_act.get("claimed_points"),
                                "title": prior_act.get("title"),
                            },
                            "conflicting_claim": {
                                "collector": role_name,
                                "category": act_copy.get("category"),
                                "claimed_points": act_copy.get("claimed_points"),
                                "title": act_copy.get("title"),
                            },
                        })

                    # Do NOT silently overwrite the prior agent's activity
                    # Rename duplicate key to preserve both without data loss
                    act_copy["activity_id"] = f"{act_id}_DUP_{role_name}"
                    act_copy["is_duplicate"] = True

                seen_activity_ids[act_id] = act_copy
                merged_activities.append(act_copy)

        # 3. Determine merge status
        if len(failed_collectors) > 0 or len(missing_collectors) > 0:
            if len(successful_collectors) == 0:
                merge_status = "FAILED"
            else:
                merge_status = "PARTIAL"
            state.workflow_status = "INCOMPLETE_COLLECTION"
        elif len(skipped_collectors) > 0:
            merge_status = "CONSENT_LIMITED"
            state.workflow_status = "MERGED"
        else:
            merge_status = "SUCCESS"
            state.workflow_status = "MERGED"

        merge_obj = MergeResult(
            status=merge_status,
            total_activities=len(merged_activities),
            duplicates_detected=duplicates_detected,
            conflicts_detected=conflicts_detected,
            failed_collectors=failed_collectors + missing_collectors,
            skipped_collectors=skipped_collectors,
            merged_activities=merged_activities,
        )

        state.merge_result = merge_obj.to_dict()
        state.merged_activities = merged_activities

        state.add_audit_entry(
            node_name="SwarmMerge",
            action="SWARM_MERGE_COMPLETE",
            details={
                "merge_status": merge_status,
                "total_merged": len(merged_activities),
                "successful_collectors": successful_collectors,
                "failed_collectors": failed_collectors + missing_collectors,
                "skipped_collectors": skipped_collectors,
                "duplicates_count": len(duplicates_detected),
                "conflicts_count": len(conflicts_detected),
            },
            status="WARNING" if merge_status != "SUCCESS" or len(duplicates_detected) > 0 else "SUCCESS",
        )

        return state
