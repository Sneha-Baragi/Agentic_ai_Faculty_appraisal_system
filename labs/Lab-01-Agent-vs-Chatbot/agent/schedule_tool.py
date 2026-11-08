"""Schedule Verification Tool for Study Planner Agent.

This module provides an external tool integration simulating an institutional
calendar / timetable service. The agent calls this tool to retrieve pre-existing
busy commitments (such as departmental seminars, lab sessions, or lectures) so it
can avoid scheduling conflicts.
"""

from typing import Any, Dict, List, Optional


class ScheduleToolError(Exception):
    """Raised when the schedule verification tool encounters an operational failure."""
    pass


class ScheduleTool:
    """Tool that queries student commitments from an institutional calendar service."""

    DEFAULT_SCHEDULE_DATABASE: Dict[str, Dict[str, Any]] = {
        "default_student": {
            "busy_days": ["Wednesday", "Friday"],
            "commitments": {
                "Wednesday": "Department Seminar & Hardware Lab (09:00 - 17:00)",
                "Friday": "Campus Project Mentorship & Lab Practicals (10:00 - 16:00)",
            },
        },
        "student_01": {
            "busy_days": ["Wednesday", "Friday"],
            "commitments": {
                "Wednesday": "Department Seminar & Hardware Lab (09:00 - 17:00)",
                "Friday": "Campus Project Mentorship & Lab Practicals (10:00 - 16:00)",
            },
        },
        "assignment_2_student": {
            "busy_days": ["Wednesday", "Friday"],
            "commitments": {
                "Wednesday": "Department Seminar & Hardware Lab (09:00 - 17:00)",
                "Friday": "Campus Project Mentorship & Lab Practicals (10:00 - 16:00)",
            },
        },
        "student_busy_friday": {
            "busy_days": ["Friday"],
            "commitments": {
                "Friday": "Industry Internship Workshop (10:00 - 16:00)",
            },
        },
        "student_heavily_booked": {
            "busy_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
            "commitments": {
                "Monday": "Core Labs",
                "Tuesday": "Project Sprint",
                "Wednesday": "Seminar",
                "Thursday": "Tutorials",
                "Friday": "Electives",
                "Saturday": "Campus Club Activities",
            },
        },
    }

    def __init__(self, failure_mode: bool = False) -> None:
        self.failure_mode: bool = failure_mode
        self.invocation_count: int = 0
        self.last_query_target: Optional[str] = None

    def read_existing_schedule(
        self,
        student_id: str = "default_student",
        simulate_error: bool = False,
    ) -> Dict[str, Any]:
        """Fetch pre-existing timetable commitments for the designated student.

        Args:
            student_id: Unique identifier for the student.
            simulate_error: If True, forces an explicit tool failure.

        Returns:
            Dictionary containing:
                - status: 'success' or 'error'
                - busy_days: list of strings (e.g., ['Wednesday'])
                - commitments: dictionary mapping busy day to activity description

        Raises:
            ScheduleToolError: When simulate_error is True or tool is in failure_mode.
        """
        self.invocation_count += 1
        self.last_query_target = student_id

        if simulate_error or self.failure_mode:
            raise ScheduleToolError(
                f"[ScheduleTool Failure] Calendar service unavailable for student '{student_id}'. "
                "Institutional API connection timed out."
            )

        schedule_data = self.DEFAULT_SCHEDULE_DATABASE.get(
            student_id,
            self.DEFAULT_SCHEDULE_DATABASE["default_student"],
        )

        return {
            "status": "success",
            "student_id": student_id,
            "busy_days": list(schedule_data["busy_days"]),
            "commitments": dict(schedule_data.get("commitments", {})),
            "source": "Institutional_Timetable_Service_v1",
        }


# Convenience standalone function matching the lab specification
_DEFAULT_TOOL_INSTANCE = ScheduleTool()


def read_existing_schedule(
    student_id: str = "default_student",
    simulate_error: bool = False,
) -> Dict[str, Any]:
    """Module-level entry point for reading existing schedules."""
    return _DEFAULT_TOOL_INSTANCE.read_existing_schedule(
        student_id=student_id,
        simulate_error=simulate_error,
    )

