from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AppraisalCycle, AppraisalReport, AuditLog, Evidence, FacultyProfile, FacultyAppraisalRun, User
from app.scoring.engine import calculate_score, load_demo_rubric
from app.services.activities import activity_to_dict, list_activities
from app.services.appraisals import latest_report, latest_score
from app.services.cycles import get_open_cycle
from app.services.evidence import EvidenceService, evidence_to_dict
from app.services.feedback import feedback_to_dict, list_student_feedback
from app.services.scoring_map import to_score_inputs


class ToolError(ValueError):
    pass


class FacultyInput(BaseModel):
    faculty_id: UUID


class RecordsInput(BaseModel):
    faculty_id: UUID
    cycle_id: UUID | None = None


class FeedbackInput(RecordsInput):
    pass


class ComputeParameters(BaseModel):
    rubric_id: str = "DEMO_RUBRIC_v1"
    require_evidence: bool = True
    minimum_feedback_rating: float | None = None


class ComputeInput(BaseModel):
    teaching: dict[str, Any]
    research: dict[str, Any]
    service: dict[str, Any]
    feedback: dict[str, Any]
    parameters: ComputeParameters


class CoordinatorInput(RecordsInput):
    request: str = Field(min_length=1, max_length=4000)
    parameters: ComputeParameters = Field(default_factory=ComputeParameters)


class CycleInput(BaseModel):
    cycle_id: UUID | None = None


class RunInput(BaseModel):
    run_id: UUID


class EvidenceInput(BaseModel):
    evidence_id: UUID


class ToolResult(BaseModel):
    tool: str
    data: dict[str, Any]
    invoked_at: datetime


def _is_reviewer(user: User) -> bool:
    return bool({role.name for role in user.roles} & {"hod", "dean", "iqac", "committee", "admin"})


def _authorize_faculty(db: Session, user: User, faculty_id: UUID) -> FacultyProfile:
    profile = db.scalar(select(FacultyProfile).where(FacultyProfile.id == faculty_id))
    if profile is None:
        raise ToolError("Faculty not found")
    if not _is_reviewer(user) and profile.user_id != user.id:
        raise ToolError("Tool access denied")
    return profile


def _record(db: Session, user: User, name: str, entity_id: str | None, success: bool, detail: str | None = None) -> None:
    db.add(AuditLog(actor_id=user.id, action=f"tool_{name}_{'success' if success else 'failure'}", entity_type="agent_tool", entity_id=entity_id, before=None, after={"success": success, "detail": detail}))
    db.commit()


def _invoke(db: Session, user: User, name: str, entity_id: str | None, operation: Callable[[], dict[str, Any]]) -> ToolResult:
    try:
        data = operation()
        _record(db, user, name, entity_id, True)
        return ToolResult(tool=name, data=data, invoked_at=datetime.utcnow())
    except Exception as exc:
        db.rollback()
        _record(db, user, name, entity_id, False, str(exc))
        if isinstance(exc, ToolError):
            raise
        raise ToolError(f"{name} failed") from exc


def get_faculty_profile_tool(db: Session, user: User, request: FacultyInput) -> ToolResult:
    return _invoke(db, user, "get_faculty_profile", str(request.faculty_id), lambda: _profile_data(_authorize_faculty(db, user, request.faculty_id)))


def _profile_data(profile: FacultyProfile) -> dict[str, Any]:
    return {"id": str(profile.id), "user_id": str(profile.user_id), "full_name": profile.full_name, "employee_code": profile.employee_code, "department": profile.department, "designation": profile.designation, "institution": profile.institution, "joining_date": profile.joining_date.isoformat() if profile.joining_date else None}


def get_appraisal_cycle_tool(db: Session, user: User, request: CycleInput) -> ToolResult:
    def operation() -> dict[str, Any]:
        cycle = db.get(AppraisalCycle, request.cycle_id) if request.cycle_id else get_open_cycle(db)
        if cycle is None:
            raise ToolError("Appraisal cycle not found")
        return {"id": str(cycle.id), "name": cycle.name, "academic_year": cycle.academic_year, "status": cycle.status, "starts_on": cycle.starts_on.isoformat(), "ends_on": cycle.ends_on.isoformat()}
    return _invoke(db, user, "get_appraisal_cycle", str(request.cycle_id) if request.cycle_id else None, operation)


def get_faculty_activities_tool(db: Session, user: User, request: FacultyInput) -> ToolResult:
    return _invoke(db, user, "get_faculty_activities", str(request.faculty_id), lambda: {"activities": [activity_to_dict(item) for item in list_activities(db, faculty_id=_authorize_faculty(db, user, request.faculty_id).id)]})


