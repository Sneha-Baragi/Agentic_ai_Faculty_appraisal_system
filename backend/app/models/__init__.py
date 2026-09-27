from app.models.appraisal import (
    AdministrativeActivity,
    AppraisalCycle,
    AppraisalReport,
    AppraisalScore,
    Evidence,
    EvidenceExtraction,
    EvidenceValidation,
    FacultyActivity,
    FacultyAppraisalRun,
    ResearchActivity,
    StudentFeedback,
    Rubric,
    TeachingActivity,
)
from app.models.base import Base
from app.models.governance import ApprovalDecision, AuditLog
from app.models.agent import AppraisalPlan
from app.models.identity import FacultyProfile, Role, User, user_roles

# New models
from app.models.teaching_requirements import TeachingRequirement
from app.models.timetable import TimetableEntry
from app.models.attendance import AttendanceRecord
from app.models.project_teams import ProjectTeam, ProjectTeamMember

__all__ = [
    "Base",
    "User",
    "Role",
    "user_roles",
    "FacultyProfile",
    "AppraisalCycle",
    "FacultyAppraisalRun",
    "FacultyActivity",
    "ResearchActivity",
    "TeachingActivity",
    "AdministrativeActivity",
    "StudentFeedback",
    "Evidence",
    "EvidenceValidation",
    "EvidenceExtraction",
    "Rubric",
    "AppraisalScore",
    "AppraisalReport",
    "ApprovalDecision",
    "AuditLog",
    "AppraisalPlan",
    "TeachingRequirement",
    "TimetableEntry",
    "AttendanceRecord",
    "ProjectTeam",
    "ProjectTeamMember",
]
