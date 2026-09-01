import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.core.security import hash_password
from app.main import app
from app.models.base import Base
from app.models import (
    AppraisalCycle,
    FacultyProfile,
    Role,
    User,
)


def _sqlite_url() -> str:
    return "sqlite://"


@pytest.fixture(scope="session")
def engine():
    db_url = _sqlite_url()
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        db_url,
        connect_args=connect_args,
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in {"alembic_version"}:
                session.execute(table.delete())
        session.commit()
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def make_user(db: Session, email: str, role_names: list[str], password: str = "password-123") -> User:
    roles = []
    for rn in role_names:
        r = db.query(Role).filter(Role.name == rn).first()
        if not r:
            r = Role(name=rn)
            db.add(r)
            db.flush()
        roles.append(r)
    user = User(email=email, hashed_password=hash_password(password), is_active=True)
    for r in roles:
        user.roles.append(r)
    db.add(user)
    db.flush()
    return user


def make_faculty_profile(db: Session, user: User, employee_code: str | None = None) -> FacultyProfile:
    if employee_code is None:
        employee_code = f"F-{str(user.id)[:8]}"
    fp = FacultyProfile(
        user_id=user.id,
        employee_code=employee_code,
        department="CS",
        designation="Asst Prof",
        confidentiality_scope="self",
    )
    db.add(fp)
    db.flush()
    return fp


def make_cycle(db: Session, status: str = "open") -> AppraisalCycle:
    c = AppraisalCycle(
        name="2026-2027 Phase 2 Test",
        academic_year="2026-2027",
        status=status,
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 12, 31),
    )
    db.add(c)
    db.flush()
    return c


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str = "password-123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