def _read_activity_records(db: Session, user: User, request: RecordsInput, category: str, name: str) -> ToolResult:
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        records = list_activities(db, faculty_id=profile.id, category=category, cycle_id=request.cycle_id)
        return {
            "records": [activity_to_dict(item) for item in records],
            "count": len(records),
            "parsed": {"faculty_id": str(profile.id), "cycle_id": str(request.cycle_id) if request.cycle_id else None, "category": category},
        }

    return _invoke(db, user, name, str(request.faculty_id), operation)


def read_teaching_records_tool(db: Session, user: User, request: RecordsInput) -> ToolResult:
    return _read_activity_records(db, user, request, "teaching", "read_teaching_records")


def read_research_records_tool(db: Session, user: User, request: RecordsInput) -> ToolResult:
    return _read_activity_records(db, user, request, "research", "read_research_records")


def read_service_records_tool(db: Session, user: User, request: RecordsInput) -> ToolResult:
    return _read_activity_records(db, user, request, "administrative", "read_service_records")


def read_student_feedback_tool(db: Session, user: User, request: FeedbackInput) -> ToolResult:
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        records = list_student_feedback(db, faculty_id=profile.id, cycle_id=request.cycle_id)
        return {
            "records": [feedback_to_dict(item) for item in records],
            "count": len(records),
            "parsed": {"faculty_id": str(profile.id), "cycle_id": str(request.cycle_id) if request.cycle_id else None},
        }

    return _invoke(db, user, "read_student_feedback", str(request.faculty_id), operation)


def compute_appraisal_tool(db: Session, user: User, request: ComputeInput) -> ToolResult:
    def operation() -> dict[str, Any]:
        errors: list[str] = []
        activity_records = []
        for source in (request.teaching, request.research, request.service):
            records = source.get("records")
            if not isinstance(records, list):
                errors.append("records must be a list")
            else:
                activity_records.extend(records)
        feedback_records = request.feedback.get("records")
        if not isinstance(feedback_records, list):
            errors.append("feedback.records must be a list")
            feedback_records = []
        if request.parameters.minimum_feedback_rating is not None:
            ratings = [item.get("rating") for item in feedback_records if isinstance(item, dict) and isinstance(item.get("rating"), (int, float))]
            if ratings and sum(ratings) / len(ratings) < request.parameters.minimum_feedback_rating:
                errors.append("student feedback is below the configured minimum")
        if errors:
            return {"valid": False, "computed_values": {}, "parsed_inputs": {}, "validation_errors": errors}
        if request.parameters.require_evidence and any(not item.get("evidence_ids") for item in activity_records):
            errors.append("every activity must have supporting evidence")
        try:
            score = calculate_score(to_score_inputs(activity_records), load_demo_rubric())
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(str(exc))
            return {"valid": False, "computed_values": {}, "parsed_inputs": {"activity_count": len(activity_records), "feedback_count": len(feedback_records)}, "validation_errors": errors}
        return {
            "valid": not errors,
            "computed_values": {"score": score.to_dict(), "activity_count": len(activity_records), "feedback_count": len(feedback_records)},
            "parsed_inputs": {"rubric_id": request.parameters.rubric_id, "activity_count": len(activity_records), "feedback_count": len(feedback_records)},
            "validation_errors": errors,
        }

    return _invoke(db, user, "compute_appraisal", None, operation)


def coordinate_appraisal_tools(db: Session, user: User, request: CoordinatorInput) -> dict[str, Any]:
    from app.services.research_papers import get_research_paper_status
    records_request = RecordsInput(faculty_id=request.faculty_id, cycle_id=request.cycle_id)
    fac_request = FacultyInput(faculty_id=request.faculty_id)

    teaching = read_teaching_records_tool(db, user, records_request)
    research = read_research_records_tool(db, user, records_request)
    service = read_service_records_tool(db, user, records_request)
    feedback = read_student_feedback_tool(db, user, FeedbackInput(faculty_id=request.faculty_id, cycle_id=request.cycle_id))
    teaching_req = get_teaching_requirement_tool(db, user, fac_request)
    project_teams = list_project_teams_tool(db, user, fac_request)
    research_status = get_research_paper_status(db, request.faculty_id, request.cycle_id)

    computed = compute_appraisal_tool(
        db,
        user,
        ComputeInput(teaching=teaching.data, research=research.data, service=service.data, feedback=feedback.data, parameters=request.parameters),
    )

    validated = dict(computed.data)
    validated["teaching_requirement"] = teaching_req.data
    validated["project_teams_count"] = len(project_teams.data.get("teams", []))
    validated["research_paper_status"] = research_status

    tool_calls = [
        teaching.model_dump(),
        research.model_dump(),
        service.model_dump(),
        feedback.model_dump(),
        teaching_req.model_dump(),
        project_teams.model_dump(),
        computed.model_dump(),
    ]

    return {"request": request.request, "tool_calls": tool_calls, "validated_result": validated}


