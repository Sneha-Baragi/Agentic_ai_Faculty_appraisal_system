from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeachingRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    required_hours: float
    actual_hours: float
    remaining_hours: float
    completed: bool


class TimetableCreate(BaseModel):
    course_code: str
    section: str
    day_of_week: str
    start_time: str
    end_time: str
    room: Optional[str] = None


class TimetableUpdate(BaseModel):
    course_code: Optional[str] = None
    section: Optional[str] = None
    day_of_week: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None


class TimetableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    faculty_id: str
    course_code: str
    section: str
    day_of_week: str
    start_time: str
    end_time: str
    room: Optional[str] = None
    created_at: datetime


class AttendanceCreate(BaseModel):
    timetable_entry_id: UUID
    attended_at: Optional[datetime] = None
    status: str = "present"


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    faculty_id: str
    timetable_entry_id: str
    status: str
    attended_at: datetime
    course_code: Optional[str] = None
    section: Optional[str] = None
    day_of_week: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None


class ProjectTeamMemberSchema(BaseModel):
    id: Optional[str] = None
    name: str
    email: Optional[str] = None


class ProjectTeamCreate(BaseModel):
    title: str
    status: str = "active"
    members: list[ProjectTeamMemberSchema] = Field(default_factory=list)


class ProjectTeamUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    members: Optional[list[ProjectTeamMemberSchema]] = None


class ProjectTeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    faculty_id: str
    title: str
    status: str
    members: list[ProjectTeamMemberSchema] = Field(default_factory=list)
    created_at: datetime


class ResearchPaperRequirementOut(BaseModel):
    submitted_count: int
    required_count: int = 2
    is_satisfied: bool
