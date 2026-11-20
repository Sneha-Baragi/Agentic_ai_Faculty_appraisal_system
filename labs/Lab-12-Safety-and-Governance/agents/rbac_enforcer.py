"""Role-Based Access Control (RBAC) Governance Agent.

Enforces role boundaries, access governance, and action authorization
across Faculty, HOD, Dean, and Admin security principals.
Pure Python standard library only.
"""
from __future__ import annotations

import logging
from typing import Any

from models.schemas import Action, Role, SecurityContext

logger = logging.getLogger(__name__)


class RBACEnforcer:
    """Enforces fine-grained Role-Based Access Control policies."""

    # Strict Action Permission Matrix
    _PERMISSIONS: dict[Role, set[Action]] = {
        Role.FACULTY: {
            Action.SUBMIT_APPRAISAL,
            Action.VIEW_OWN_APPRAISAL,
        },
        Role.HOD: {
            Action.SUBMIT_APPRAISAL,
            Action.VIEW_OWN_APPRAISAL,
            Action.REVIEW_APPRAISAL,
            Action.APPROVE_APPRAISAL,
        },
        Role.DEAN: {
            Action.SUBMIT_APPRAISAL,
            Action.VIEW_OWN_APPRAISAL,
            Action.REVIEW_APPRAISAL,
            Action.APPROVE_APPRAISAL,
            Action.OVERRIDE_SCORE,
            Action.EXPORT_REPORT,
        },
        Role.ADMIN: {
            Action.SUBMIT_APPRAISAL,
            Action.VIEW_OWN_APPRAISAL,
            Action.REVIEW_APPRAISAL,
            Action.APPROVE_APPRAISAL,
            Action.OVERRIDE_SCORE,
            Action.EXPORT_REPORT,
            Action.MANAGE_USERS,
        },
    }

    def __init__(self) -> None:
        """Initialize RBAC enforcer."""
        pass

    def get_allowed_actions(self, role: Role | str) -> set[Action]:
        """Retrieve set of permitted actions for a role.

        Args:
            role: Security role enum or string.

        Returns:
            Set of permitted :class:`~models.schemas.Action` enums.
        """
        if isinstance(role, str):
            role = Role.from_str(role)
        return self._PERMISSIONS.get(role, set())

    def authorize(
        self,
        context: SecurityContext,
        action: Action | str,
        resource_owner_id: str | None = None,
    ) -> tuple[bool, str]:
        """Authorize an action requested by a security principal.

        Args:
            context: Authenticated caller security context.
            action: Action requested by the caller.
            resource_owner_id: Optional owner id of the targeted appraisal resource.

        Returns:
            Tuple of (allowed: bool, reason: str).
        """
        # Normalize role and action
        role = context.role if isinstance(context.role, Role) else Role.from_str(context.role)
        if isinstance(action, str):
            try:
                action = Action.from_str(action)
            except ValueError as exc:
                return False, f"Unknown action requested: {exc}"

        allowed_actions = self.get_allowed_actions(role)

        # 1. Action-level permission check
        if action not in allowed_actions:
            reason = (
                f"Role escalation violation: Role '{role.value}' is not permitted "
                f"to execute action '{action.value}'. Required permissions: "
                f"{[a.value for a in allowed_actions]}"
            )
            logger.warning("RBAC REJECTED: %s (Actor: %s)", reason, context.actor_id)
            return False, reason

        # 2. Resource-level ownership check for VIEW_OWN_APPRAISAL
        if action == Action.VIEW_OWN_APPRAISAL and resource_owner_id:
            if role == Role.FACULTY and resource_owner_id != context.actor_id:
                reason = (
                    f"Resource boundary violation: Faculty user '{context.actor_id}' "
                    f"attempted to view appraisal of faculty '{resource_owner_id}'."
                )
                logger.warning("RBAC REJECTED: %s", reason)
                return False, reason

        logger.debug(
            "RBAC ALLOWED: Actor '%s' (Role: '%s') authorized for '%s'.",
            context.actor_id,
            role.value,
            action.value,
        )
        return True, f"Action '{action.value}' authorized for role '{role.value}'."
