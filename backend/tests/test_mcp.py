import pytest

import backend.app.mcp.connector as connector_module
from backend.app.mcp.connector import get_mcp_tool, get_mcp_tools

EXPECTED_TOOL_KEYS = {
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

EXCLUDED_TOOL_NAMES = {
    "create_timetable",
    "delete_timetable",
    "mark_attendance",
    "create_project_team",
    "delete_project_team",
    "validate_evidence",
}


def test_exposed_tool_set():
    tools = get_mcp_tools()

    assert isinstance(tools, dict)
    assert len(tools) == 15
    assert set(tools.keys()) == EXPECTED_TOOL_KEYS


def test_write_tools_are_excluded():
    tools = get_mcp_tools()

    for name in EXCLUDED_TOOL_NAMES:
        assert name not in tools


def test_get_mcp_tool_returns_registry_callable():
    tools = get_mcp_tools()
    tool = get_mcp_tool("get_faculty_profile")

    assert callable(tool)
    assert tool is tools["get_faculty_profile"]


def test_get_mcp_tool_unknown_name_raises_value_error():
    with pytest.raises(ValueError) as exc_info:
        get_mcp_tool("does_not_exist")

    message = str(exc_info.value)
    assert "does_not_exist" in message
    assert "Unknown MCP tool" in message


def test_connector_exposes_existing_registry_callables():
    tools = get_mcp_tools()

    for name, callable_obj in tools.items():
        assert callable_obj is connector_module.TOOL_REGISTRY[name]
