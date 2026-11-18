"""DataAssistant Agent Implementation.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Scenario: Multi-Source Assistant Agent

The DataAssistant agent acts as the reasoning layer:
1. Discovers server capabilities dynamically through the MCPClient.
2. Selects the appropriate capability (resource or tool) for a user request.
3. Formulates structured arguments matching the capability input schema.
4. Invokes the capability via the client connector.
5. Synthesizes a factual, grounded final answer and concise summary.
6. Records complete end-to-end execution traces for auditability and transparency.
"""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from client.mcp_client import MCPClient


class DataAssistant:
    """Agent that integrates with heterogeneous data sources through an MCP client."""

    def __init__(
        self,
        client: MCPClient,
        caller_id: str = "data_assistant",
    ) -> None:
        """Initialize DataAssistant with an MCP client connector.

        Args:
            client: The MCPClient instance to communicate with.
            caller_id: Authorized caller identifier for database queries.
        """
        self.client = client
        self.caller_id = caller_id
        self.traces: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # TRACE MANAGEMENT
    # -------------------------------------------------------------------------

    def get_traces(self) -> List[Dict[str, Any]]:
        """Return all recorded execution traces."""
        return list(self.traces)

    def clear_traces(self) -> None:
        """Reset the execution trace history."""
        self.traces.clear()

    def export_trace_json(self, indent: int = 2) -> str:
        """Export all execution traces as a JSON string."""
        return json.dumps(self.traces, indent=indent, default=str)

    # -------------------------------------------------------------------------
    # CAPABILITY SELECTION & REASONING (DYNAMIC MANIFEST DRIVEN)
    # -------------------------------------------------------------------------

    def _select_capability(
        self, user_request: str, manifest: Dict[str, Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[str], str, Dict[str, Any]]:
        """Analyze user request against discovered capabilities.

        Returns:
            Tuple of (capability_name, capability_kind, selection_reason, kwargs).
        """
        req_lower = user_request.lower().strip()

        # Check for list files (Assignment 1 capability)
        if "list_files" in manifest and any(
            kw in req_lower
            for kw in [
                "list the available files",
                "list files",
                "list available files",
                "what files exist",
                "available files",
                "show files",
                "directory contents",
            ]
        ):
            return (
                "list_files",
                manifest["list_files"]["kind"],
                "User requested a listing of accessible files; selected 'list_files' resource.",
                {"subdir": ""},
            )

        # Check for database queries (tool)
        if "query_db" in manifest and any(
            kw in req_lower
            for kw in [
                "signup",
                "signups",
                "database",
                "sql",
                "select ",
                "count",
                "registered",
                "how many people",
                "attendance count",
            ]
        ):
            # Extract or default SQL query
            sql = "SELECT event, count FROM signups;"
            # If user explicitly wrote a SELECT statement, preserve it
            select_match = re.search(r"(SELECT\s+.+?;?)", user_request, re.IGNORECASE)
            if select_match:
                sql = select_match.group(1).strip()
                if not sql.endswith(";"):
                    sql += ";"

            return (
                "query_db",
                manifest["query_db"]["kind"],
                "User asked for structured signup counts; selected 'query_db' tool to execute read-only SQL.",
                {"sql": sql, "caller_id": self.caller_id},
            )

        # Check for local API calls (tool)
        if "call_api" in manifest and any(
            kw in req_lower
            for kw in [
                "today",
                "events today",
                "happening today",
                "scheduled today",
                "api",
                "current events",
                "status",
            ]
        ):
            endpoint = "events_today"
            if "status" in req_lower and "event" not in req_lower:
                endpoint = "system_status"
            return (
                "call_api",
                manifest["call_api"]["kind"],
                f"User requested real-time campus event schedule; selected 'call_api' tool with endpoint '{endpoint}'.",
                {"endpoint": endpoint, "params": {}},
            )

        # Check for file reading (resource)
        if "read_file" in manifest and any(
            kw in req_lower
            for kw in [
                "read",
                "readme",
                "announcement",
                "view",
                "content",
                ".md",
                ".txt",
                ".env",
                ".ini",
            ]
        ):
            # Determine target file path
            file_path = "README.md"
            if "announcement" in req_lower:
                file_path = "announcements.txt"
            else:
                # Check for explicit file paths mentioned in the prompt (including adversarial ones)
                path_match = re.search(
                    r"([A-Za-z0-9_\-\./\\]+\.[A-Za-z0-9_]+)", user_request
                )
                if path_match:
                    file_path = path_match.group(1).strip()

            return (
                "read_file",
                manifest["read_file"]["kind"],
                f"User requested file contents; selected 'read_file' resource targeting '{file_path}'.",
                {"file_path": file_path},
            )

        # Fallback if no matching capability identified
        return (
            None,
            None,
            "No discovered capability matches the user request intent.",
            {},
        )

    # -------------------------------------------------------------------------
    # RESPONSE SYNTHESIS & SUMMARIZATION
    # -------------------------------------------------------------------------

    def _summarize_output(self, cap_name: str, output: Dict[str, Any]) -> str:
        """Generate a concise output summary from the tool or resource output."""
        if output.get("status") != "success":
            code = output.get("error_code", "ERROR")
            msg = output.get("message", "Operation failed")
            return f"Operation failed [{code}]: {msg}"

        if cap_name == "read_file":
            fname = output.get("file_name", "file")
            size = output.get("size_bytes", 0)
            return f"Successfully read '{fname}' ({size} bytes)."

        if cap_name == "query_db":
            count = output.get("row_count", 0)
            return f"Database query returned {count} record(s)."

        if cap_name == "call_api":
            endpoint = output.get("endpoint", "")
            data = output.get("data", {})
            if isinstance(data, dict) and "total_events" in data:
                return f"API '{endpoint}' returned {data['total_events']} scheduled events."
            return f"API '{endpoint}' returned successful payload."

        if cap_name == "list_files":
            count = output.get("file_count", 0)
            return f"Discovered {count} accessible file(s) in safe boundary."

        return "Capability completed successfully."

    def _synthesize_final_answer(
        self, cap_name: Optional[str], output: Dict[str, Any], user_request: str
    ) -> str:
        """Formulate a grounded final answer directly from the connector output."""
        if not cap_name:
            return (
                "I could not find an appropriate capability to satisfy your request. "
                "Available capabilities are: "
                + ", ".join(self.client._manifest.keys())
                + "."
            )

        # Handle errors (including security blocks)
        if output.get("status") != "success":
            code = output.get("error_code", "ERROR")
            msg = output.get("message", "An error occurred.")
            if code == "PERMISSION_DENIED":
                return (
                    f"Access Denied: The requested operation violates security policies ({code}). "
                    f"Details: {msg}"
                )
            return f"Error ({code}): {msg}"

        # Handle successful read_file
        if cap_name == "read_file":
            content = output.get("content", "").strip()
            fname = output.get("file_name", "file")
            first_lines = "\n".join(content.splitlines()[:10])
            return (
                f"Contents of {fname}:\n\n"
                f"{first_lines}\n\n"
                f"[End of excerpt — Total size: {output.get('size_bytes', 0)} bytes]"
            )

        # Handle successful query_db
        if cap_name == "query_db":
            rows = output.get("rows", [])
            if not rows:
                return "The database query executed successfully, but returned 0 records."

            lines = ["Here are the current campus event signup counts from the database:"]
            total_signups = 0
            for row in rows:
                event_name = row.get("event", "Unknown Event")
                count = row.get("count", 0)
                total_signups += count
                lines.append(f"- {event_name}: {count} signups")
            lines.append(f"\nTotal participants across all events: {total_signups}")
            return "\n".join(lines)

        # Handle successful call_api
        if cap_name == "call_api":
            data = output.get("data", {})
            events = data.get("events", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            date_str = data.get("date", "Today") if isinstance(data, dict) else "Today"
            if not events:
                return f"No campus events are scheduled for {date_str}."

            lines = [f"Campus events scheduled for {date_str}:"]
            for ev in events:
                name = ev.get("name") or ev.get("event") or "Event"
                time_str = ev.get("time", "TBD")
                room = ev.get("room", "TBD")
                lines.append(f"- {name} at {time_str} ({room})")
            return "\n".join(lines)

        # Handle successful list_files
        if cap_name == "list_files":
            files = output.get("files", [])
            lines = [f"Accessible files in directory ({output.get('directory', 'safe_data')}):"]
            for f in files:
                lines.append(f"- {f.get('name')} ({f.get('size_bytes', 0)} bytes)")
            return "\n".join(lines)

        return "Request processed successfully."

    # -------------------------------------------------------------------------
    # MAIN AGENT EXECUTION ENTRY POINT
    # -------------------------------------------------------------------------

    def process_request(self, user_request: str) -> Dict[str, Any]:
        """Process a user request end-to-end via dynamic MCP discovery and invocation.

        Args:
            user_request: The plain English prompt from the user.

        Returns:
            Dictionary containing execution metadata, capability used, input,
            output, summary, and final answer.
        """
        # Step 1: Discover capabilities from the server
        discovered = self.client.discover()
        manifest_map = {cap["name"]: cap for cap in discovered}

        # Step 2: Select capability based on request intent
        cap_name, kind, reason, kwargs = self._select_capability(
            user_request, manifest_map
        )

        success = False
        tool_output: Dict[str, Any] = {}

        # Step 3: Execute capability if found
        if cap_name:
            tool_output = self.client.call(cap_name, **kwargs)
            success = tool_output.get("status") == "success"
        else:
            tool_output = {
                "status": "error",
                "error_code": "NO_MATCHING_CAPABILITY",
                "message": reason,
            }

        # Step 4: Summarize and synthesize final answer
        output_summary = self._summarize_output(cap_name or "none", tool_output)
        final_answer = self._synthesize_final_answer(cap_name, tool_output, user_request)

        # Step 5: Record execution trace
        trace_entry = {
            "step": len(self.traces) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_request": user_request,
            "discovered_capabilities": list(manifest_map.keys()),
            "selected_capability": cap_name,
            "selected_kind": kind,
            "selection_reason": reason,
            "tool_input": kwargs,
            "tool_output": tool_output,
            "success": success,
            "output_summary": output_summary,
            "final_answer": final_answer,
        }
        self.traces.append(trace_entry)

        return {
            "user_request": user_request,
            "capability": cap_name,
            "kind": kind,
            "input": kwargs,
            "output": tool_output,
            "output_summary": output_summary,
            "final_answer": final_answer,
            "success": success,
        }
