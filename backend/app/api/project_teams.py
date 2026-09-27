from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_faculty_profile
from app.models import FacultyProfile, User
from app.schemas.phase2 import (
    ProjectTeamCreate,
    ProjectTeamMemberSchema,
    ProjectTeamOut,
    ProjectTeamUpdate,
    ResearchPaperRequirementOut,
)
from app.services.project_teams import (
    create_project_team,
    delete_project_team,
    list_project_teams,
    update_project_team,
)
from app.services.research_papers import get_research_paper_status

router = APIRouter(tags=["project-teams"])


def _out(team) -> ProjectTeamOut:
    members = [
        ProjectTeamMemberSchema(id=str(m.id), name=m.name, email=m.email)
        for m in (team.members or [])
    ]
    return ProjectTeamOut(
        id=str(team.id),
        faculty_id=str(team.faculty_id),
        title=team.title,
        status=team.status,
        members=members,
        created_at=team.created_at,
    )


@router.get("/api/v1/project-teams/me", response_model=List[ProjectTeamOut])
@router.get("/api/project-teams/me", response_model=List[ProjectTeamOut])
@router.get("/api/v1/project-teams", response_model=List[ProjectTeamOut])
@router.get("/api/project-teams", response_model=List[ProjectTeamOut])
def read_project_teams(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> List[ProjectTeamOut]:
    teams = list_project_teams(db, profile.id)
    return [_out(t) for t in teams]


@router.post("/api/v1/project-teams", response_model=ProjectTeamOut, status_code=status.HTTP_201_CREATED)
@router.post("/api/project-teams", response_model=ProjectTeamOut, status_code=status.HTTP_201_CREATED)
def add_project_team(
    data: ProjectTeamCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> ProjectTeamOut:
    team = create_project_team(db, profile.id, data)
    return _out(team)


@router.put("/api/v1/project-teams/{team_id}", response_model=ProjectTeamOut)
@router.put("/api/project-teams/{team_id}", response_model=ProjectTeamOut)
def edit_project_team(
    team_id: UUID,
    data: ProjectTeamUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> ProjectTeamOut:
    team = update_project_team(db, profile.id, team_id, data)
    return _out(team)


@router.delete("/api/v1/project-teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/api/project-teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_team(
    team_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
):
    delete_project_team(db, profile.id, team_id)
    return None


@router.get("/api/v1/research-papers/me", response_model=ResearchPaperRequirementOut)
@router.get("/api/research-papers/me", response_model=ResearchPaperRequirementOut)
def read_research_paper_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> ResearchPaperRequirementOut:
    status_data = get_research_paper_status(db, profile.id)
    return ResearchPaperRequirementOut(**status_data)
