from __future__ import annotations

import datetime as _dt
from typing import Any, Optional, Union

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StrictInt, field_validator


class _ResearchMetricsValues(BaseModel):
    h_index: StrictInt | None = None
    i10_index: StrictInt | None = None
    total_citations: StrictInt | None = None
    papers_this_year: StrictInt | None = None
    source: str = Field(min_length=1)
    captured_at: _dt.datetime | None = None

    @field_validator("h_index", "i10_index", "total_citations", "papers_this_year")
    @classmethod
    def validate_non_negative_metric(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("research metric values cannot be negative")
        return value

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source must not be blank")
        return value

    @field_validator("captured_at")
    @classmethod
    def validate_utc_capture_time(cls, value: _dt.datetime | None) -> _dt.datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() != _dt.timedelta(0):
                raise ValueError("captured_at must be a UTC datetime")
            return value.astimezone(_dt.timezone.utc)
        return value


class ResearchMetricsInput(_ResearchMetricsValues):
    pass


class ResearchMetricsSnapshot(_ResearchMetricsValues):
    scholar_profile_url: str | None = None
    captured_at: _dt.datetime


class AppraisalRunRequest(BaseModel):
    research_metrics: ResearchMetricsInput | None = Field(
        default=None,
        deprecated=True,
        description="Accepted for backward compatibility but ignored; metrics are retrieved from the stored Scholar profile.",
    )


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    institution: Optional[str] = None
    joining_date: Optional[_dt.date] = None
    google_scholar_id: Optional[str] = None
    google_scholar_url: Optional[AnyHttpUrl] = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    email: str
    employee_code: str
    full_name: Optional[str]
    department: str
    designation: str
    institution: Optional[str]
    joining_date: Optional[_dt.date]
    google_scholar_id: Optional[str]
    google_scholar_url: Optional[AnyHttpUrl]


class CycleCreate(BaseModel):
    name: str
    academic_year: str
    start_date: _dt.date
    end_date: _dt.date
    status: str = "open"


class CycleOut(BaseModel):
    id: str
    name: str
    academic_year: str
    start_date: Optional[_dt.date]
    end_date: Optional[_dt.date]
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ActivityCreate(BaseModel):
    category: str
    activity_type: str
    title: str
    description: Optional[str] = None
    date: Optional[_dt.date] = None
    extras: dict[str, Any] = Field(default_factory=dict)


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[_dt.date] = None
    activity_type: Optional[str] = None
    extras: Optional[dict[str, Any]] = None
