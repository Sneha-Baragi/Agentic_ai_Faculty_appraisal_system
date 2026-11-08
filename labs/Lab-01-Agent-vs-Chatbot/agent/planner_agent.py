"""Study Planner Agent with Autonomous Goal-Plan-Act-Observe-Revise Loop.

This module implements the Study Planner Agent for Lab 1.
Unlike a conventional chatbot, this agent:
1. Maintains structured internal state across all reasoning steps.
2. Formulates explicit goals and halts upon reaching a declared stopping condition.
3. Plans missing requirement discovery, asking ONLY for missing parameters.
4. Autonomously invokes external tools (ScheduleTool) to inspect calendar conflicts.
5. Generates conflict-free, repeatable study plans with explicit assumptions.
6. Implements in-place revision: mutates the existing schedule without re-planning from scratch.
7. Logs every iteration (Goal, Plan, Act, Observe, Revise) into a transparent audit trail.
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from agent.schedule_tool import ScheduleTool, ScheduleToolError, read_existing_schedule

DAYS_OF_WEEK: List[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


@dataclass
class DaySchedule:
    """Represents a scheduled day within the weekly study plan."""
    day: str
    status: str  # 'STUDY', 'BUSY_CONFLICT', 'UNAVAILABLE', 'OFF'
    subject: Optional[str] = None
    hours: float = 0.0
    time_of_day: str = "Unassigned"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "status": self.status,
            "subject": self.subject,
            "hours": self.hours,
            "time_of_day": self.time_of_day,
            "notes": self.notes,
        }


@dataclass
class AgentState:
    """Structured internal state maintained across the agent loop."""
    goal: str
    subjects: List[str] = field(default_factory=list)
    hours_per_day: Optional[float] = None
    unavailable_days: Optional[List[str]] = None
    existing_schedule: Optional[Dict[str, Any]] = None
    study_plan: Optional[Dict[str, DaySchedule]] = None
    assumptions: List[str] = field(default_factory=list)
    goal_completed: bool = False
    schedule_generated: bool = False
    stopping_reason: Optional[str] = None
    iteration_log: List[Dict[str, Any]] = field(default_factory=list)
    tool_errors: List[str] = field(default_factory=list)
    uncovered_conflicts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "subjects": list(self.subjects),
            "hours_per_day": self.hours_per_day,
            "unavailable_days": list(self.unavailable_days) if self.unavailable_days is not None else None,
            "existing_schedule": self.existing_schedule,
            "study_plan": {k: v.to_dict() for k, v in self.study_plan.items()} if self.study_plan else None,
            "assumptions": list(self.assumptions),
            "goal_completed": self.goal_completed,
            "schedule_generated": self.schedule_generated,
            "stopping_reason": self.stopping_reason,
            "iteration_log": self.iteration_log,
            "tool_errors": self.tool_errors,
            "uncovered_conflicts": [dict(c) for c in self.uncovered_conflicts],
        }


class StudyPlannerAgent:
    """Stateful agent orchestrating the Goal-Plan-Act-Observe-Revise loop."""

    def __init__(
        self,
        goal: str = "Generate a conflict-free 7-day study plan matching student goals and timetable constraints.",
        schedule_tool: Optional[ScheduleTool] = None,
    ) -> None:
        self.state = AgentState(goal=goal)
        self.schedule_tool = schedule_tool or ScheduleTool()
        self.current_iteration = 0

        # Log initial GOAL formulation
        self._log_iteration(
            phase="GOAL",
            plan_desc=f"Establish operational goal: '{goal}'.",
            action_desc="Initialize structured state with declared stopping condition (schedule_generated == True).",
            observation_desc="Stopping condition declared; state ready for requirement analysis.",
            goal_satisfied=False,
            stopping_reason=None,
        )

    # -------------------------------------------------------------------------
    # AGENT LOOP PRIMITIVES: GOAL, PLAN, ACT, OBSERVE, REVISE
    # -------------------------------------------------------------------------

    def is_stopping_condition_met(self) -> bool:
        """Evaluate declared stopping condition: schedule generated and verified."""
        return self.state.schedule_generated and self.state.goal_completed

    def _log_iteration(
        self,
        phase: str,
        plan_desc: str,
        action_desc: str,
        observation_desc: str,
        goal_satisfied: bool,
        stopping_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record structured iteration step into the agent state."""
        self.current_iteration += 1
        entry = {
            "iteration": self.current_iteration,
            "phase": phase,
            "plan": plan_desc,
            "action": action_desc,
            "observation": observation_desc,
            "goal_satisfied": goal_satisfied,
            "stopping_reason": stopping_reason,
        }
        self.state.iteration_log.append(entry)
        return entry

    def inspect_missing_information(self) -> List[str]:
        """PLAN: Inspect structured state to determine what required information is missing.

        Ensures the agent asks ONLY for missing items and does not re-ask for
        parameters already provided.
        """
        missing = []
        if not self.state.subjects:
            missing.append("subjects")
        if self.state.hours_per_day is None or self.state.hours_per_day <= 0:
            missing.append("hours_per_day")
        if self.state.unavailable_days is None:
            missing.append("unavailable_days")
        return missing

    def ingest_initial_request(
        self,
        subjects: Optional[List[str]] = None,
        hours_per_day: Optional[float] = None,
        unavailable_days: Optional[List[str]] = None,
    ) -> None:
        """ACT & OBSERVE: Receive and store initial student inputs."""
        if subjects:
            self.state.subjects = [s.strip() for s in subjects if s.strip()]
        if hours_per_day is not None and hours_per_day > 0:
            self.state.hours_per_day = float(hours_per_day)
        if unavailable_days is not None:
            self.state.unavailable_days = [d.capitalize().strip() for d in unavailable_days]

        self._log_iteration(
            phase="OBSERVE",
            plan_desc="Parse and ingest initial student study planning request.",
            action_desc=f"Recorded inputs: subjects={self.state.subjects}, hours_per_day={self.state.hours_per_day}, unavailable_days={self.state.unavailable_days}.",
            observation_desc="Stored parameters in structured agent state.",
            goal_satisfied=False,
            stopping_reason=None,
        )

    def step_clarification(self) -> Tuple[bool, List[str]]:
        """PLAN & ACT: Identify missing items and generate clarification inquiries.

        Returns:
            Tuple of (is_complete, list_of_clarification_questions)
        """
        missing = self.inspect_missing_information()

        # Record explicit PLAN phase assessing missing requirements
        self._log_iteration(
            phase="PLAN",
            plan_desc="Inspect structured state to identify missing parameters before scheduling.",
            action_desc=f"Analyzed state: missing={missing if missing else 'None'}.",
            observation_desc=f"{len(missing)} missing parameter(s) identified." if missing else "All student requirements present.",
            goal_satisfied=False,
            stopping_reason=None,
        )

        if not missing:
            return True, []

        questions = []
        if "subjects" in missing:
            questions.append("What academic subjects do you need to study this week?")
        if "hours_per_day" in missing:
            questions.append("How many hours per day can you dedicate to studying (e.g., 2 hours)?")
        if "unavailable_days" in missing:
            questions.append("Which days of the week are you unavailable for study sessions (e.g., Sunday)?")

        self._log_iteration(
            phase="ACT",
            plan_desc=f"Formulate clarification requests for missing parameters: {missing}.",
            action_desc=f"Generated {len(questions)} targeted question(s).",
            observation_desc=f"Waiting on user input for: {', '.join(missing)}.",
            goal_satisfied=False,
            stopping_reason=None,
        )
        return False, questions

    def supply_clarification(
        self,
        subjects: Optional[List[str]] = None,
        hours_per_day: Optional[float] = None,
        unavailable_days: Optional[List[str]] = None,
    ) -> None:
        """OBSERVE: Incorporate answered clarifications into state."""
        provided = []
        if subjects and not self.state.subjects:
            self.state.subjects = [s.strip() for s in subjects if s.strip()]
            provided.append("subjects")
        if hours_per_day is not None and (self.state.hours_per_day is None or self.state.hours_per_day <= 0):
            self.state.hours_per_day = float(hours_per_day)
            provided.append("hours_per_day")
        if unavailable_days is not None and self.state.unavailable_days is None:
            self.state.unavailable_days = [d.capitalize().strip() for d in unavailable_days]
            provided.append("unavailable_days")

        self._log_iteration(
            phase="OBSERVE",
            plan_desc="Receive clarification inputs from student.",
            action_desc=f"Updated missing parameters: {provided}.",
            observation_desc="Clarifications integrated into structured state.",
            goal_satisfied=False,
            stopping_reason=None,
        )

    def fetch_existing_schedule(
        self,
        student_id: str = "default_student",
        simulate_error: bool = False,
    ) -> Dict[str, Any]:
        """ACT & OBSERVE: Query institutional timetable tool to retrieve busy days."""
        plan_desc = f"Call external schedule_tool.read_existing_schedule for student '{student_id}'."

        self._log_iteration(
            phase="PLAN",
            plan_desc=plan_desc,
            action_desc="Prepare tool parameters to inspect external calendar conflicts.",
            observation_desc="Schedule verification tool selected for invocation.",
            goal_satisfied=False,
            stopping_reason=None,
        )

        try:
            schedule_result = self.schedule_tool.read_existing_schedule(
                student_id=student_id,
                simulate_error=simulate_error,
            )
            self.state.existing_schedule = schedule_result
            busy_days = schedule_result.get("busy_days", [])

            self._log_iteration(
                phase="OBSERVE",
                plan_desc=plan_desc,
                action_desc="Tool executed successfully.",
                observation_desc=f"Identified external busy commitments on: {busy_days}.",
                goal_satisfied=False,
                stopping_reason=None,
            )
            return schedule_result

        except ScheduleToolError as err:
            error_msg = str(err)
            self.state.tool_errors.append(error_msg)
            self._log_iteration(
                phase="OBSERVE",
                plan_desc=plan_desc,
                action_desc="Tool execution failed with ScheduleToolError.",
                observation_desc=f"Explicit tool failure handled: {error_msg}",
                goal_satisfied=False,
                stopping_reason="Tool execution failure encountered.",
            )
            raise

    def detect_schedule_conflicts(self) -> List[Dict[str, Any]]:
        """PLAN & OBSERVE: Identify external calendar conflicts not declared by the student.

        Cross-references student-declared unavailable days against busy days returned by
        the institutional schedule tool. Identifies any uncovered commitments (such as
        Friday or Wednesday) so they are reported and excluded before finalization.
        """
        if not self.state.existing_schedule:
            self.fetch_existing_schedule()

        busy_days = self.state.existing_schedule.get("busy_days", [])
        unavailable = set(self.state.unavailable_days or [])
        commitments = self.state.existing_schedule.get("commitments", {})

        uncovered: List[Dict[str, Any]] = []
        for day in busy_days:
            if day not in unavailable:
                conflict_entry = {
                    "day": day,
                    "source": "ScheduleTool",
                    "commitment": commitments.get(day, "Institutional Commitment"),
                    "student_marked_unavailable": False,
                    "resolution": f"Proactively excluded {day} from study allocations to prevent schedule conflict.",
                }
                uncovered.append(conflict_entry)

        # Prevent duplicate iteration logging if already detected for identical state
        existing_conflict_days = [c["day"] for c in self.state.uncovered_conflicts]
        new_conflict_days = [c["day"] for c in uncovered]
        if self.state.uncovered_conflicts and existing_conflict_days == new_conflict_days:
            return self.state.uncovered_conflicts

        self.state.uncovered_conflicts = uncovered

        if uncovered:
            uncovered_days = [c["day"] for c in uncovered]
            self._log_iteration(
                phase="PLAN",
                plan_desc="Cross-reference student declared availability against external timetable commitments.",
                action_desc=f"Detected {len(uncovered)} uncovered calendar conflict(s): {uncovered_days}.",
                observation_desc=(
                    f"Identified uncovered conflict on {', '.join(uncovered_days)} "
                    f"(external busy commitment not declared by student). Enforcing exclusion before finalizing plan."
                ),
                goal_satisfied=False,
                stopping_reason=None,
            )
            for c in uncovered:
                conflict_report = (
                    f"Uncovered conflict detected: {c['day']} has campus commitment '{c['commitment']}'. "
                    f"Proactively excluded from study allocations."
                )
                if conflict_report not in self.state.assumptions:
                    self.state.assumptions.append(conflict_report)

        return uncovered

    def verify_all_busy_days_excluded(
        self,
        plan: Dict[str, DaySchedule],
        busy_days: set,
    ) -> bool:
        """Explicit safety verification: Ensure EVERY institutional busy day is strictly excluded from study allocations.

        Guarantees that no busy day (such as Wednesday or Friday) is silently scheduled
        for a study session. Raises AssertionError if any busy day has status == 'STUDY' or hours > 0.
        """
        for busy_day in busy_days:
            schedule_item = plan.get(busy_day)
            if schedule_item is None:
                raise AssertionError(f"Safety Check Failed: Busy day '{busy_day}' is missing from the 7-day study plan.")
            if schedule_item.status == "STUDY":
                raise AssertionError(
                    f"Safety Violation: Busy day '{busy_day}' was erroneously scheduled for study with "
                    f"subject '{schedule_item.subject}'! Institutional commitments must not be overwritten."
                )
            if schedule_item.hours > 0.0:
                raise AssertionError(
                    f"Safety Violation: Busy day '{busy_day}' has {schedule_item.hours} hours scheduled! "
                    "Must be 0.0 hours."
                )
            if schedule_item.status != "BUSY_CONFLICT":
                raise AssertionError(
                    f"Safety Violation: Busy day '{busy_day}' has status '{schedule_item.status}' instead of 'BUSY_CONFLICT'."
                )
            if schedule_item.subject is not None:
                raise AssertionError(
                    f"Safety Violation: Busy day '{busy_day}' has subject '{schedule_item.subject}' assigned! "
                    "Subject must be None for busy conflict days."
                )
        return True

    def generate_initial_plan(self) -> Dict[str, DaySchedule]:
        """ACT: Synthesize the weekly study plan enforcing constraints and assumptions."""
        # 1. Validation of minimum prerequisites
        missing = self.inspect_missing_information()
        if missing:
            raise ValueError(f"Cannot generate plan. Missing requirements: {missing}")

        if not self.state.existing_schedule:
            self.fetch_existing_schedule()

        # Proactively detect and report any uncovered calendar conflicts before finalizing plan
        self.detect_schedule_conflicts()

        busy_days = set(self.state.existing_schedule.get("busy_days", []))
        unavailable = set(self.state.unavailable_days or [])
        commitments = self.state.existing_schedule.get("commitments", {})

        # 2. Check for impossible / conflicting scenarios
        blocked_days = busy_days.union(unavailable)
        available_days = [d for d in DAYS_OF_WEEK if d not in blocked_days]

        if not available_days:
            reason = (
                "Conflict Detected: Impossible requirements. All 7 days are blocked "
                f"(Unavailable: {sorted(list(unavailable))}, Institutional Busy: {sorted(list(busy_days))})."
            )
            self.state.stopping_reason = reason
            self._log_iteration(
                phase="ACT",
                plan_desc="Generate balanced weekly schedule.",
                action_desc="Calculated available study slots across 7-day window.",
                observation_desc=f"0 available days remain. {reason}",
                goal_satisfied=False,
                stopping_reason=reason,
            )
            raise ValueError(reason)

        # 3. Repeatable round-robin subject allocation across available study days
        plan: Dict[str, DaySchedule] = {}
        assumptions: List[str] = [
            f"Daily study volume fixed at {self.state.hours_per_day} hours per active day.",
            "Default Morning block (09:00 - 11:00) allocated for study sessions unless requested otherwise.",
            f"Institutional busy days ({sorted(list(busy_days))}) avoided to prevent campus schedule conflicts.",
            f"Student personal rest days ({sorted(list(unavailable))}) respected with zero study allocations.",
            "Subjects distributed systematically in round-robin sequence to ensure balanced coverage.",
        ]
        # Append uncovered conflict assumptions if any were detected
        for c in self.state.uncovered_conflicts:
            conflict_report = (
                f"Uncovered conflict detected: {c['day']} has campus commitment '{c['commitment']}'. "
                f"Proactively excluded from study allocations."
            )
            if conflict_report not in assumptions:
                assumptions.append(conflict_report)

        subject_idx = 0
        num_subjects = len(self.state.subjects)

        for day in DAYS_OF_WEEK:
            if day in unavailable:
                plan[day] = DaySchedule(
                    day=day,
                    status="UNAVAILABLE",
                    subject=None,
                    hours=0.0,
                    time_of_day="Off",
                    notes="Student-designated unavailable day (Rest / Personal).",
                )
            elif day in busy_days:
                plan[day] = DaySchedule(
                    day=day,
                    status="BUSY_CONFLICT",
                    subject=None,
                    hours=0.0,
                    time_of_day="Institutional Schedule",
                    notes=f"Campus commitment: {commitments.get(day, 'Institutional Seminar / Lab')}.",
                )
            else:
                assigned_subject = self.state.subjects[subject_idx % num_subjects]
                subject_idx += 1
                plan[day] = DaySchedule(
                    day=day,
                    status="STUDY",
                    subject=assigned_subject,
                    hours=float(self.state.hours_per_day),
                    time_of_day="Morning (09:00 - 11:00)",
                    notes=f"Core curriculum study session for {assigned_subject}.",
                )

        # 4. EXPLICIT PRE-FINALIZATION CHECK: Ensure every busy day is strictly excluded
        self.verify_all_busy_days_excluded(plan, busy_days)

        self.state.study_plan = plan
        self.state.assumptions = assumptions
        self.state.schedule_generated = True
        self.state.goal_completed = True
        self.state.stopping_reason = (
            "Conflict-free 7-day study plan successfully generated, verified against calendar constraints."
        )

        self._log_iteration(
            phase="ACT",
            plan_desc="Construct 7-day schedule with balanced round-robin subject assignment.",
            action_desc=f"Allocated {len(available_days)} study slots across available days: {available_days}.",
            observation_desc="Initial schedule generated; verified all institutional busy days (including uncovered conflicts) are strictly excluded from study allocations.",
            goal_satisfied=True,
            stopping_reason=self.state.stopping_reason,
        )
        return plan

    def revise_plan(self, feedback: str) -> Dict[str, DaySchedule]:
        """REVISE: Mutate the existing plan in-place based on user feedback.

        CRITICAL REQUIREMENT:
        Mutates the existing study_plan dictionary without re-running the initial
        planning process from scratch, strictly preserving all non-targeted entries.
        """
        if not self.state.study_plan:
            raise ValueError("Cannot revise plan: No existing study plan has been generated yet.")

        plan = self.state.study_plan
        feedback_lower = feedback.lower()
        plan_desc = f"Process user feedback and mutate existing plan: '{feedback}'."
        actions_taken = []

        # Case 1: Time of day change (e.g. "Move Tuesday's session to the evening")
        target_day = None
        for day in DAYS_OF_WEEK:
            if day.lower() in feedback_lower:
                target_day = day
                break

        if target_day and target_day in plan:
            day_schedule = plan[target_day]

            if "evening" in feedback_lower:
                old_time = day_schedule.time_of_day
                day_schedule.time_of_day = "Evening (18:00 - 20:00)"
                day_schedule.notes += " [Mutated: moved from morning to evening per feedback]"
                actions_taken.append(
                    f"Mutated {target_day} session: time_of_day changed from '{old_time}' to 'Evening (18:00 - 20:00)'."
                )

            elif "afternoon" in feedback_lower:
                old_time = day_schedule.time_of_day
                day_schedule.time_of_day = "Afternoon (14:00 - 16:00)"
                day_schedule.notes += " [Mutated: moved to afternoon per feedback]"
                actions_taken.append(
                    f"Mutated {target_day} session: time_of_day changed from '{old_time}' to 'Afternoon (14:00 - 16:00)'."
                )

            elif "morning" in feedback_lower:
                old_time = day_schedule.time_of_day
                day_schedule.time_of_day = "Morning (09:00 - 11:00)"
                day_schedule.notes += " [Mutated: set to morning per feedback]"
                actions_taken.append(f"Mutated {target_day} session time to Morning.")

        # Case 2: Subject swap between two days (e.g., "Swap Thursday and Saturday subjects")
        if "swap" in feedback_lower:
            days_mentioned = [d for d in DAYS_OF_WEEK if d.lower() in feedback_lower]
            if len(days_mentioned) >= 2:
                d1, d2 = days_mentioned[0], days_mentioned[1]
                busy_days = set(self.state.existing_schedule.get("busy_days", [])) if self.state.existing_schedule else set()
                if d1 in busy_days or d2 in busy_days:
                    blocked = d1 if d1 in busy_days else d2
                    actions_taken.append(
                        f"Refused swap targeting {blocked}: day is reserved for institutional commitment ({plan[blocked].notes})."
                    )
                elif plan[d1].status != "STUDY" or plan[d2].status != "STUDY":
                    actions_taken.append(
                        f"Cannot swap between {d1} and {d2}: both slots must be active study sessions."
                    )
                else:
                    s1, s2 = plan[d1].subject, plan[d2].subject
                    plan[d1].subject = s2
                    plan[d2].subject = s1
                    plan[d1].notes += f" [Mutated: swapped with {d2}]"
                    plan[d2].notes += f" [Mutated: swapped with {d1}]"
                    actions_taken.append(f"Swapped subjects between {d1} ({s1} -> {s2}) and {d2} ({s2} -> {s1}).")

        # Case 3: Subject replacement / revision focus (e.g., "Change Saturday focus to Practice Tests")
        if "revision" in feedback_lower or "practice" in feedback_lower:
            if target_day and plan[target_day].status == "STUDY":
                old_sub = plan[target_day].subject
                plan[target_day].subject = "Comprehensive Revision & Practice Tests"
                plan[target_day].notes += f" [Mutated: shifted from {old_sub} to Revision & Tests]"
                actions_taken.append(f"Updated {target_day} subject to 'Comprehensive Revision & Practice Tests'.")

        if not actions_taken:
            # Fallback for general feedback
            actions_taken.append("Feedback recorded; schedule validated without structural modifications.")

        self.state.assumptions.append(f"Revised plan reflects user feedback: '{feedback}'.")

        self._log_iteration(
            phase="REVISE",
            plan_desc=plan_desc,
            action_desc="; ".join(actions_taken),
            observation_desc="Existing plan mutated in-place. All other schedule entries preserved intact.",
            goal_satisfied=True,
            stopping_reason="Plan updated per user revision feedback.",
        )
        return plan

    def run_autonomous_loop(
        self,
        initial_request: Dict[str, Any],
        clarification_data: Optional[Dict[str, Any]] = None,
        feedback: Optional[str] = None,
        student_id: str = "default_student",
    ) -> Dict[str, Any]:
        """Execute the full end-to-end autonomous agent loop deterministically."""
        # Step 1: GOAL & INITIAL INGEST
        self.ingest_initial_request(
            subjects=initial_request.get("subjects"),
            hours_per_day=initial_request.get("hours_per_day"),
            unavailable_days=initial_request.get("unavailable_days"),
        )

        # Step 2: PLAN & CLARIFY
        is_complete, questions = self.step_clarification()
        if not is_complete:
            if clarification_data:
                self.supply_clarification(
                    subjects=clarification_data.get("subjects"),
                    hours_per_day=clarification_data.get("hours_per_day"),
                    unavailable_days=clarification_data.get("unavailable_days"),
                )
            else:
                return {
                    "status": "awaiting_clarification",
                    "missing_fields": self.inspect_missing_information(),
                    "questions": questions,
                    "state": self.state.to_dict(),
                }

        # Step 3: ACT (TOOL INVOCATION)
        self.fetch_existing_schedule(student_id=student_id)

        # Step 4: ACT (SCHEDULE GENERATION) & OBSERVE
        initial_plan = self.generate_initial_plan()

        # Step 5: REVISE (if feedback provided)
        if feedback:
            self.revise_plan(feedback)

        return {
            "status": "completed",
            "state": self.state.to_dict(),
            "study_plan": {k: v.to_dict() for k, v in self.state.study_plan.items()},
            "stopping_condition_met": self.is_stopping_condition_met(),
        }
