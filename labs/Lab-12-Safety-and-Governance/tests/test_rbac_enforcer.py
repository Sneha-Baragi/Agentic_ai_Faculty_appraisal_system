"""Unit tests for RBACEnforcer agent.

Tests role permissions matrix, boundary enforcement, and authorization decisions.
"""
from __future__ import annotations

import unittest
from pathlib import Path
import sys

_LAB_ROOT = Path(__file__).resolve().parent.parent
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from agents.rbac_enforcer import RBACEnforcer
from models.schemas import Action, Role, SecurityContext


class TestRBACEnforcer(unittest.TestCase):
    """Test suite for Role-Based Access Control enforcement."""

    def setUp(self) -> None:
        self.rbac = RBACEnforcer()

    def test_faculty_permissions(self) -> None:
        """Faculty can submit and view their own appraisal, but cannot review or approve."""
        ctx = SecurityContext(actor_id="FAC-001", role=Role.FACULTY)

        # Permitted
        allowed, _ = self.rbac.authorize(ctx, Action.SUBMIT_APPRAISAL)
        self.assertTrue(allowed)

        allowed, _ = self.rbac.authorize(ctx, Action.VIEW_OWN_APPRAISAL, resource_owner_id="FAC-001")
        self.assertTrue(allowed)

        # Denied
        allowed, reason = self.rbac.authorize(ctx, Action.APPROVE_APPRAISAL)
        self.assertFalse(allowed)
        self.assertIn("Role escalation violation", reason)

        allowed, _ = self.rbac.authorize(ctx, Action.REVIEW_APPRAISAL)
        self.assertFalse(allowed)

        allowed, _ = self.rbac.authorize(ctx, Action.OVERRIDE_SCORE)
        self.assertFalse(allowed)

        allowed, _ = self.rbac.authorize(ctx, Action.MANAGE_USERS)
        self.assertFalse(allowed)

    def test_faculty_resource_boundary(self) -> None:
        """Faculty cannot view appraisal of another faculty member."""
        ctx = SecurityContext(actor_id="FAC-001", role=Role.FACULTY)
        allowed, reason = self.rbac.authorize(
            ctx, Action.VIEW_OWN_APPRAISAL, resource_owner_id="FAC-002"
        )
        self.assertFalse(allowed)
        self.assertIn("Resource boundary violation", reason)

    def test_hod_permissions(self) -> None:
        """HOD can submit, view, review, and approve appraisals, but not override score."""
        ctx = SecurityContext(actor_id="HOD-CSE-01", role=Role.HOD)

        self.assertTrue(self.rbac.authorize(ctx, Action.SUBMIT_APPRAISAL)[0])
        self.assertTrue(self.rbac.authorize(ctx, Action.REVIEW_APPRAISAL)[0])
        self.assertTrue(self.rbac.authorize(ctx, Action.APPROVE_APPRAISAL)[0])

        # HOD cannot override score or manage users
        allowed_override, _ = self.rbac.authorize(ctx, Action.OVERRIDE_SCORE)
        self.assertFalse(allowed_override)

        allowed_manage, _ = self.rbac.authorize(ctx, Action.MANAGE_USERS)
        self.assertFalse(allowed_manage)

    def test_dean_permissions(self) -> None:
        """Dean can review, approve, override score, and export reports."""
        ctx = SecurityContext(actor_id="DEAN-ENGG-01", role=Role.DEAN)

        self.assertTrue(self.rbac.authorize(ctx, Action.REVIEW_APPRAISAL)[0])
        self.assertTrue(self.rbac.authorize(ctx, Action.APPROVE_APPRAISAL)[0])
        self.assertTrue(self.rbac.authorize(ctx, Action.OVERRIDE_SCORE)[0])
        self.assertTrue(self.rbac.authorize(ctx, Action.EXPORT_REPORT)[0])

        # Dean cannot manage users (reserved for Admin)
        allowed_manage, _ = self.rbac.authorize(ctx, Action.MANAGE_USERS)
        self.assertFalse(allowed_manage)

    def test_admin_permissions(self) -> None:
        """Admin has full authorization across all governed actions."""
        ctx = SecurityContext(actor_id="ADMIN-ROOT-01", role=Role.ADMIN)

        for action in Action:
            allowed, _ = self.rbac.authorize(ctx, action)
            self.assertTrue(allowed, f"Admin should be permitted to execute {action.value}")

    def test_invalid_action_rejected(self) -> None:
        """Unknown action strings should be safely rejected."""
        ctx = SecurityContext(actor_id="ADMIN-01", role=Role.ADMIN)
        allowed, reason = self.rbac.authorize(ctx, "non_existent_action")
        self.assertFalse(allowed)
        self.assertIn("Unknown action", reason)


if __name__ == "__main__":
    unittest.main()