def get_evidence_tool(db: Session, user: User, request: FacultyInput) -> ToolResult:
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        rows = db.scalars(select(Evidence).where(Evidence.faculty_id == profile.id)).all()
        return {"evidence": [evidence_to_dict(item) for item in rows]}
    return _invoke(db, user, "get_evidence", str(request.faculty_id), operation)


def validate_evidence_tool(db: Session, user: User, request: EvidenceInput) -> ToolResult:
    def operation() -> dict[str, Any]:
        evidence = db.scalar(select(Evidence).options(selectinload(Evidence.activity)).where(Evidence.id == request.evidence_id))
        if evidence is None:
            raise ToolError("Evidence not found")
        profile = _authorize_faculty(db, user, evidence.faculty_id)
        if evidence.activity is None:
            raise ToolError("Evidence activity not found")
        updated = EvidenceService().validate_and_extract(db, evidence=evidence, faculty=profile, activity=evidence.activity)
        return {"evidence": evidence_to_dict(updated)}
    return _invoke(db, user, "validate_evidence", str(request.evidence_id), operation)


def calculate_appraisal_score_tool(db: Session, user: User, request: RunInput) -> ToolResult:
    def operation() -> dict[str, Any]:
        run = db.get(FacultyAppraisalRun, request.run_id)
        if run is None:
            raise ToolError("Appraisal run not found")
        _authorize_faculty(db, user, run.faculty_id)
        score = latest_score(db, faculty_id=run.faculty_id, cycle_id=run.cycle_id)
        if score is None:
            raise ToolError("No calculated score found")
        return {"run_id": str(run.id), "total": score.total, "breakdown": score.breakdown, "engine_version": score.engine_version}
    return _invoke(db, user, "calculate_appraisal_score", str(request.run_id), operation)


def generate_appraisal_report_tool(db: Session, user: User, request: RunInput) -> ToolResult:
    def operation() -> dict[str, Any]:
        run = db.get(FacultyAppraisalRun, request.run_id)
        if run is None:
            raise ToolError("Appraisal run not found")
        _authorize_faculty(db, user, run.faculty_id)
        report = latest_report(db, run_id=run.id)
        if report is None:
            raise ToolError("No generated report found")
        return {"id": str(report.id), "version_number": report.version_number, "status": report.status, "report": report.report_json or {}}
    return _invoke(db, user, "generate_appraisal_report", str(request.run_id), operation)


def retrieve_previous_appraisal_tool(db: Session, user: User, request: FacultyInput) -> ToolResult:
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        reports = db.scalars(select(AppraisalReport).join(FacultyAppraisalRun, AppraisalReport.run_id == FacultyAppraisalRun.id).where(FacultyAppraisalRun.faculty_id == profile.id).order_by(AppraisalReport.version_number.desc())).all()
        return {"reports": [{"id": str(item.id), "version_number": item.version_number, "status": item.status, "rating": item.rating_recommendation} for item in reports]}
    return _invoke(db, user, "retrieve_previous_appraisal", str(request.faculty_id), operation)


class TimetableCreateInput(BaseModel):
    faculty_id: UUID
    course_code: str
    section: str
    day_of_week: str
    start_time: str
    end_time: str
    room: str | None = None


class TimetableDeleteInput(BaseModel):
    faculty_id: UUID
    entry_id: UUID


class AttendanceMarkInput(BaseModel):
    faculty_id: UUID
    timetable_entry_id: UUID
    attended_at: datetime | None = None
    status: str = "present"


class ProjectTeamCreateInput(BaseModel):
    faculty_id: UUID
    title: str
    status: str = "active"
    members: list[dict[str, Any]] = []


class ProjectTeamDeleteInput(BaseModel):
    faculty_id: UUID
    team_id: UUID


def get_teaching_requirement_tool(db: Session, user: User, request: FacultyInput) -> ToolResult:
    from app.services.teaching_requirements import get_teaching_requirement_for_faculty
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        u = db.get(User, profile.user_id) or user
        return get_teaching_requirement_for_faculty(db, u, profile)
    return _invoke(db, user, "get_teaching_requirement", str(request.faculty_id), operation)


def list_timetable_tool(db: Session, user: User, request: FacultyInput) -> ToolResult:
    from app.services.timetable import list_timetable_entries
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        entries = list_timetable_entries(db, profile.id)
        return {"timetable": [{"id": str(e.id), "course_code": e.course_code, "section": e.section, "day_of_week": e.day_of_week, "start_time": e.start_time.isoformat() if e.start_time else None, "end_time": e.end_time.isoformat() if e.end_time else None, "room": e.room} for e in entries]}
    return _invoke(db, user, "list_timetable", str(request.faculty_id), operation)


