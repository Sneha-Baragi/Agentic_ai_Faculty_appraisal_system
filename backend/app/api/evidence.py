from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_faculty_profile
from app.models import Evidence, FacultyActivity, FacultyProfile
from app.services.activities import get_owned_activity
from app.services.evidence import EvidenceError, EvidenceService, evidence_to_dict

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


def _service() -> EvidenceService:
    return EvidenceService()


@router.get("")
def list_evidence(
    activity_id: str | None = None,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> list[dict]:
    stmt = select(Evidence).where(Evidence.faculty_id == profile.id)
    if activity_id:
        stmt = stmt.where(Evidence.activity_id == activity_id)
    rows = list(db.scalars(stmt.order_by(Evidence.uploaded_at.desc())))
    return [evidence_to_dict(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_evidence(
    activity_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    activity = get_owned_activity(db, activity_id=activity_id, faculty_id=profile.id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    data = file.file.read()
    try:
        evidence = _service().upload(
            db,
            faculty=profile,
            activity=activity,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            data=data,
        )
        db.commit()
        db.refresh(evidence)
        return evidence_to_dict(evidence)
    except EvidenceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{evidence_id}")
def get_evidence(
    evidence_id: str,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> dict:
    row = _service().get_owned(db, evidence_id=evidence_id, faculty_id=profile.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return evidence_to_dict(row)


@router.get("/{evidence_id}/file")
def download_evidence(
    evidence_id: str,
    db: Session = Depends(get_db),
    profile: FacultyProfile = Depends(get_faculty_profile),
) -> Response:
    row = _service().get_owned(db, evidence_id=evidence_id, faculty_id=profile.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    payload = _service().read_bytes(row)
    return Response(
        content=payload,
        media_type=row.mime or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{row.original_filename or "evidence"}"'},
    )
