from datetime import datetime
import uuid

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PortableUUID


class TeachingRequirement(Base):
    __tablename__ = "teaching_requirements"

    role: Mapped[str] = mapped_column(String(50), primary_key=True)
    required_hours: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
