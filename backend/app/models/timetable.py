from datetime import datetime
import uuid

from sqlalchemy import String, Time, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PortableUUID


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_profiles.id"), nullable=False, index=True
    )
    course_code: Mapped[str] = mapped_column(String(64), nullable=False)
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., Monday
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    room: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
