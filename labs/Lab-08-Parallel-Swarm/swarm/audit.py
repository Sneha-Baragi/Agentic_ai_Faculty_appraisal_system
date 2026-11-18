"""Audit and Trace Logging for Lab 8 - Parallel Swarm.

Course: Agentic AI (26ECAC401)
Lab: 8 - Parallel Swarm
Scenario: Faculty Appraisal Management System
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AuditLogger:
    """Manages append-only immutable audit trail and execution timeline logging."""

    @staticmethod
    def create_entry(
        node_name: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        status: str = "SUCCESS",
    ) -> Dict[str, Any]:
        """Create a timestamped audit entry."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node_name": node_name,
            "action": action,
            "status": status,
            "details": details or {},
        }

    @staticmethod
    def filter_by_node(audit_log: List[Dict[str, Any]], node_name: str) -> List[Dict[str, Any]]:
        """Filter audit entries by node name."""
        return [e for e in audit_log if e.get("node_name") == node_name]

    @staticmethod
    def filter_by_action(audit_log: List[Dict[str, Any]], action: str) -> List[Dict[str, Any]]:
        """Filter audit entries by action name."""
        return [e for e in audit_log if e.get("action") == action]
