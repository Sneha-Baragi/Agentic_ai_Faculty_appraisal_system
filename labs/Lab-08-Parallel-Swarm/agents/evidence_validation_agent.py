"""Evidence Validation Specialist Agent for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.schemas import WorkflowState


class EvidenceValidationAgent:
    """Validates merged appraisal activities against the official institutional evidence registry."""

    def __init__(self, evidence_path: Optional[Path] = None) -> None:
        """Initialize evidence validation agent with path to mock evidence registry."""
        if evidence_path is None:
            self.evidence_path = Path(__file__).resolve().parent.parent / "data" / "mock_evidence.json"
        else:
            self.evidence_path = Path(evidence_path)

    def execute(self, state: WorkflowState) -> WorkflowState:
        """Validate all merged activities across the parallel swarm collectors.

        Classifies claims into:
        - VERIFIED: Evidence exists in registry, valid status, matches faculty_id, and matches category.
        - MISSING_EVIDENCE: Evidence reference is blank or not found in registry.
        - MISMATCHED_EVIDENCE: Evidence belongs to another faculty or wrong category.
        - INCOMPLETE: Missing mandatory title or non-positive claimed points.

        Rules:
        - Every claim is annotated with its evidence status and validation notes.
        - Exceptions are gathered in state.evidence_exceptions.
        - Unresolved exceptions block final scoring approval and report publication.
        """
        # Load evidence registry
        evidence_registry: Dict[str, Dict[str, Any]] = {}
        if self.evidence_path.exists():
            with open(self.evidence_path, "r", encoding="utf-8") as f:
                records = json.load(f)
                evidence_registry = {r["evidence_id"]: r for r in records}

        activities = state.merged_activities
        validated: List[Dict[str, Any]] = []
        exceptions: List[Dict[str, Any]] = []

        counts = {
            "total_evaluated": len(activities),
            "verified_count": 0,
            "missing_count": 0,
            "mismatched_count": 0,
            "incomplete_count": 0,
        }

        for act in activities:
            act_copy = dict(act)
            ev_ref = act_copy.get("evidence_ref")

            # Check 1: Incomplete claim data
            if not act_copy.get("title") or act_copy.get("claimed_points") is None or act_copy.get("claimed_points", 0) <= 0:
                act_copy["evidence_status"] = "INCOMPLETE"
                act_copy["validation_notes"] = "Claim lacks mandatory title or valid positive points."
                counts["incomplete_count"] += 1
                exceptions.append(act_copy)
                validated.append(act_copy)
                continue

            # Check 2: Missing evidence reference
            if not ev_ref or ev_ref not in evidence_registry:
                act_copy["evidence_status"] = "MISSING_EVIDENCE"
                act_copy["validation_notes"] = f"Evidence reference '{ev_ref}' not found in official registry."
                counts["missing_count"] += 1
                exceptions.append(act_copy)
                validated.append(act_copy)
                continue

            evidence_rec = evidence_registry[ev_ref]

            # Check 3: Faculty ID mismatch
            if evidence_rec.get("faculty_id") != state.faculty_id:
                act_copy["evidence_status"] = "MISMATCHED_EVIDENCE"
                act_copy["validation_notes"] = (
                    f"Faculty ID mismatch: evidence document belongs to '{evidence_rec.get('faculty_id')}', "
                    f"claimed by '{state.faculty_id}'."
                )
                counts["mismatched_count"] += 1
                exceptions.append(act_copy)
                validated.append(act_copy)
                continue

            # Check 4: Category mismatch
            if evidence_rec.get("category") != act_copy.get("category"):
                act_copy["evidence_status"] = "MISMATCHED_EVIDENCE"
                act_copy["validation_notes"] = (
                    f"Category mismatch: evidence registered under '{evidence_rec.get('category')}', "
                    f"claimed under '{act_copy.get('category')}'."
                )
                counts["mismatched_count"] += 1
                exceptions.append(act_copy)
                validated.append(act_copy)
                continue

            # Check 5: Document status validity
            if evidence_rec.get("status") != "VALID":
                act_copy["evidence_status"] = "MISMATCHED_EVIDENCE"
                act_copy["validation_notes"] = f"Evidence certificate status is invalid ({evidence_rec.get('status')})."
                counts["mismatched_count"] += 1
                exceptions.append(act_copy)
                validated.append(act_copy)
                continue

            # Verification passed
            act_copy["evidence_status"] = "VERIFIED"
            act_copy["validation_notes"] = f"Verified against '{evidence_rec.get('document_name')}' ({evidence_rec.get('verified_checksum')})."
            counts["verified_count"] += 1
            validated.append(act_copy)

        state.validated_activities = validated
        state.evidence_exceptions = exceptions
        state.workflow_status = "VALIDATED"

        state.add_audit_entry(
            node_name="EvidenceValidationAgent",
            action="EVIDENCE_VALIDATION_COMPLETE",
            details={
                "metrics": counts,
                "exceptions_count": len(exceptions),
                "is_clean": len(exceptions) == 0,
            },
            status="WARNING" if len(exceptions) > 0 else "SUCCESS",
        )

        return state
