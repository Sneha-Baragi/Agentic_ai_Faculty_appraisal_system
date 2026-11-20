"""End-to-End integration tests for all governance scenarios.

Loads fixture scenarios from data/governance_fixtures.json and executes them
through the GovernanceEngine, asserting correctness against expected outcomes.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
import sys

_LAB_ROOT = Path(__file__).resolve().parent.parent
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from governance.governance_engine import GovernanceEngine
from models.schemas import Action, Role, SecurityContext


class TestEndToEndGovernance(unittest.TestCase):
    """End-to-end integration tests over realistic academic appraisal scenarios."""

    def setUp(self) -> None:
        self.fixture_file = _LAB_ROOT / "data" / "governance_fixtures.json"
        with open(self.fixture_file, "r", encoding="utf-8") as f:
            self.scenarios = json.load(f)
        self.engine = GovernanceEngine()

    def test_all_scenarios_execute_with_expected_verdicts(self) -> None:
        """Every fixture scenario must execute and yield its expected status."""
        for sc in self.scenarios:
            with self.subTest(scenario_id=sc["scenario_id"]):
                actor = sc["actor"]
                ctx = SecurityContext(
                    actor_id=actor["actor_id"],
                    role=Role.from_str(actor["role"]),
                    ip_address=actor.get("ip_address", "127.0.0.1"),
                    session_id=actor.get("session_id", "sess-test"),
                )
                action = Action.from_str(sc["action"])
                payload = sc.get("payload", {})
                res_owner = sc.get("resource_owner_id")

                report = self.engine.process_request(
                    context=ctx,
                    action=action,
                    payload=payload,
                    resource_owner_id=res_owner,
                )

                expected_status = sc.get("expected_status")
                self.assertEqual(
                    report.status,
                    expected_status,
                    f"Scenario '{sc['scenario_id']}' failed: expected status '{expected_status}', got '{report.status}'",
                )

                if "expected_rbac_allowed" in sc:
                    self.assertEqual(
                        report.rbac_allowed,
                        sc["expected_rbac_allowed"],
                        f"Scenario '{sc['scenario_id']}' RBAC allowed mismatch",
                    )

                if "expected_guardrail_allowed" in sc and report.guardrail_result:
                    self.assertEqual(
                        report.guardrail_result.allowed,
                        sc["expected_guardrail_allowed"],
                        f"Scenario '{sc['scenario_id']}' Guardrail allowed mismatch",
                    )

    def test_audit_chain_integrity_after_all_scenarios(self) -> None:
        """After executing all scenarios, the entire ledger chain must verify intact."""
        for sc in self.scenarios:
            actor = sc["actor"]
            ctx = SecurityContext(
                actor_id=actor["actor_id"],
                role=Role.from_str(actor["role"]),
            )
            self.engine.process_request(
                context=ctx,
                action=Action.from_str(sc["action"]),
                payload=sc.get("payload", {}),
            )

        is_valid, broken_idx, msg = self.engine.audit_ledger.verify_integrity()
        self.assertTrue(is_valid, f"Ledger integrity failed: {msg}")
        self.assertIsNone(broken_idx)
        self.assertEqual(len(self.engine.audit_ledger), len(self.scenarios))


if __name__ == "__main__":
    unittest.main()
