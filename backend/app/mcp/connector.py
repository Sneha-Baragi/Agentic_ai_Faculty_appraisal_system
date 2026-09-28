"""Thin MCP-style connector adapter for existing read-only appraisal tools.

This module is intentionally not a networked MCP server or a new database layer.
It simply exposes the app's existing authorized tool functions through a small,
read-only registry, delegating to the established tool implementations.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.tools import TOOL_REGISTRY

_READ_ONLY_TOOL_NAMES = {
    "get_faculty_profile",
    "get_appraisal_cycle",
    "get_faculty_activities",
    "read_teaching_records",
    "read_research_records",
    "read_service_records",
    "read_student_feedback",
    "get_evidence",
    "calculate_appraisal_score",
    "generate_appraisal_report",
    "retrieve_previous_appraisal",
    "get_teaching_requirement",
    "list_timetable",
    "list_attendance",
    "list_project_teams",
}


def get_mcp_tools() -> dict[str, Callable[..., Any]]:
    """Return the read-only registry of externally exposed appraisal tools.

    The connector delegates to the existing TOOL_REGISTRY from the tool layer so
    the app preserves its current authorization, auditing, and DB access patterns.
    """
    registry = {name: TOOL_REGISTRY[name] for name in sorted(_READ_ONLY_TOOL_NAMES) if name in TOOL_REGISTRY}
    missing = sorted(_READ_ONLY_TOOL_NAMES - set(registry))
    if missing:
        raise ValueError(f"Missing read-only MCP tools in TOOL_REGISTRY: {missing}")
    return registry


def get_mcp_tool(name: str) -> Callable[..., Any]:
    """Return a named MCP-style tool callable or raise for unknown names."""
    tools = get_mcp_tools()
    if name not in tools:
        raise ValueError(f"Unknown MCP tool: {name}")
    return tools[name]