def create_timetable_tool(db: Session, user: User, request: TimetableCreateInput) -> ToolResult:
    from app.services.timetable import create_timetable_entry
    from app.schemas.phase2 import TimetableCreate
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        entry = create_timetable_entry(db, profile.id, TimetableCreate(course_code=request.course_code, section=request.section, day_of_week=request.day_of_week, start_time=request.start_time, end_time=request.end_time, room=request.room))
        return {"id": str(entry.id), "course_code": entry.course_code, "section": entry.section, "day_of_week": entry.day_of_week}
    return _invoke(db, user, "create_timetable", str(request.faculty_id), operation)


def delete_timetable_tool(db: Session, user: User, request: TimetableDeleteInput) -> ToolResult:
    from app.services.timetable import delete_timetable_entry
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        delete_timetable_entry(db, profile.id, request.entry_id)
        return {"deleted": True, "entry_id": str(request.entry_id)}
    return _invoke(db, user, "delete_timetable", str(request.entry_id), operation)


def list_attendance_tool(db: Session, user: User, request: FacultyInput) -> ToolResult:
    from app.services.attendance import list_attendance_records
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        records = list_attendance_records(db, profile.id)
        return {"attendance": records}
    return _invoke(db, user, "list_attendance", str(request.faculty_id), operation)


def mark_attendance_tool(db: Session, user: User, request: AttendanceMarkInput) -> ToolResult:
    from app.services.attendance import mark_attendance
    from app.schemas.phase2 import AttendanceCreate
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        res = mark_attendance(db, profile.id, AttendanceCreate(timetable_entry_id=request.timetable_entry_id, attended_at=request.attended_at, status=request.status))
        return res
    return _invoke(db, user, "mark_attendance", str(request.faculty_id), operation)


def list_project_teams_tool(db: Session, user: User, request: FacultyInput) -> ToolResult:
    from app.services.project_teams import list_project_teams
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        teams = list_project_teams(db, profile.id)
        return {"teams": [{"id": str(t.id), "title": t.title, "status": t.status, "members": [{"name": m.name, "email": m.email} for m in (t.members or [])]} for t in teams]}
    return _invoke(db, user, "list_project_teams", str(request.faculty_id), operation)


def create_project_team_tool(db: Session, user: User, request: ProjectTeamCreateInput) -> ToolResult:
    from app.services.project_teams import create_project_team
    from app.schemas.phase2 import ProjectTeamCreate, ProjectTeamMemberSchema
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        members = [ProjectTeamMemberSchema(name=m.get("name", ""), email=m.get("email")) for m in request.members]
        team = create_project_team(db, profile.id, ProjectTeamCreate(title=request.title, status=request.status, members=members))
        return {"id": str(team.id), "title": team.title, "status": team.status}
    return _invoke(db, user, "create_project_team", str(request.faculty_id), operation)


def delete_project_team_tool(db: Session, user: User, request: ProjectTeamDeleteInput) -> ToolResult:
    from app.services.project_teams import delete_project_team
    def operation() -> dict[str, Any]:
        profile = _authorize_faculty(db, user, request.faculty_id)
        delete_project_team(db, profile.id, request.team_id)
        return {"deleted": True, "team_id": str(request.team_id)}
    return _invoke(db, user, "delete_project_team", str(request.team_id), operation)


TOOL_REGISTRY = {
    "get_faculty_profile": get_faculty_profile_tool,
    "get_appraisal_cycle": get_appraisal_cycle_tool,
    "get_faculty_activities": get_faculty_activities_tool,
    "read_teaching_records": read_teaching_records_tool,
    "read_research_records": read_research_records_tool,
    "read_service_records": read_service_records_tool,
    "read_student_feedback": read_student_feedback_tool,
    "compute_appraisal": compute_appraisal_tool,
    "get_evidence": get_evidence_tool,
    "validate_evidence": validate_evidence_tool,
    "calculate_appraisal_score": calculate_appraisal_score_tool,
    "generate_appraisal_report": generate_appraisal_report_tool,
    "retrieve_previous_appraisal": retrieve_previous_appraisal_tool,
    "get_teaching_requirement": get_teaching_requirement_tool,
    "list_timetable": list_timetable_tool,
    "create_timetable": create_timetable_tool,
    "delete_timetable": delete_timetable_tool,
    "list_attendance": list_attendance_tool,
    "mark_attendance": mark_attendance_tool,
    "list_project_teams": list_project_teams_tool,
    "create_project_team": create_project_team_tool,
    "delete_project_team": delete_project_team_tool,
}

