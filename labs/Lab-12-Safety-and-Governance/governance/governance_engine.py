"""Governance Engine: Orchestrates end-to-end safety, security & audit policies.

Coordinates the 6-stage governance pipeline:
1. Role-Based Access Control (RBACEnforcer)
2. Prompt Injection & Adversarial Guardrails (PromptGuard)
3. Sensitive Data & PII Redaction (PIIRedactor)
4. Safe Agent Execution & Appraisal Computation
5. Output Guardrail Validation & Sanity Verification
6. Cryptographic Hash-Chained Audit Ledger (AuditLedger)

Pure Python standard library only.
"""
from __future__ import annotations

import datetime
import logging
import time
import uuid
from typing import Any

from agents.audit_ledger import AuditLedger
from agents.pii_redactor import PIIRedactor
from agents.prompt_guard import PromptGuard
from agents.rbac_enforcer import RBACEnforcer
from models.schemas import (
    Action,
    AuditEntry,
    GovernanceReport,
    GuardrailResult,
    PIIRedactionResult,
    Role,
    SecurityContext,
    ThreatLevel,
)
from tools.hash_chain import compute_payload_hash

logger = logging.getLogger(__name__)


class GovernanceEngine:
    """End-to-end governance and safety pipeline orchestrator."""

    def __init__(
        self,
        rbac_enforcer: RBACEnforcer | None = None,
        prompt_guard: PromptGuard | None = None,
        pii_redactor: PIIRedactor | None = None,
        audit_ledger: AuditLedger | None = None,
    ) -> None:
        """Initialize governance pipeline components."""
        self.rbac = rbac_enforcer or RBACEnforcer()
        self.prompt_guard = prompt_guard or PromptGuard()
        self.pii_redactor = pii_redactor or PIIRedactor()
        self.audit_ledger = audit_ledger or AuditLedger()

    def process_request(
        self,
        context: SecurityContext,
        action: Action | str,
        payload: dict[str, Any] | str | None = None,
        resource_owner_id: str | None = None,
    ) -> GovernanceReport:
        """Process an incoming request through the multi-stage governance pipeline.

        Args:
            context: Authenticated security context of the caller.
            action: Action requested by the caller.
            payload: Request payload (claims text, appraisal submission, or params).
            resource_owner_id: Optional ID of the resource owner for boundary checks.

        Returns:
            Comprehensive :class:`~models.schemas.GovernanceReport`.
        """
        start_time = time.perf_counter()
        request_id = f"gov-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Normalize action
        if isinstance(action, str):
            try:
                action = Action.from_str(action)
            except ValueError as exc:
                action_str = str(action)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                audit_entry = self.audit_ledger.append_entry(
                    actor_id=context.actor_id,
                    role=context.role.value if isinstance(context.role, Role) else str(context.role),
                    action=action_str,
                    status="REJECTED",
                    payload={"error": str(exc)},
                    timestamp=timestamp,
                )
                return GovernanceReport(
                    request_id=request_id,
                    timestamp=timestamp,
                    security_context=context,
                    action=action_str,
                    status="REJECTED",
                    rbac_allowed=False,
                    rbac_reason=f"Unknown action: {exc}",
                    audit_entry=audit_entry,
                    pipeline_duration_ms=round(elapsed_ms, 2),
                )

        action_name = action.value
        role_name = context.role.value if isinstance(context.role, Role) else str(context.role)

        # -------------------------------------------------------------------
        # STAGE 1: RBAC Permission & Role Boundary Check
        # -------------------------------------------------------------------
        rbac_allowed, rbac_reason = self.rbac.authorize(
            context=context,
            action=action,
            resource_owner_id=resource_owner_id,
        )

        if not rbac_allowed:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            audit_entry = self.audit_ledger.append_entry(
                actor_id=context.actor_id,
                role=role_name,
                action=action_name,
                status="REJECTED",
                payload={"violation": rbac_reason, "target_owner": resource_owner_id},
                timestamp=timestamp,
            )
            return GovernanceReport(
                request_id=request_id,
                timestamp=timestamp,
                security_context=context,
                action=action,
                status="REJECTED",
                rbac_allowed=False,
                rbac_reason=rbac_reason,
                guardrail_result=None,
                pii_result=None,
                audit_entry=audit_entry,
                pipeline_duration_ms=round(elapsed_ms, 2),
            )

        # -------------------------------------------------------------------
        # STAGE 2: Prompt Injection & Adversarial Content Guardrails
        # -------------------------------------------------------------------
        # Extract textual content from payload
        text_to_scan = self._extract_text(payload)
        guardrail_result = self.prompt_guard.evaluate(
            text=text_to_scan,
            context={"actor_id": context.actor_id, "action": action_name},
        )

        if not guardrail_result.allowed:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            audit_entry = self.audit_ledger.append_entry(
                actor_id=context.actor_id,
                role=role_name,
                action=action_name,
                status="BLOCKED",
                payload={
                    "threat_level": guardrail_result.threat_level.value,
                    "violations": guardrail_result.violations,
                    "raw_text_snippet": text_to_scan[:120],
                },
                timestamp=timestamp,
            )
            return GovernanceReport(
                request_id=request_id,
                timestamp=timestamp,
                security_context=context,
                action=action,
                status="BLOCKED",
                rbac_allowed=True,
                rbac_reason=rbac_reason,
                guardrail_result=guardrail_result,
                pii_result=None,
                audit_entry=audit_entry,
                pipeline_duration_ms=round(elapsed_ms, 2),
            )

        # -------------------------------------------------------------------
        # STAGE 3: Sensitive PII Redaction
        # -------------------------------------------------------------------
        pii_result = self.pii_redactor.redact(text_to_scan)
        sanitized_payload = self._apply_redaction(payload, pii_result.redacted_text)

        # -------------------------------------------------------------------
        # STAGE 4: Safe Execution / Business Logic
        # -------------------------------------------------------------------
        exec_result = self._execute_action(
            action=action,
            context=context,
            payload=sanitized_payload,
        )

        # -------------------------------------------------------------------
        # STAGE 5: Output Guardrail Validation
        # -------------------------------------------------------------------
        output_passed, output_issues = self._validate_output(exec_result)

        # -------------------------------------------------------------------
        # STAGE 6: Cryptographic Audit Logging
        # -------------------------------------------------------------------
        final_status = "APPROVED" if output_passed else "FLAGGED"
        audit_entry = self.audit_ledger.append_entry(
            actor_id=context.actor_id,
            role=role_name,
            action=action_name,
            status=final_status,
            payload=exec_result,
            timestamp=timestamp,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return GovernanceReport(
            request_id=request_id,
            timestamp=timestamp,
            security_context=context,
            action=action,
            status=final_status,
            rbac_allowed=True,
            rbac_reason=rbac_reason,
            guardrail_result=guardrail_result,
            pii_result=pii_result,
            execution_result=exec_result,
            output_guardrail_passed=output_passed,
            audit_entry=audit_entry,
            pipeline_duration_ms=round(elapsed_ms, 2),
        )

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _extract_text(self, payload: Any) -> str:
        """Extract text content to be scanned for guardrails and PII."""
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            # Prioritize claims_text, remarks, or notes
            candidates = [
                payload.get("claims_text"),
                payload.get("remarks"),
                payload.get("feedback"),
                payload.get("comments"),
                payload.get("summary"),
            ]
            for c in candidates:
                if isinstance(c, str) and c.strip():
                    return c
            # Fallback to stringified values
            return " ".join(str(v) for v in payload.values())
        if hasattr(payload, "claims_text"):
            return getattr(payload, "claims_text", "")
        return str(payload)

    def _apply_redaction(self, payload: Any, redacted_text: str) -> Any:
        """Apply redacted text back into payload structure."""
        if isinstance(payload, dict):
            new_payload = dict(payload)
            if "claims_text" in new_payload:
                new_payload["claims_text"] = redacted_text
            elif "remarks" in new_payload:
                new_payload["remarks"] = redacted_text
            elif "feedback" in new_payload:
                new_payload["feedback"] = redacted_text
            return new_payload
        if hasattr(payload, "claims_text"):
            # Dataclass or object with claims_text
            try:
                data = payload.to_dict() if hasattr(payload, "to_dict") else dict(payload.__dict__)
                data["claims_text"] = redacted_text
                return data
            except Exception:
                pass
        return payload

    def _execute_action(
        self,
        action: Action,
        context: SecurityContext,
        payload: Any,
    ) -> dict[str, Any]:
        """Simulate authorized domain logic execution safely."""
        p_dict = payload if isinstance(payload, dict) else {}

        if action == Action.SUBMIT_APPRAISAL:
            # Score verification logic bounded between 0 and 100
            raw_score = float(p_dict.get("self_appraisal_score", 75.0))
            bounded_score = max(0.0, min(100.0, raw_score))
            return {
                "operation": "SUBMIT_APPRAISAL",
                "faculty_id": p_dict.get("faculty_id", context.actor_id),
                "department": p_dict.get("department", "Computer Science & Engineering"),
                "academic_year": p_dict.get("academic_year", "2024-2025"),
                "verified_score": bounded_score,
                "sanitized_claims": p_dict.get("claims_text", ""),
                "processing_status": "SUBMITTED_FOR_HOD_REVIEW",
            }

        elif action == Action.VIEW_OWN_APPRAISAL:
            return {
                "operation": "VIEW_OWN_APPRAISAL",
                "faculty_id": context.actor_id,
                "access_granted": True,
                "record_count": 1,
                "current_status": "UNDER_REVIEW",
            }

        elif action == Action.REVIEW_APPRAISAL:
            return {
                "operation": "REVIEW_APPRAISAL",
                "reviewer_id": context.actor_id,
                "target_faculty_id": p_dict.get("faculty_id", "FAC-UNKNOWN"),
                "review_recommendation": p_dict.get("recommendation", "RECOMMENDED"),
                "review_remarks": p_dict.get("remarks", "Appraisal verified against departmental benchmarks."),
            }

        elif action == Action.APPROVE_APPRAISAL:
            return {
                "operation": "APPROVE_APPRAISAL",
                "approver_id": context.actor_id,
                "target_faculty_id": p_dict.get("faculty_id", "FAC-UNKNOWN"),
                "approval_status": "APPROVED",
                "final_rating": p_dict.get("final_rating", "VERY_GOOD"),
            }

        elif action == Action.OVERRIDE_SCORE:
            override_val = float(p_dict.get("override_score", 85.0))
            bounded_val = max(0.0, min(100.0, override_val))
            return {
                "operation": "OVERRIDE_SCORE",
                "dean_id": context.actor_id,
                "target_faculty_id": p_dict.get("faculty_id", "FAC-UNKNOWN"),
                "original_score": float(p_dict.get("original_score", 70.0)),
                "override_score": bounded_val,
                "justification": p_dict.get("justification", "Institutional merit adjustment approved by Dean."),
            }

        elif action == Action.EXPORT_REPORT:
            return {
                "operation": "EXPORT_REPORT",
                "exported_by": context.actor_id,
                "scope": p_dict.get("scope", "INSTITUTE_WIDE"),
                "format": "JSON_CSV",
                "total_records": p_dict.get("count", 42),
            }

        elif action == Action.MANAGE_USERS:
            return {
                "operation": "MANAGE_USERS",
                "admin_id": context.actor_id,
                "action_type": p_dict.get("sub_action", "AUDIT_USER_ROLES"),
                "affected_users": p_dict.get("users", ["FAC-001", "HOD-CSE"]),
            }

        return {"operation": str(action.value), "status": "COMPLETED"}

    def _validate_output(self, result: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate execution results against output safety guardrails.

        Ensures:
        1. Numerical scores are within [0.0, 100.0].
        2. No unredacted sensitive tokens or system leaks.
        """
        issues: list[str] = []

        # Check score bounds
        for key in ("verified_score", "override_score", "final_score"):
            if key in result:
                val = result[key]
                if not isinstance(val, (int, float)) or val < 0.0 or val > 100.0:
                    issues.append(f"Output score '{key}' = {val} out of permitted [0, 100] bounds.")

        # Check for unredacted leaked secrets
        result_str = str(result)
        if "BEGIN PRIVATE KEY" in result_str or "SYSTEM_TOKEN_SECRET" in result_str:
            issues.append("Secret leakage detected in output structure.")

        return len(issues) == 0, issues
