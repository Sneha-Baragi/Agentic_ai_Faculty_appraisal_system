"""
Campus Data Assistant – Tool-Using Agent
========================================
Lab 2 | Agentic AI (26ECAC401)

This module implements CampusDataAssistant, a rule-based tool-using agent
that answers campus-related questions by calling the appropriate tools in a
controlled, traceable manner.

Architecture
------------
  User question
      │
      ▼
  _route(question)         ← decides which handler to invoke
      │
      ▼
  _handle_*()              ← domain-specific logic
      │
      ▼
  _call(tool, reason, **args) ← centralised tool invocation
      │                         records trace entry before & after each call
      ▼
  Tool function             ← calculator / csv_reader / events_api / notifier

Design principles
-----------------
  • Tools are only called when genuinely needed.
  • Every tool call is logged with: name, reason, input, output, status.
  • The agent never fabricates data; it uses actual tool results.
  • Missing API data is handled gracefully and surfaced to the user.
  • Tool errors are reported, not silently swallowed.
"""

from __future__ import annotations

import json
import textwrap
from datetime import datetime, timezone
from typing import Any, Callable

from tools.calculator import calculator
from tools.csv_reader import read_csv
from tools.events_api import get_event_info
from tools.notifier import send_notification, LOW_TURNOUT_THRESHOLD


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class ToolDefinition:
    """Metadata + callable for a single registered tool."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict,
        func: Callable,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema  # JSON-schema-style description
        self.func = func


_TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "read_csv": ToolDefinition(
        name="read_csv",
        description=(
            "Reads the local event-signup CSV file and returns structured rows "
            "with event names, sign-up counts, and optional categories. "
            "Use this tool when the question requires sign-up numbers."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "csv_path": {
                    "type": "string",
                    "description": "Optional path override; defaults to data/event_signups.csv.",
                }
            },
            "required": [],
        },
        func=read_csv,
    ),
    "calculator": ToolDefinition(
        name="calculator",
        description=(
            "Performs arithmetic on a list of numbers. "
            "Supported operations: 'sum', 'average'. "
            "Use this tool for any numeric computation; never compute in-prompt."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["sum", "average"],
                },
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 1,
                },
            },
            "required": ["operation", "values"],
        },
        func=calculator,
    ),
    "get_event_info": ToolDefinition(
        name="get_event_info",
        description=(
            "Retrieves the date and location for a named campus event from the "
            "mock events API. Use this tool for location/date questions. "
            "Returns 'no_metadata' if the event exists but details are missing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "event_name": {
                    "type": "string",
                    "description": "Exact name of the event.",
                }
            },
            "required": ["event_name"],
        },
        func=get_event_info,
    ),
    "send_notification": ToolDefinition(
        name="send_notification",
        description=(
            "Drafts (but does NOT send) a low-turnout notification message. "
            "Call only when the computed average falls below the threshold. "
            "This tool is for Assignment 1."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "threshold": {"type": "number"},
                "actual_average": {"type": "number"},
            },
            "required": ["message"],
        },
        func=send_notification,
    ),
}


# ---------------------------------------------------------------------------
# Trace entry type
# ---------------------------------------------------------------------------

class TraceEntry:
    """One record in the execution trace."""

    def __init__(
        self,
        tool_name: str,
        reason: str,
        inputs: dict,
        output: dict,
        status: str,
        timestamp: str,
    ) -> None:
        self.tool_name = tool_name
        self.reason = reason
        self.inputs = inputs
        self.output = output
        self.status = status          # "success" | "error"
        self.timestamp = timestamp

    def to_dict(self) -> dict:
        return {
            "tool": self.tool_name,
            "reason": self.reason,
            "inputs": self.inputs,
            "output": self.output,
            "status": self.status,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class CampusDataAssistant:
    """
    Rule-based tool-using agent for campus data queries.

    The agent routes incoming questions to domain-specific handlers.
    Every tool invocation goes through _call(), which records a full
    trace entry.

    Usage
    -----
    >>> agent = CampusDataAssistant()
    >>> result = agent.answer("How many students signed up across all events in the dataset?")
    >>> print(result["final_answer"])
    """

    # Threshold for Assignment 1 (low-turnout notification).
    LOW_TURNOUT_THRESHOLD: float = LOW_TURNOUT_THRESHOLD

    def __init__(self) -> None:
        self._trace: list[TraceEntry] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def answer(self, question: str) -> dict:
        """
        Answer a campus data question using the appropriate tool(s).

        Returns a dict containing:
            question       – the original question
            reasoning      – which handler/tools were selected and why
            tool_calls     – list of trace dicts for every tool invoked
            final_answer   – the human-readable answer
            trace          – same as tool_calls (alias for the full trace)
        """
        self._trace = []  # fresh trace per question
        question = question.strip()
        response = self._route(question)
        response["question"] = question
        response["trace"] = [e.to_dict() for e in self._trace]
        return response

    def get_trace(self) -> list[dict]:
        """Return the execution trace from the most recent answer() call."""
        return [e.to_dict() for e in self._trace]

    def get_tool_registry(self) -> dict:
        """Return the tool registry metadata (without callables)."""
        return {
            name: {
                "description": td.description,
                "input_schema": td.input_schema,
            }
            for name, td in _TOOL_REGISTRY.items()
        }

    # ------------------------------------------------------------------
    # Routing logic
    # ------------------------------------------------------------------

    def _route(self, question: str) -> dict:
        """
        Decide which handler to invoke based on the question text.

        Rules are matched in priority order. If no rule matches,
        the agent responds that it cannot help without fabricating data.
        """
        q = question.lower()

        # Q1 – sign-up total and/or average
        if any(kw in q for kw in ("sign", "signup", "signed up", "average", "total", "how many")):
            # Distinguish Assignment 2 (category filter) vs. base Q1
            if "technical" in q or "category" in q:
                return self._handle_technical_average()
            return self._handle_signups_total_and_average()

        # Q2 / Q3 – event location and date
        if any(kw in q for kw in ("where", "when", "location", "date")):
            event_name = self._extract_event_name(question)
            return self._handle_event_info(event_name)

        # No-tool path – general greeting / help text
        if any(kw in q for kw in ("hello", "hi", "help", "what can you")):
            return self._handle_no_tool(question)

        # Fallback
        return {
            "reasoning": (
                "No matching tool or handler found for this question. "
                "The agent cannot fabricate an answer."
            ),
            "tool_calls": [],
            "final_answer": (
                "I'm not sure how to answer that question with the available tools. "
                "I can help with event sign-up statistics, event dates/locations, "
                "and campus event information."
            ),
        }

    # ------------------------------------------------------------------
    # Handler: Question 1 – total and average sign-ups
    # ------------------------------------------------------------------

    def _handle_signups_total_and_average(self) -> dict:
        reasoning = (
            "The question asks about sign-up numbers, which live in the event "
            "sign-up CSV file. I will: (1) read the CSV, (2) extract numeric "
            "sign-up values, (3) call calculator(sum), (4) call calculator(average). "
            "I will NOT use the events API for this question."
        )

        # Step 1 – read CSV
        csv_result = self._call(
            tool_name="read_csv",
            reason="Sign-up counts live in the CSV export, not the events API.",
            csv_path=None,
        )

        if "error" in csv_result:
            return {
                "reasoning": reasoning,
                "tool_calls": [e.to_dict() for e in self._trace],
                "final_answer": (
                    f"Could not retrieve sign-up data: {csv_result['error']}"
                ),
            }

        # Step 2 – extract numeric sign-up values
        rows = csv_result["rows"]
        signup_values: list[int] = [row["Signups"] for row in rows]
        event_count = csv_result["row_count"]

        # Step 3 – sum
        sum_result = self._call(
            tool_name="calculator",
            reason=(
                "I have the list of sign-up counts from the CSV. "
                "The calculator tool will compute the total sum reliably."
            ),
            operation="sum",
            values=signup_values,
        )

        if "error" in sum_result:
            return {
                "reasoning": reasoning,
                "tool_calls": [e.to_dict() for e in self._trace],
                "final_answer": (
                    f"Calculator error (sum): {sum_result['error']}"
                ),
            }

        # Step 4 – average
        avg_result = self._call(
            tool_name="calculator",
            reason=(
                "Now I need the average. I pass the same sign-up values "
                "(not the raw CSV rows) to the calculator."
            ),
            operation="average",
            values=signup_values,
        )

        if "error" in avg_result:
            return {
                "reasoning": reasoning,
                "tool_calls": [e.to_dict() for e in self._trace],
                "final_answer": (
                    f"Calculator error (average): {avg_result['error']}"
                ),
            }

        total = sum_result["result"]
        average = avg_result["result"]

        # Step 5 (Assignment 1) – notify if average is below threshold
        if average < self.LOW_TURNOUT_THRESHOLD:
            self._call(
                tool_name="send_notification",
                reason=(
                    f"The computed average ({average}) is below the "
                    f"low-turnout threshold ({self.LOW_TURNOUT_THRESHOLD}). "
                    "Drafting a notice for the event coordinator."
                ),
                message=(
                    f"Campus Event Alert: The average sign-up count across all "
                    f"events in the dataset is {average}, which is below the minimum "
                    f"threshold of {self.LOW_TURNOUT_THRESHOLD}. "
                    f"Please consider promoting upcoming events."
                ),
                threshold=self.LOW_TURNOUT_THRESHOLD,
                actual_average=average,
            )

        # Build final answer from tool results only
        final_answer = (
            f"Based on the event sign-up data:\n"
            f"  • Total sign-ups across all events : {total}\n"
            f"  • Number of events                 : {event_count}\n"
            f"  • Average sign-ups per event       : {average}"
        )

        return {
            "reasoning": reasoning,
            "tool_calls": [e.to_dict() for e in self._trace],
            "final_answer": final_answer,
            # Expose raw values for test assertions
            "_total": total,
            "_average": average,
            "_event_count": event_count,
        }

    # ------------------------------------------------------------------
    # Handler: Assignment 2 – average for technical events only
    # ------------------------------------------------------------------

    def _handle_technical_average(self) -> dict:
        reasoning = (
            "The question asks for the average sign-up count for 'technical' "
            "category events. I will: (1) read the CSV, (2) filter rows where "
            "Category == 'technical', (3) validate the filtered list is non-empty, "
            "(4) call calculator(average) on the filtered values."
        )

        # Step 1 – read CSV
        csv_result = self._call(
            tool_name="read_csv",
            reason=(
                "I need sign-up data with category tags. "
                "The CSV contains a Category column."
            ),
            csv_path=None,
        )

        if "error" in csv_result:
            return {
                "reasoning": reasoning,
                "tool_calls": [e.to_dict() for e in self._trace],
                "final_answer": (
                    f"Could not retrieve sign-up data: {csv_result['error']}"
                ),
            }

        # Step 2 – filter to technical events
        rows = csv_result["rows"]
        if not rows or "Category" not in rows[0]:
            return {
                "reasoning": reasoning,
                "tool_calls": [e.to_dict() for e in self._trace],
                "final_answer": (
                    "The CSV does not contain a 'Category' column. "
                    "Cannot filter by event category."
                ),
            }

        tech_rows = [r for r in rows if r.get("Category", "").lower() == "technical"]

        # Step 3 – validate non-empty
        if not tech_rows:
            return {
                "reasoning": reasoning,
                "tool_calls": [e.to_dict() for e in self._trace],
                "final_answer": (
                    "No events with category 'technical' were found in the CSV."
                ),
            }

        tech_values = [r["Signups"] for r in tech_rows]
        tech_names = [r["Event"] for r in tech_rows]

        # Step 4 – average via calculator
        avg_result = self._call(
            tool_name="calculator",
            reason=(
                f"I have {len(tech_values)} technical event sign-up counts: "
                f"{tech_values}. Using the calculator for the average."
            ),
            operation="average",
            values=tech_values,
        )

        if "error" in avg_result:
            return {
                "reasoning": reasoning,
                "tool_calls": [e.to_dict() for e in self._trace],
                "final_answer": f"Calculator error: {avg_result['error']}",
            }

        average = avg_result["result"]
        final_answer = (
            f"Technical events: {tech_names}\n"
            f"Sign-ups: {tech_values}\n"
            f"Average sign-ups for technical events: {average}"
        )

        return {
            "reasoning": reasoning,
            "tool_calls": [e.to_dict() for e in self._trace],
            "final_answer": final_answer,
            "_technical_average": average,
            "_technical_events": tech_names,
        }

    # ------------------------------------------------------------------
    # Handler: Questions 2 & 3 – event date and location
    # ------------------------------------------------------------------

    def _handle_event_info(self, event_name: str) -> dict:
        reasoning = (
            f"The question asks about date and location of '{event_name}'. "
            "Date and location metadata belong to the events API, not the CSV. "
            "I will call get_event_info() and use the returned data verbatim."
        )

        api_result = self._call(
            tool_name="get_event_info",
            reason=(
                f"Date and location for '{event_name}' are stored in the "
                "events API, not the sign-up CSV."
            ),
            event_name=event_name,
        )

        status = api_result.get("status")

        if status == "ok":
            final_answer = (
                f"{event_name} is at {api_result['location']} "
                f"on {api_result['date']}."
            )
        elif status == "no_metadata":
            final_answer = (
                f"I don't have location/date metadata for {event_name} "
                f"in the events API."
            )
        else:
            # not_found or unexpected error
            error_msg = api_result.get(
                "error",
                api_result.get("message", "Unknown API error.")
            )
            final_answer = (
                f"The events API does not have a record for '{event_name}'. "
                f"Details: {error_msg}"
            )

        return {
            "reasoning": reasoning,
            "tool_calls": [e.to_dict() for e in self._trace],
            "final_answer": final_answer,
        }

    # ------------------------------------------------------------------
    # Handler: No-tool questions (greetings, help)
    # ------------------------------------------------------------------

    def _handle_no_tool(self, question: str) -> dict:
        return {
            "reasoning": (
                "This is a conversational greeting / help request. "
                "No tool is needed."
            ),
            "tool_calls": [],
            "final_answer": (
                "Hello! I'm the Campus Data Assistant. I can help you with:\n"
                "  • Event sign-up totals and averages (reads CSV + calculator)\n"
                "  • Event dates and locations (queries mock events API)\n"
                "  • Category-filtered statistics (reads CSV, filters, calculator)\n\n"
                "Ask me something like:\n"
                "  'How many students signed up across all events?'\n"
                "  'Where and when is the Hackathon Kickoff?'"
            ),
        }

    # ------------------------------------------------------------------
    # Centralised tool invocation (Section 7 contract)
    # ------------------------------------------------------------------

    def _call(self, tool_name: str, reason: str, **kwargs: Any) -> dict:
        """
        Invoke a registered tool and record the full execution trace entry.

        Steps performed:
          1. Validate the tool name against the registry.
          2. Record the reason for calling it.
          3. Record the exact structured input.
          4. Execute the tool function.
          5. Capture the structured output.
          6. Detect errors (key "error" in output counts as a tool error).
          7. Append a complete TraceEntry to self._trace.

        Args:
            tool_name: Key in _TOOL_REGISTRY.
            reason:    Human-readable justification for this tool call.
            **kwargs:  Keyword arguments forwarded to the tool function.

        Returns:
            The tool's output dict (may contain "error").
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Step 1 – validate tool name
        if tool_name not in _TOOL_REGISTRY:
            output = {
                "error": (
                    f"Tool '{tool_name}' is not in the registry. "
                    f"Available tools: {list(_TOOL_REGISTRY.keys())}."
                )
            }
            entry = TraceEntry(
                tool_name=tool_name,
                reason=reason,
                inputs=dict(kwargs),
                output=output,
                status="error",
                timestamp=timestamp,
            )
            self._trace.append(entry)
            return output

        tool_def = _TOOL_REGISTRY[tool_name]

        # Steps 2–3: reason and input are captured in the TraceEntry below.
        structured_input = dict(kwargs)

        # Step 4 – execute
        try:
            output: dict = tool_def.func(**kwargs)
        except Exception as exc:
            output = {
                "error": (
                    f"Tool '{tool_name}' raised an unexpected exception: "
                    f"{type(exc).__name__}: {exc}"
                )
            }

        # Step 5–6 – capture output and determine status
        status = "error" if "error" in output else "success"

        # Step 7 – record trace
        entry = TraceEntry(
            tool_name=tool_name,
            reason=reason,
            inputs=structured_input,
            output=output,
            status=status,
            timestamp=timestamp,
        )
        self._trace.append(entry)
        return output

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_event_name(self, question: str) -> str:
        """
        Extract an event name from a free-text question.

        Uses a priority-ordered substring match against known event names.
        Returns "Unknown Event" if no match is found so that the API can
        return a 'not_found' response rather than the agent fabricating data.
        """
        known_events = [
            "Hackathon Kickoff",
            "AI Club Talk",
            "Capstone Expo",
            "Robotics Demo",
            "GenAI Workshop",
            "Career Panel",
        ]
        q_lower = question.lower()
        for event in known_events:
            if event.lower() in q_lower:
                return event
        # Return the question itself trimmed as a best-effort fallback;
        # the API will return 'not_found', which is correct behaviour.
        return question.strip()

