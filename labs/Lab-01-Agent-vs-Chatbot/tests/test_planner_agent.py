"""Unit Tests for Study Planner Agent (Lab 1).

Validates autonomous agent capabilities:
- Asks only for missing information.
- Does not repeatedly request information already provided.
- Executes Goal-Plan-Act-Observe-Revise loop.
- Calls the schedule tool and respects external calendar busy days.
- Excludes student unavailable days.
- Mutates existing plan object in-place upon receiving feedback.
- Preserves non-targeted plan entries during revision.
- Explicitly handles external tool failures.
- Detects impossible or conflicting constraints.
- Records structured iteration logs throughout the loop.
- Supports Assignment 1 (Two Rounds of Feedback) and Assignment 2 (Conflict Detection).
"""

import os
import sys
import unittest

# Ensure the Lab 1 root is in python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LAB_ROOT = os.path.dirname(CURRENT_DIR)
if LAB_ROOT not in sys.path:
    sys.path.insert(0, LAB_ROOT)

from agent.planner_agent import StudyPlannerAgent
from agent.schedule_tool import ScheduleTool, ScheduleToolError


class TestStudyPlannerAgent(unittest.TestCase):
    """Test suite verifying autonomous study planning agent behavior."""

    def setUp(self) -> None:
        self.tool = ScheduleTool()
        self.agent = StudyPlannerAgent(schedule_tool=self.tool)

    def test_agent_asks_only_for_missing_information(self) -> None:
        """Verify the agent identifies and asks ONLY for missing fields."""
        # Initial input contains subjects and hours, but lacks unavailable_days
        self.agent.ingest_initial_request(
            subjects=["Data Structures", "Operating Systems", "AI Agents"],
            hours_per_day=2,
            unavailable_days=None,
        )

        missing = self.agent.inspect_missing_information()
        self.assertEqual(missing, ["unavailable_days"])

        is_complete, questions = self.agent.step_clarification()
        self.assertFalse(is_complete)
        self.assertEqual(len(questions), 1)
        self.assertIn("unavailable for study sessions", questions[0])

    def test_agent_does_not_reask_known_information(self) -> None:
        """Verify the agent does not repeatedly request parameters already supplied."""
        self.agent.ingest_initial_request(
            subjects=["Data Structures"],
            hours_per_day=2,
            unavailable_days=None,
        )
        # Supply the missing unavailable_days
        self.agent.supply_clarification(unavailable_days=["Sunday"])

        missing = self.agent.inspect_missing_information()
        self.assertEqual(missing, [])

        is_complete, questions = self.agent.step_clarification()
        self.assertTrue(is_complete)
        self.assertEqual(questions, [])

    def test_agent_completes_goal_and_stopping_condition(self) -> None:
        """Verify the agent declares and reaches its stopping condition."""
        self.assertFalse(self.agent.is_stopping_condition_met())

        result = self.agent.run_autonomous_loop(
            initial_request={
                "subjects": ["Data Structures", "Operating Systems", "AI Agents"],
                "hours_per_day": 2,
            },
            clarification_data={"unavailable_days": ["Sunday"]},
            feedback=None,
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(self.agent.state.goal_completed)
        self.assertTrue(self.agent.state.schedule_generated)
        self.assertTrue(self.agent.is_stopping_condition_met())
        self.assertIsNotNone(self.agent.state.stopping_reason)

    def test_agent_calls_schedule_tool(self) -> None:
        """Verify external schedule tool is actively called and observed with >= 2 busy days."""
        self.assertEqual(self.tool.invocation_count, 0)

        self.agent.ingest_initial_request(
            subjects=["Data Structures", "Operating Systems", "AI Agents"],
            hours_per_day=2,
            unavailable_days=["Sunday"],
        )
        tool_data = self.agent.fetch_existing_schedule(student_id="student_01")

        self.assertEqual(self.tool.invocation_count, 1)
        self.assertGreaterEqual(
            len(tool_data["busy_days"]),
            2,
            "read_existing_schedule() must return at least two busy days per Lab Guide.",
        )
        self.assertIn("Wednesday", tool_data["busy_days"])
        self.assertIn("Friday", tool_data["busy_days"])
        self.assertEqual(self.agent.state.existing_schedule, tool_data)

    def test_existing_busy_day_conflict_avoided(self) -> None:
        """Verify Wednesday and Friday (busy days from tool) are excluded from study sessions."""
        self.agent.run_autonomous_loop(
            initial_request={
                "subjects": ["Data Structures", "Operating Systems", "AI Agents"],
                "hours_per_day": 2,
            },
            clarification_data={"unavailable_days": ["Sunday"]},
        )

        plan = self.agent.state.study_plan
        self.assertIsNotNone(plan)

        # Wednesday must be flagged as busy conflict, with 0 study hours
        wed = plan["Wednesday"]
        self.assertEqual(wed.status, "BUSY_CONFLICT")
        self.assertIsNone(wed.subject)
        self.assertEqual(wed.hours, 0.0)
        self.assertIn("Department Seminar", wed.notes)

        # Friday must be flagged as busy conflict, with 0 study hours
        fri = plan["Friday"]
        self.assertEqual(fri.status, "BUSY_CONFLICT")
        self.assertIsNone(fri.subject)
        self.assertEqual(fri.hours, 0.0)
        self.assertIn("Campus Project Mentorship", fri.notes)

    def test_unavailable_days_excluded(self) -> None:
        """Verify student-designated rest days (Sunday) are excluded from study."""
        self.agent.run_autonomous_loop(
            initial_request={
                "subjects": ["Data Structures", "Operating Systems", "AI Agents"],
                "hours_per_day": 2,
            },
            clarification_data={"unavailable_days": ["Sunday"]},
        )

        plan = self.agent.state.study_plan
        sun = plan["Sunday"]
        self.assertEqual(sun.status, "UNAVAILABLE")
        self.assertIsNone(sun.subject)
        self.assertEqual(sun.hours, 0.0)

    def test_feedback_mutates_existing_plan_in_place(self) -> None:
        """CRITICAL: Test that user feedback mutates the existing schedule object."""
        self.agent.run_autonomous_loop(
            initial_request={
                "subjects": ["Data Structures", "Operating Systems", "AI Agents"],
                "hours_per_day": 2,
            },
            clarification_data={"unavailable_days": ["Sunday"]},
        )

        initial_plan = self.agent.state.study_plan
        initial_tuesday_time = initial_plan["Tuesday"].time_of_day
        self.assertEqual(initial_tuesday_time, "Morning (09:00 - 11:00)")

        # Save copy of other days to verify preservation
        initial_monday = initial_plan["Monday"].to_dict()
        initial_thursday = initial_plan["Thursday"].to_dict()
        initial_friday = initial_plan["Friday"].to_dict()
        initial_saturday = initial_plan["Saturday"].to_dict()
        initial_wednesday = initial_plan["Wednesday"].to_dict()
        initial_sunday = initial_plan["Sunday"].to_dict()

        # Apply feedback: "Move Tuesday's session to the evening."
        revised_plan = self.agent.revise_plan("Move Tuesday's session to the evening.")

        # Ensure object identity / mutation in place
        self.assertIs(revised_plan, initial_plan)
        self.assertEqual(self.agent.state.study_plan["Tuesday"].time_of_day, "Evening (18:00 - 20:00)")
        self.assertIn("moved from morning to evening", self.agent.state.study_plan["Tuesday"].notes)

        # Verify all other days remain completely unchanged
        self.assertEqual(self.agent.state.study_plan["Monday"].to_dict(), initial_monday)
        self.assertEqual(self.agent.state.study_plan["Thursday"].to_dict(), initial_thursday)
        self.assertEqual(self.agent.state.study_plan["Friday"].to_dict(), initial_friday)
        self.assertEqual(self.agent.state.study_plan["Saturday"].to_dict(), initial_saturday)
        self.assertEqual(self.agent.state.study_plan["Wednesday"].to_dict(), initial_wednesday)
        self.assertEqual(self.agent.state.study_plan["Sunday"].to_dict(), initial_sunday)

    def test_tool_failure_handled_explicitly(self) -> None:
        """Verify tool failures are caught and logged, never silently ignored."""
        failing_tool = ScheduleTool(failure_mode=True)
        agent = StudyPlannerAgent(schedule_tool=failing_tool)

        agent.ingest_initial_request(
            subjects=["Data Structures"],
            hours_per_day=2,
            unavailable_days=["Sunday"],
        )

        with self.assertRaises(ScheduleToolError):
            agent.fetch_existing_schedule(simulate_error=True)

        self.assertGreater(len(agent.state.tool_errors), 0)
        self.assertIn("Calendar service unavailable", agent.state.tool_errors[0])

        # Verify iteration log recorded the error
        last_log = agent.state.iteration_log[-1]
        self.assertEqual(last_log["phase"], "OBSERVE")
        self.assertIn("Explicit tool failure handled", last_log["observation"])

    def test_detect_impossible_requirements(self) -> None:
        """Verify agent detects impossible requirements (all days blocked) rather than silently generating invalid plan."""
        # Block Monday through Saturday as student-unavailable; tool blocks Wednesday
        agent = StudyPlannerAgent(schedule_tool=self.tool)
        agent.ingest_initial_request(
            subjects=["Data Structures"],
            hours_per_day=2,
            unavailable_days=["Monday", "Tuesday", "Thursday", "Friday", "Saturday", "Sunday"],
        )
        agent.fetch_existing_schedule()  # blocks Wednesday

        with self.assertRaises(ValueError) as ctx:
            agent.generate_initial_plan()

        self.assertIn("Conflict Detected: Impossible requirements", str(ctx.exception))
        self.assertFalse(agent.state.goal_completed)
        self.assertIn("Conflict Detected", agent.state.stopping_reason)

    def test_iteration_logs_populated_correctly(self) -> None:
        """Verify every iteration contains required audit fields."""
        self.agent.run_autonomous_loop(
            initial_request={
                "subjects": ["Data Structures", "Operating Systems", "AI Agents"],
                "hours_per_day": 2,
            },
            clarification_data={"unavailable_days": ["Sunday"]},
            feedback="Move Tuesday's session to the evening.",
        )

        logs = self.agent.state.iteration_log
        self.assertGreaterEqual(len(logs), 4)

        required_keys = {"iteration", "phase", "plan", "action", "observation", "goal_satisfied", "stopping_reason"}
        phases_seen = set()

        for entry in logs:
            self.assertTrue(required_keys.issubset(entry.keys()))
            phases_seen.add(entry["phase"])
            self.assertIsInstance(entry["iteration"], int)
            self.assertIsInstance(entry["goal_satisfied"], bool)

        self.assertIn("PLAN", phases_seen)
        self.assertIn("ACT", phases_seen)
        self.assertIn("OBSERVE", phases_seen)
        self.assertIn("REVISE", phases_seen)

    def test_assignment_1_two_rounds_of_feedback(self) -> None:
        """Official Assignment 1: Two consecutive rounds of feedback mutating existing plan."""
        self.agent.run_autonomous_loop(
            initial_request={
                "subjects": ["Data Structures", "Operating Systems", "AI Agents"],
                "hours_per_day": 2,
            },
            clarification_data={"unavailable_days": ["Sunday"]},
        )

        # Round 1: Move Tuesday session to evening
        self.agent.revise_plan("Move Tuesday's session to the evening.")
        self.assertEqual(self.agent.state.study_plan["Tuesday"].time_of_day, "Evening (18:00 - 20:00)")

        # Round 2: Swap Thursday and Saturday subjects (active study days)
        thursday_sub_before = self.agent.state.study_plan["Thursday"].subject
        saturday_sub_before = self.agent.state.study_plan["Saturday"].subject

        self.agent.revise_plan("Swap Thursday and Saturday subjects so AI Agents is studied on Saturday.")

        self.assertEqual(self.agent.state.study_plan["Thursday"].subject, saturday_sub_before)
        self.assertEqual(self.agent.state.study_plan["Saturday"].subject, thursday_sub_before)
        # Verify Tuesday remained evening
        self.assertEqual(self.agent.state.study_plan["Tuesday"].time_of_day, "Evening (18:00 - 20:00)")

    def test_assignment_2_uncovered_conflict_detection_and_exclusion(self) -> None:
        """Official Assignment 2 (Lab Guide pages 8-9):
        - Student marks Sunday as unavailable.
        - Schedule tool returns Wednesday and Friday as busy (at least two busy days).
        - Friday is not initially marked unavailable by the student.
        - Agent must identify Friday as an uncovered conflict and report it before finalizing the plan.
        - Agent must explicitly check that every busy day is excluded before finalization.
        - Agent must NOT silently schedule a session on Friday.
        """
        agent = StudyPlannerAgent(schedule_tool=self.tool)

        # 1. Student marks Sunday as unavailable; Friday is NOT marked unavailable
        initial_unavailable = ["Sunday"]
        self.assertNotIn("Friday", initial_unavailable)

        agent.ingest_initial_request(
            subjects=["Data Structures", "Operating Systems", "AI Agents"],
            hours_per_day=2.0,
            unavailable_days=initial_unavailable,
        )

        # 2. Schedule tool returns at least two busy days: Wednesday and Friday
        schedule_data = agent.fetch_existing_schedule(student_id="default_student")
        busy_days = schedule_data["busy_days"]
        self.assertGreaterEqual(len(busy_days), 2, "read_existing_schedule() must return >= 2 busy days")
        self.assertIn("Wednesday", busy_days)
        self.assertIn("Friday", busy_days)

        # 3. Agent identifies Friday as an uncovered conflict and records it before plan finalization
        uncovered = agent.detect_schedule_conflicts()
        uncovered_days = [c["day"] for c in uncovered]
        self.assertIn("Friday", uncovered_days, "Agent must identify Friday as an uncovered conflict")
        self.assertIn("Wednesday", uncovered_days)
        self.assertIn("Friday", [c["day"] for c in agent.state.uncovered_conflicts])

        # 4. Generate the weekly plan
        plan = agent.generate_initial_plan()

        # 5. Verify the report / assumptions include the uncovered conflict
        conflict_reports = [
            asm for asm in agent.state.assumptions if "Friday" in asm and "conflict" in asm.lower()
        ]
        self.assertTrue(len(conflict_reports) > 0, "Uncovered conflict on Friday must be reported in assumptions")

        # 6. Verify Friday was NOT silently scheduled for a study session
        friday_slot = plan["Friday"]
        self.assertEqual(friday_slot.status, "BUSY_CONFLICT")
        self.assertEqual(friday_slot.hours, 0.0)
        self.assertIsNone(friday_slot.subject, "Friday must not have a study subject assigned")
        self.assertNotEqual(friday_slot.status, "STUDY", "Friday must not be silently scheduled for study")

        # 7. Verify explicit exclusion check validates every busy day
        self.assertTrue(agent.verify_all_busy_days_excluded(plan, set(busy_days)))

        # 8. Verify Wednesday and Sunday are also properly blocked
        self.assertEqual(plan["Wednesday"].status, "BUSY_CONFLICT")
        self.assertEqual(plan["Sunday"].status, "UNAVAILABLE")

        # 9. Verify only active non-blocked days received study allocations
        study_days = [d for d, s in plan.items() if s.status == "STUDY"]
        self.assertEqual(set(study_days), {"Monday", "Tuesday", "Thursday", "Saturday"})
        self.assertNotIn("Friday", study_days)

    def test_verify_all_busy_days_excluded_raises_on_violation(self) -> None:
        """Verify explicit exclusion validator raises AssertionError if a busy day is scheduled."""
        agent = StudyPlannerAgent(schedule_tool=self.tool)
        agent.ingest_initial_request(
            subjects=["Data Structures"],
            hours_per_day=2.0,
            unavailable_days=["Sunday"],
        )
        plan = agent.generate_initial_plan()

        # Artificially corrupt Friday to status 'STUDY' to simulate a silent scheduling bug
        corrupted_plan = dict(plan)
        from agent.planner_agent import DaySchedule
        corrupted_plan["Friday"] = DaySchedule(
            day="Friday",
            status="STUDY",
            subject="Data Structures",
            hours=2.0,
        )

        with self.assertRaises(AssertionError) as ctx:
            agent.verify_all_busy_days_excluded(corrupted_plan, {"Wednesday", "Friday"})
        self.assertIn("Safety Violation: Busy day 'Friday' was erroneously scheduled for study", str(ctx.exception))

    def test_assignment_2_schedule_conflict_detection(self) -> None:
        """Official Assignment 2: Detect scheduling conflict when user commitments leave zero study time."""
        # Student is heavily booked on all days except Sunday, and Sunday is marked unavailable
        busy_tool = ScheduleTool()
        agent = StudyPlannerAgent(schedule_tool=busy_tool)
        agent.ingest_initial_request(
            subjects=["Advanced AI"],
            hours_per_day=3,
            unavailable_days=["Sunday"],
        )
        agent.fetch_existing_schedule(student_id="student_heavily_booked")

        with self.assertRaises(ValueError) as exc:
            agent.generate_initial_plan()

        self.assertIn("Conflict Detected", str(exc.exception))
        self.assertIn("All 7 days are blocked", str(exc.exception))


if __name__ == "__main__":
    unittest.main()

