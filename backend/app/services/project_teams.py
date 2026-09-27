from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project_teams import ProjectTeam, ProjectTeamMember
from app.schemas.phase2 import ProjectTeamCreate, ProjectTeamUpdate, ProjectTeamMemberSchema


def list_project_teams(db: Session, faculty_id: UUID) -> List[ProjectTeam]:
    return db.scalars(
        select(ProjectTeam)
        .where(ProjectTeam.faculty_id == faculty_id)
        .order_by(ProjectTeam.created_at.desc())
    ).all()


def create_project_team(
    db: Session, faculty_id: UUID, data: ProjectTeamCreate
) -> ProjectTeam:
    team = ProjectTeam(
        faculty_id=faculty_id,
        title=data.title.strip(),
        status=data.status,
    )
    db.add(team)
    db.flush()

    for m in data.members:
        member = ProjectTeamMember(
            team_id=team.id,
            name=m.name.strip(),
            email=m.email.strip() if (m.email and m.email.strip()) else "",
        )
        db.add(member)

    db.commit()
    db.refresh(team)
    return team


def update_project_team(
    db: Session, faculty_id: UUID, team_id: UUID, data: ProjectTeamUpdate
) -> ProjectTeam:
    team = db.get(ProjectTeam, team_id)
    if team is None or team.faculty_id != faculty_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project team not found",
        )

    if data.title is not None:
        team.title = data.title.strip()
    if data.status is not None:
        team.status = data.status

    if data.members is not None:
        # replace members
        for existing in list(team.members):
            db.delete(existing)
        db.flush()
        for m in data.members:
            member = ProjectTeamMember(
                team_id=team.id,
                name=m.name.strip(),
                email=m.email.strip() if (m.email and m.email.strip()) else "",
            )
            db.add(member)

    db.commit()
    db.refresh(team)
    return team


def delete_project_team(db: Session, faculty_id: UUID, team_id: UUID) -> None:
    team = db.get(ProjectTeam, team_id)
    if team is None or team.faculty_id != faculty_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project team not found",
        )
    db.delete(team)
    db.commit()
