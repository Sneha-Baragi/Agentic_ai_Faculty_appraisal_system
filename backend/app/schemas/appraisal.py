from __future__ import annotations

import datetime as _dt
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    institution: Optional[str] = None
    joining_date: Optional[_dt.date] = None


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
