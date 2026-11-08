from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_faculty_profile
from app.models import AuditLog, FacultyProfile
from app.schemas.appraisal import ActivityCreate, ActivityUpdate
from app.services.activities import (
    ActivityError,
    activity_to_dict,
    create_activity,
    delete_activity,
    get_owned_activity,
    list_activities,
    update_activity,
)
from app.services.constants import ACTIVITY_TYPES

router = APIRouter(prefix="/api/v1/activities", tags=["activities"])


@router.get("/types")
def activity_types(_profile: FacultyProfile = Depends(get_faculty_profile)) -> dict:
    return ACTIVITY_TYPES


@router.get("")
def get_activities(
    category: str | None = None,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> list[dict]:
    return [activity_to_dict(item) for item in list_activities(db, faculty_id=profile.id, category=category)]


@router.post("", status_code=status.HTTP_201_CREATED)
def post_activity(
    body: ActivityCreate,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    try:
        activity = create_activity(
            db,
            faculty=profile,
            category=body.category,
            activity_type=body.activity_type,
            title=body.title,
            description=body.description,
            activity_date=body.date,
            extras=body.extras,
        )
        db.add(
            AuditLog(
                actor_id=profile.user_id,
                action="activity_created",
                entity_type="faculty_activity",
                entity_id=str(activity.id),
                before=None,
                after={
                    "category": activity.category,
                    "activity_type": activity.activity_type,
                    "title": activity.title,
                },
            )
        )
        db.commit()
        db.refresh(activity)
        return activity_to_dict(activity)
    except ActivityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{activity_id}")
def patch_activity(
    activity_id: str,
    body: ActivityUpdate,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    activity = get_owned_activity(db, activity_id=activity_id, faculty_id=profile.id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    before_snapshot = {
        "title": activity.title,
        "description": activity.description,
        "activity_type": activity.activity_type,
        "activity_date": activity.activity_date.isoformat() if activity.activity_date else None,
    }
    try:
        update_activity(
            db,
            activity=activity,
            title=body.title,
            description=body.description,
            activity_date=body.date,
            activity_type=body.activity_type,
            extras=body.extras,
        )
        after_snapshot = {
            "title": activity.title,
            "description": activity.description,
            "activity_type": activity.activity_type,
            "activity_date": activity.activity_date.isoformat() if activity.activity_date else None,
        }
        db.add(
            AuditLog(
                actor_id=profile.user_id,
                action="activity_updated",
                entity_type="faculty_activity",
                entity_id=str(activity.id),
                before=before_snapshot,
                after=after_snapshot,
            )
        )
        db.commit()
        db.refresh(activity)
        return activity_to_dict(activity)
    except ActivityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_activity(
    activity_id: str,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> Response:
    activity = get_owned_activity(db, activity_id=activity_id, faculty_id=profile.id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    before_snapshot = {
        "category": activity.category,
        "activity_type": activity.activity_type,
        "title": activity.title,
    }
    delete_activity(db, activity=activity)
    db.add(
        AuditLog(
            actor_id=profile.user_id,
            action="activity_deleted",
            entity_type="faculty_activity",
            entity_id=activity_id,
            before=before_snapshot,
            after=None,
        )
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
