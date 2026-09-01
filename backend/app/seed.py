"""Idempotent Phase 1 seed: roles, demo users, DEMO rubric."""

from datetime import date

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import FacultyProfile, Role, Rubric, User
from app.scoring.engine import load_demo_rubric

ROLE_NAMES = ("faculty", "hod", "dean", "iqac", "committee", "admin")


def _get_or_create_role(db, name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        db.add(role)
        db.flush()
    return role


def _get_or_create_user(db, email: str, password: str, role: Role) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, hashed_password=hash_password(password), is_active=True)
        user.roles.append(role)
        db.add(user)
        db.flush()
    return user


def seed() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        roles = {name: _get_or_create_role(db, name) for name in ROLE_NAMES}

        admin = _get_or_create_user(
            db, settings.seed_admin_email, settings.seed_admin_password, roles["admin"]
        )
        faculty_user = _get_or_create_user(
            db, settings.seed_faculty_email, settings.seed_faculty_password, roles["faculty"]
        )
        _get_or_create_user(db, settings.seed_hod_email, settings.seed_hod_password, roles["hod"])

        dean_email = getattr(settings, "seed_dean_email", None) or "dean@demo.local"
        dean_password = getattr(settings, "seed_dean_password", None) or "dean-demo"
        _get_or_create_user(db, dean_email, dean_password, roles["dean"])

        iqac_email = getattr(settings, "seed_iqac_email", None) or "iqac@demo.local"
        iqac_password = getattr(settings, "seed_iqac_password", None) or "iqac-demo"
        _get_or_create_user(db, iqac_email, iqac_password, roles["iqac"])

        committee_email = getattr(settings, "seed_committee_email", None) or "committee@demo.local"
        committee_password = getattr(settings, "seed_committee_password", None) or "committee-demo"
        _get_or_create_user(db, committee_email, committee_password, roles["committee"])

        profile = db.scalar(select(FacultyProfile).where(FacultyProfile.user_id == faculty_user.id))
        if profile is None:
            db.add(
                FacultyProfile(
                    user_id=faculty_user.id,
                    employee_code="FAC-001",
                    department="Computer Science",
                    designation="Assistant Professor",
                    confidentiality_scope="self",
                )
            )

        existing = db.scalar(select(Rubric).where(Rubric.name == "DEMO/TEST Faculty Appraisal Rubric"))
        if existing is None:
            definition = load_demo_rubric()
            db.add(
                Rubric(
                    name=definition["name"],
                    version=str(definition["version"]),
                    is_demo=True,
                    effective_from=date(2026, 1, 1),
                    json_definition=definition,
                    created_by=admin.id,
                )
            )

        db.commit()
        print("Seed complete.")
        print(f"  admin:      {settings.seed_admin_email}")
        print(f"  faculty:    {settings.seed_faculty_email}")
        print(f"  hod:        {settings.seed_hod_email}")
        print(f"  dean:       {dean_email}")
        print(f"  iqac:       {iqac_email}")
        print(f"  committee:  {committee_email}")
        print("  rubric:     DEMO/TEST Faculty Appraisal Rubric (is_demo=true)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
