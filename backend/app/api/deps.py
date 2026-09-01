import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import FacultyProfile, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = payload.get("sub")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = db.scalar(
        select(User)
        .options(selectinload(User.roles), selectinload(User.faculty_profile))
        .where(User.id == user_uuid)
    )
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*names: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        owned = {role.name for role in user.roles}
        if owned.isdisjoint(set(names)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _dep


def get_faculty_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FacultyProfile:
    profile = user.faculty_profile or db.scalar(
        select(FacultyProfile).where(FacultyProfile.user_id == user.id)
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Faculty profile required")
    return profile

