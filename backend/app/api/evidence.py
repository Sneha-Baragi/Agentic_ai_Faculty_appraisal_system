from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_faculty_profile
from app.core.config import get_settings
from app.models import AuditLog, Evidence, FacultyActivity, FacultyProfile
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

    settings = get_settings()
    max_size = settings.max_upload_size

    # Fast-reject if Content-Length or known file size exceeds limit
    content_length_header = file.headers.get("content-length") if file.headers else None
    if content_length_header:
        try:
            if int(content_length_header) > max_size:
                file.file.close()
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum upload size of {max_size} bytes",
                )
        except ValueError:
            pass

    if getattr(file, "size", None) is not None and file.size > max_size:
        file.file.close()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {max_size} bytes",
        )

    # Read in bounded chunks to prevent buffering massive uploads into RAM
    chunk_size = 64 * 1024
    buffer = bytearray()
    try:
        while True:
            chunk = file.file.read(chunk_size)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum upload size of {max_size} bytes",
                )
        data = bytes(buffer)
    finally:
        file.file.close()

    try:
        evidence = _service().upload(
            db,
            faculty=profile,
            activity=activity,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            data=data,
        )
        db.add(
            AuditLog(
                actor_id=profile.user_id,
                action="evidence_uploaded",
                entity_type="evidence",
                entity_id=str(evidence.id),
                before=None,
                after={
                    "activity_id": str(activity.id),
                    "filename": evidence.original_filename,
                    "file_size": evidence.file_size,
                    "mime": evidence.mime,
                    "validation_status": evidence.validation_status,
                },
            )
        )
        db.commit()
        db.refresh(evidence)
        return evidence_to_dict(evidence)
    except HTTPException:
        raise
    except EvidenceError as exc:
        db.rollback()
        msg = str(exc)
        if "file_too_large" in msg:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum upload size of {max_size} bytes",
            ) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence processing failed: {exc}",
        ) from exc



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
