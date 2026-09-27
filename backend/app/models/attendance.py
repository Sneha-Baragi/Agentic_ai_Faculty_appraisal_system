from datetime import datetime
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PortableUUID


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("faculty_profiles.id"), nullable=False, index=True
    )
    timetable_entry_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("timetable_entries.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="present")
    attended_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
