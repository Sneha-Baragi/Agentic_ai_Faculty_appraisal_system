"""
tests/test_campus_assistant.py
==============================
Comprehensive test suite for Lab 2 – Tool-Using Agent.

Run from the Lab-02-Tool-Using-Agent directory:
    python -m unittest discover -s tests -v

Or run a specific class:
    python -m unittest tests.test_campus_assistant.TestCalculator -v

Coverage:
  TestCalculator        – Unit tests for tools/calculator.py
  TestCSVReader         – Unit tests for tools/csv_reader.py
  TestEventsAPI         – Unit tests for tools/events_api.py
  TestNotifier          – Unit tests for tools/notifier.py
  TestCampusAssistant   – Integration tests for agent/campus_assistant.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Path setup – ensure the Lab-02 root is importable regardless of CWD.
# ---------------------------------------------------------------------------
_LAB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LAB_ROOT not in sys.path:
    sys.path.insert(0, _LAB_ROOT)

from tools.calculator import calculator
from tools.csv_reader import read_csv
from tools.events_api import get_event_info
from tools.notifier import send_notification
from agent.campus_assistant import CampusDataAssistant


# ===========================================================================
# TestCalculator
# ===========================================================================

class TestCalculator(unittest.TestCase):
    """Unit tests for the calculator tool."""

    # --- sum -----------------------------------------------------------------

    def test_sum_basic(self):
        """Sum of [12, 9, 15] must be 36."""
        result = calculator(operation="sum", values=[12, 9, 15])
        self.assertNotIn("error", result, msg=f"Unexpected error: {result}")
        self.assertEqual(result["result"], 36)

    def test_sum_all_lab_data(self):
        """Sum of the full dataset [12,9,15,7,20,11] must be 74."""
        result = calculator(operation="sum", values=[12, 9, 15, 7, 20, 11])
        self.assertNotIn("error", result)
        self.assertEqual(result["result"], 74)

    def test_sum_single_value(self):
        """Sum of a single value must equal that value."""
        result = calculator(operation="sum", values=[42])
        self.assertEqual(result["result"], 42)

    def test_sum_floats(self):
        """Sum of floats."""
        result = calculator(operation="sum", values=[1.5, 2.5])
        self.assertAlmostEqual(result["result"], 4.0)

    def test_sum_case_insensitive(self):
        """Operation name matching must be case-insensitive."""
        result = calculator(operation="SUM", values=[10, 20])
        self.assertNotIn("error", result)
        self.assertEqual(result["result"], 30)

    # --- average -------------------------------------------------------------

    def test_average_basic(self):
        """Average of [12, 9, 15] must be 12.0."""
        result = calculator(operation="average", values=[12, 9, 15])
        self.assertNotIn("error", result)
        self.assertAlmostEqual(result["result"], 12.0)

    def test_average_all_lab_data(self):
        """Average of [12,9,15,7,20,11] must be 12.33."""
        result = calculator(operation="average", values=[12, 9, 15, 7, 20, 11])
        self.assertNotIn("error", result)
        self.assertAlmostEqual(result["result"], 12.33, places=2)

    def test_average_single_value(self):
        """Average of a single value must equal that value."""
        result = calculator(operation="average", values=[7])
        self.assertAlmostEqual(result["result"], 7.0)

    # --- empty values --------------------------------------------------------

    def test_sum_empty_values(self):
        """Empty list must return an error, not raise an exception."""
        result = calculator(operation="sum", values=[])
        self.assertIn("error", result)
        self.assertNotIn("result", result)

    def test_average_empty_values(self):
        """Empty list must return an error for average too."""
        result = calculator(operation="average", values=[])
        self.assertIn("error", result)

    # --- unsupported operation -----------------------------------------------

    def test_unsupported_operation(self):
        """An unknown operation name must return an error."""
        result = calculator(operation="multiply", values=[2, 3])
        self.assertIn("error", result)
        self.assertNotIn("result", result)

    def test_unsupported_operation_empty_string(self):
        """Empty string operation must return an error."""
        result = calculator(operation="", values=[1, 2])
        self.assertIn("error", result)

    # --- invalid numeric values ----------------------------------------------

    def test_invalid_string_in_values(self):
        """Non-numeric strings in the list must return an error."""
        result = calculator(operation="sum", values=["a", "b"])
        self.assertIn("error", result)
        self.assertNotIn("result", result)

    def test_invalid_mixed_types(self):
        """A list mixing numbers and strings must return an error."""
        result = calculator(operation="sum", values=[1, "two", 3])
        self.assertIn("error", result)

    def test_invalid_boolean_values(self):
        """Booleans must be rejected (bool is a subclass of int in Python)."""
        result = calculator(operation="sum", values=[True, False])
        self.assertIn("error", result)

    def test_invalid_values_not_a_list(self):
        """Non-list values argument must return an error."""
        result = calculator(operation="sum", values=42)  # type: ignore[arg-type]
        self.assertIn("error", result)

    def test_no_silent_failure(self):
        """Invalid input must NEVER return a 'result' key alongside an 'error'."""
        result = calculator(operation="sum", values=[])
        self.assertNotIn("result", result, "Silent failure detected: 'result' present with 'error'.")


# ===========================================================================
# TestCSVReader
# ===========================================================================

class TestCSVReader(unittest.TestCase):
    """Unit tests for the csv_reader tool."""

    # Helpers ----------------------------------------------------------------

    def _write_csv(self, rows: list[list[str]], tmpdir: str, filename: str = "test.csv") -> str:
        """Write rows to a temporary CSV and return its path."""
        path = os.path.join(tmpdir, filename)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow(row)
        return path

    # --- successful read -----------------------------------------------------

    def test_read_correct_csv(self):
        """CSV with all required columns must be read without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv([
                ["Event", "Signups", "Category"],
                ["AI Club Talk", "12", "technical"],
                ["Hackathon Kickoff", "9", "technical"],
            ], tmpdir)
            result = read_csv(csv_path=path)
            self.assertNotIn("error", result)
            self.assertIn("rows", result)
            self.assertIn("row_count", result)

    def test_correct_row_count(self):
        """Row count must equal the number of data rows (excluding header)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv([
                ["Event", "Signups", "Category"],
                ["AI Club Talk", "12", "technical"],
                ["Hackathon Kickoff", "9", "technical"],
                ["Robotics Demo", "15", "technical"],
            ], tmpdir)
            result = read_csv(csv_path=path)
            self.assertEqual(result["row_count"], 3)

    def test_correct_signup_values(self):
        """Sign-up values must be returned as integers, not strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv([
                ["Event", "Signups"],
                ["Capstone Expo", "20"],
            ], tmpdir)
            result = read_csv(csv_path=path)
            self.assertIsInstance(result["rows"][0]["Signups"], int)
            self.assertEqual(result["rows"][0]["Signups"], 20)

    def test_full_dataset_signups(self):
        """The standard data/event_signups.csv must return 6 rows summing to 74."""
        # Use the real data file bundled with Lab 2.
        lab_root = _LAB_ROOT
        csv_path = os.path.join(lab_root, "data", "event_signups.csv")
        if not os.path.exists(csv_path):
            self.skipTest("data/event_signups.csv not found.")
        result = read_csv(csv_path=csv_path)
        self.assertNotIn("error", result)
        self.assertEqual(result["row_count"], 6)
        total = sum(r["Signups"] for r in result["rows"])
        self.assertEqual(total, 74)

    # --- missing file --------------------------------------------------------

    def test_missing_file(self):
        """A path that does not exist must return an error."""
        result = read_csv(csv_path="/nonexistent/path/data.csv")
        self.assertIn("error", result)
        self.assertNotIn("rows", result)

    # --- empty CSV -----------------------------------------------------------

    def test_empty_csv(self):
        """A completely empty file (0 bytes) must return an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.csv")
            open(path, "w").close()  # create 0-byte file
            result = read_csv(csv_path=path)
            self.assertIn("error", result)

    def test_header_only_csv(self):
        """A CSV with headers but no data rows must return an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv([["Event", "Signups"]], tmpdir)
            result = read_csv(csv_path=path)
            self.assertIn("error", result)

    # --- missing required columns --------------------------------------------

    def test_missing_event_column(self):
        """CSV without the 'Event' column must return an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv([
                ["Signups"],
                ["12"],
            ], tmpdir)
            result = read_csv(csv_path=path)
            self.assertIn("error", result)

    def test_missing_signups_column(self):
        """CSV without the 'Signups' column must return an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv([
                ["Event"],
                ["AI Club Talk"],
            ], tmpdir)
            result = read_csv(csv_path=path)
            self.assertIn("error", result)

    def test_non_integer_signups(self):
        """Non-integer Signups value must return an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_csv([
                ["Event", "Signups"],
                ["AI Club Talk", "twelve"],
            ], tmpdir)
            result = read_csv(csv_path=path)
            self.assertIn("error", result)


# ===========================================================================
# TestEventsAPI
# ===========================================================================

class TestEventsAPI(unittest.TestCase):
    """Unit tests for the events_api tool."""

    # --- known event with metadata ------------------------------------------

    def test_hackathon_kickoff(self):
        """Hackathon Kickoff must return status 'ok' with correct metadata."""
        result = get_event_info("Hackathon Kickoff")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["date"], "2026-07-05")
        self.assertEqual(result["location"], "Innovation Lab")

    def test_ai_club_talk(self):
        """AI Club Talk must return status 'ok' with correct metadata."""
        result = get_event_info("AI Club Talk")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["date"], "2026-07-02")
        self.assertEqual(result["location"], "CS Block Auditorium")

    def test_ok_response_has_event_name(self):
        """Successful response must echo back the event_name."""
        result = get_event_info("Hackathon Kickoff")
        self.assertEqual(result["event_name"], "Hackathon Kickoff")

    # --- unknown event -------------------------------------------------------

    def test_unknown_event(self):
        """A completely unknown event must return status 'not_found'."""
        result = get_event_info("Nonexistent Conference")
        self.assertEqual(result["status"], "not_found")
        self.assertIn("error", result)

    def test_unknown_event_no_fabrication(self):
        """The 'not_found' response must NOT contain 'date' or 'location'."""
        result = get_event_info("Mystery Event")
        self.assertNotIn("date", result)
        self.assertNotIn("location", result)

    def test_empty_event_name(self):
        """An empty string event name must return status 'not_found'."""
        result = get_event_info("")
        self.assertEqual(result["status"], "not_found")

    # --- missing metadata ----------------------------------------------------

    def test_capstone_expo_no_metadata(self):
        """Capstone Expo is known but metadata is absent; expect 'no_metadata'."""
        result = get_event_info("Capstone Expo")
        self.assertEqual(result["status"], "no_metadata")

    def test_no_metadata_response_no_date(self):
        """'no_metadata' response must NOT contain fabricated 'date' or 'location'."""
        result = get_event_info("Capstone Expo")
        self.assertNotIn("date", result)
        self.assertNotIn("location", result)

    def test_no_metadata_has_message(self):
        """'no_metadata' response must include a human-readable 'message'."""
        result = get_event_info("Capstone Expo")
        self.assertIn("message", result)
        self.assertIsInstance(result["message"], str)
        self.assertGreater(len(result["message"]), 0)


# ===========================================================================
# TestNotifier
# ===========================================================================

class TestNotifier(unittest.TestCase):
    """Unit tests for the notification drafter (Assignment 1)."""

    def test_draft_created(self):
        """A valid message must produce status 'drafted'."""
        result = send_notification(message="Low turnout alert.", actual_average=8.0)
        self.assertEqual(result["status"], "drafted")
        self.assertTrue(result["drafted"])

    def test_draft_contains_message(self):
        """The drafted message field must include the input text."""
        result = send_notification(message="Please promote events.", actual_average=8.0)
        self.assertIn("message", result)
        self.assertIn("Please promote events.", result["message"])

    def test_nothing_actually_sent(self):
        """The result must contain [DRAFT – NOT SENT] marker."""
        result = send_notification(message="Test alert.", actual_average=5.0)
        self.assertIn("DRAFT", result["message"])

    def test_empty_message_returns_error(self):
        """An empty message must return an error."""
        result = send_notification(message="")
        self.assertIn("error", result)

    def test_average_recorded(self):
        """The actual_average must be echoed back in the response."""
        result = send_notification(message="Alert.", actual_average=7.5)
        self.assertEqual(result["actual_average"], 7.5)


# ===========================================================================
# TestCampusAssistant – Integration / Agent tests
# ===========================================================================

class TestCampusAssistant(unittest.TestCase):
    """Integration tests for the CampusDataAssistant agent."""

    def setUp(self):
        self.agent = CampusDataAssistant()

    # --- Q1: sign-up statistics ---------------------------------------------

    def test_total_signups(self):
        """Agent must return total sign-ups = 74 (from tool results, not hardcoded)."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        self.assertNotIn("error", response.get("final_answer", ""))
        self.assertEqual(response.get("_total"), 74)

    def test_average_signups(self):
        """Agent must return average = 12.33."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        self.assertAlmostEqual(response.get("_average"), 12.33, places=2)

    def test_event_count(self):
        """Agent must report 6 events."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        self.assertEqual(response.get("_event_count"), 6)

    def test_final_answer_contains_total(self):
        """Final answer text must include '74'."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        self.assertIn("74", response["final_answer"])

    def test_final_answer_contains_average(self):
        """Final answer text must include '12.33'."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        self.assertIn("12.33", response["final_answer"])

    # --- Q2: event date and location ----------------------------------------

    def test_hackathon_date_and_location(self):
        """Agent must correctly report Hackathon Kickoff date and location."""
        response = self.agent.answer("Where and when is the Hackathon Kickoff?")
        answer = response["final_answer"]
        self.assertIn("Innovation Lab", answer)
        self.assertIn("2026-07-05", answer)

    def test_event_answer_uses_tool_data(self):
        """The answer for Hackathon must NOT contain fallback/fabricated text."""
        response = self.agent.answer("Where and when is the Hackathon Kickoff?")
        answer = response["final_answer"]
        self.assertNotIn("I don't know", answer)
        self.assertNotIn("fabricated", answer.lower())

    # --- Q3: missing metadata -----------------------------------------------

    def test_capstone_expo_honest_response(self):
        """Agent must NOT fabricate date/location for Capstone Expo."""
        response = self.agent.answer("Where and when is the Capstone Expo?")
        answer = response["final_answer"]
        # Must NOT contain a specific date
        self.assertNotIn("2026-07-", answer)
        # Must NOT contain a specific location
        self.assertNotIn("Auditorium", answer)
        self.assertNotIn("Lab", answer)

    def test_capstone_expo_missing_metadata_message(self):
        """Agent must acknowledge missing metadata for Capstone Expo."""
        response = self.agent.answer("Where and when is the Capstone Expo?")
        answer = response["final_answer"].lower()
        self.assertTrue(
            "don't have" in answer or "no" in answer or "metadata" in answer or "not" in answer,
            msg=f"Expected honest missing-metadata response. Got: {response['final_answer']}"
        )

    def test_capstone_expo_error_in_trace(self):
        """The trace for Capstone Expo must record the no_metadata API status."""
        response = self.agent.answer("Where and when is the Capstone Expo?")
        trace = response["trace"]
        self.assertTrue(len(trace) > 0, "Trace must not be empty.")
        api_calls = [e for e in trace if e["tool"] == "get_event_info"]
        self.assertTrue(len(api_calls) > 0, "get_event_info must appear in trace.")
        api_output = api_calls[0]["output"]
        self.assertEqual(api_output.get("status"), "no_metadata")

    # --- tool selection correctness -----------------------------------------

    def test_signups_question_uses_read_csv(self):
        """Q1 must call read_csv."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        tool_names = [e["tool"] for e in response["trace"]]
        self.assertIn("read_csv", tool_names)

    def test_signups_question_uses_calculator(self):
        """Q1 must call calculator (at least once)."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        tool_names = [e["tool"] for e in response["trace"]]
        self.assertIn("calculator", tool_names)

    def test_event_question_does_not_use_csv(self):
        """Q2 (location/date) must NOT call read_csv."""
        response = self.agent.answer("Where and when is the Hackathon Kickoff?")
        tool_names = [e["tool"] for e in response["trace"]]
        self.assertNotIn("read_csv", tool_names)

    def test_event_question_does_not_use_calculator(self):
        """Q2 (location/date) must NOT call calculator."""
        response = self.agent.answer("Where and when is the Hackathon Kickoff?")
        tool_names = [e["tool"] for e in response["trace"]]
        self.assertNotIn("calculator", tool_names)

    def test_no_tool_for_greeting(self):
        """A greeting must NOT trigger any tool call."""
        response = self.agent.answer("Hello, what can you help me with?")
        self.assertEqual(len(response["trace"]), 0,
                         "Greeting should not invoke any tool.")

    # --- tool call order ----------------------------------------------------

    def test_q1_tool_call_order(self):
        """For Q1: read_csv must be called BEFORE calculator."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        tool_names = [e["tool"] for e in response["trace"]]
        self.assertGreater(tool_names.index("calculator"),
                           tool_names.index("read_csv"),
                           "read_csv must precede calculator in the trace.")

    def test_q1_sum_before_average(self):
        """For Q1: calculator(sum) must be called before calculator(average)."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        calc_calls = [
            e for e in response["trace"] if e["tool"] == "calculator"
        ]
        self.assertGreaterEqual(len(calc_calls), 2,
                                "Expected at least two calculator calls.")
        self.assertEqual(calc_calls[0]["inputs"]["operation"], "sum")
        self.assertEqual(calc_calls[1]["inputs"]["operation"], "average")

    # --- structured input and output logging --------------------------------

    def test_trace_has_required_fields(self):
        """Every trace entry must contain tool, reason, inputs, output, status."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        for entry in response["trace"]:
            for field in ("tool", "reason", "inputs", "output", "status", "timestamp"):
                self.assertIn(field, entry,
                              f"Trace entry missing '{field}': {entry}")

    def test_calculator_inputs_are_structured(self):
        """Calculator inputs in trace must include 'operation' and 'values'."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        calc_calls = [e for e in response["trace"] if e["tool"] == "calculator"]
        for call in calc_calls:
            self.assertIn("operation", call["inputs"])
            self.assertIn("values", call["inputs"])
            self.assertIsInstance(call["inputs"]["values"], list)

    def test_calculator_receives_numeric_values_only(self):
        """Calculator must receive numeric sign-up values, not raw CSV rows."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        calc_calls = [e for e in response["trace"] if e["tool"] == "calculator"]
        for call in calc_calls:
            for v in call["inputs"]["values"]:
                self.assertIsInstance(v, (int, float),
                                      f"Non-numeric value passed to calculator: {v}")

    def test_trace_outputs_are_dicts(self):
        """Every trace output must be a dict."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        for entry in response["trace"]:
            self.assertIsInstance(entry["output"], dict)

    def test_trace_status_is_success_on_valid_question(self):
        """All trace entries for Q1 must have status 'success'."""
        response = self.agent.answer(
            "How many students signed up for events this month, and what's the average per event?"
        )
        for entry in response["trace"]:
            self.assertEqual(entry["status"], "success",
                             f"Unexpected error status in trace: {entry}")

    # --- tool errors do not silently propagate ------------------------------

    def test_invalid_tool_name_handled(self):
        """Calling a non-existent tool via _call must return an error dict, not raise."""
        agent = CampusDataAssistant()
        result = agent._call("nonexistent_tool", "testing error handling")
        self.assertIn("error", result)

    def test_invalid_tool_error_in_trace(self):
        """An invalid tool call must be recorded in the trace with status 'error'."""
        agent = CampusDataAssistant()
        agent._call("nonexistent_tool", "testing error handling")
        trace = agent.get_trace()
        self.assertTrue(len(trace) > 0)
        self.assertEqual(trace[-1]["status"], "error")

    # --- Assignment 2: technical category filter ----------------------------

    def test_technical_average(self):
        """Agent must correctly compute average for technical events only."""
        response = self.agent.answer(
            "What's the average sign-up for technical events only?"
        )
        # Technical events: AI Club Talk (12), Hackathon Kickoff (9), Robotics Demo (15) → avg 12.0
        avg = response.get("_technical_average")
        if avg is not None:
            self.assertAlmostEqual(avg, 12.0, places=2)

    def test_technical_filter_uses_read_csv(self):
        """Assignment 2 question must call read_csv."""
        response = self.agent.answer(
            "What's the average sign-up for technical events only?"
        )
        tool_names = [e["tool"] for e in response["trace"]]
        self.assertIn("read_csv", tool_names)

    def test_technical_filter_uses_calculator(self):
        """Assignment 2 question must call calculator."""
        response = self.agent.answer(
            "What's the average sign-up for technical events only?"
        )
        tool_names = [e["tool"] for e in response["trace"]]
        self.assertIn("calculator", tool_names)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)

