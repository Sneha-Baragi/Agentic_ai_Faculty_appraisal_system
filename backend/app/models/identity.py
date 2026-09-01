import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PortableUUID

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", PortableUUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", PortableUUID(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")
    faculty_profile: Mapped["FacultyProfile | None"] = relationship(back_populates="user", uselist=False)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")


class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"
    __table_args__ = (UniqueConstraint("employee_code"),)

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    designation: Mapped[str] = mapped_column(String(120), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    joining_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidentiality_scope: Mapped[str] = mapped_column(String(50), default="self", nullable=False)

    user: Mapped[User] = relationship(back_populates="faculty_profile")
