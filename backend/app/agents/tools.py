from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AppraisalCycle, AppraisalReport, AppraisalScore, AuditLog, Evidence, FacultyActivity, FacultyProfile, FacultyAppraisalRun, User
from app.scoring.engine import calculate_score, load_demo_rubric
from app.services.activities import activity_to_dict, list_activities
from app.services.appraisals import latest_report, latest_score
from app.services.cycles import get_open_cycle
from app.services.evidence import EvidenceService, evidence_to_dict


class ToolError(ValueError):
    pass


class FacultyInput(BaseModel):
    faculty_id: UUID


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


TOOL_REGISTRY = {
    "get_faculty_profile": get_faculty_profile_tool,
    "get_appraisal_cycle": get_appraisal_cycle_tool,
    "get_faculty_activities": get_faculty_activities_tool,
    "get_evidence": get_evidence_tool,
    "validate_evidence": validate_evidence_tool,
    "calculate_appraisal_score": calculate_appraisal_score_tool,
    "generate_appraisal_report": generate_appraisal_report_tool,
    "retrieve_previous_appraisal": retrieve_previous_appraisal_tool,
}
