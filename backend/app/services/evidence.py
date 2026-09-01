from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Evidence, EvidenceExtraction, EvidenceValidation, FacultyActivity, FacultyProfile
from app.services.cycles import get_open_cycle
from app.services.extraction import DocumentExtractor
from app.services.storage import get_storage, object_key_for
from app.services.validation import EvidenceValidationService, ValidationOutcome


class EvidenceError(ValueError):
    pass


class EvidenceService:
    def __init__(self) -> None:
        self.storage = get_storage()
        self.validator = EvidenceValidationService()
        self.extractor = DocumentExtractor()

    def precheck(self, *, filename: str, content_type: str | None, size: int) -> ValidationOutcome:
        return self.validator.validate_upload_candidate(
            filename=filename, content_type=content_type, size=size
        )

    def upload(
        self,
        db: Session,
        *,
        faculty: FacultyProfile,
        activity: FacultyActivity,
        filename: str,
        content_type: str | None,
        data: bytes,
    ) -> Evidence:
        pre = self.precheck(filename=filename, content_type=content_type, size=len(data))
        if not pre.ok:
            raise EvidenceError("; ".join(pre.reasons))
        cycle = get_open_cycle(db)
        if cycle is None:
            raise EvidenceError("No open appraisal cycle")
        evidence_id = uuid.uuid4()
        key = object_key_for(
            faculty_id=str(faculty.id),
            cycle_id=str(activity.cycle_id or cycle.id),
            activity_id=str(activity.id),
            evidence_id=str(evidence_id),
            filename=filename,
        )
        checksum = hashlib.sha256(data).hexdigest()
        self.storage.put(key, data, content_type or "application/octet-stream")
        kind = Path(filename).suffix.lower().lstrip(".") or "bin"
        evidence = Evidence(
            id=evidence_id,
            activity_id=activity.id,
            faculty_id=faculty.id,
            cycle_id=activity.cycle_id or cycle.id,
            storage_key=key,
            mime=content_type or "application/octet-stream",
            checksum_sha256=checksum,
            kind=kind,
            original_filename=filename,
            file_size=len(data),
            validation_status="uploaded",
            extraction_status="pending",
        )
        db.add(evidence)
        db.flush()
        self.validate_and_extract(db, evidence=evidence, faculty=faculty, activity=activity, data=data)
        return evidence

    def validate_and_extract(
        self,
        db: Session,
        *,
        evidence: Evidence,
        faculty: FacultyProfile,
        activity: FacultyActivity,
        data: bytes | None = None,
    ) -> Evidence:
        evidence.validation_status = "validating"
        db.flush()
        cycle = get_open_cycle(db)
        outcome = self.validator.validate_stored(
            storage=self.storage,
            object_key=evidence.storage_key,
            filename=evidence.original_filename or "file.bin",
            content_type=evidence.mime,
            size=evidence.file_size or 0,
            checksum=evidence.checksum_sha256,
            activity_faculty_id=activity.faculty_id,
            authenticated_faculty_id=faculty.id,
            cycle_status=cycle.status if cycle else None,
        )
        db.add(
            EvidenceValidation(
                evidence_id=evidence.id,
                activity_id=activity.id,
                verdict="supported" if outcome.ok else "insufficient",
                confidence=1.0 if outcome.ok else 0.0,
                reasons={"checks": outcome.reasons},
            )
        )
        if not outcome.ok:
            evidence.validation_status = "invalid"
            evidence.extraction_status = "skipped"
            return evidence
        evidence.validation_status = "valid"
        evidence.extraction_status = "extracting"
        db.flush()
        payload = data if data is not None else self.storage.get(evidence.storage_key)
        result = self.extractor.extract(payload, evidence.original_filename or "file.bin", evidence.mime)
        evidence.extraction_status = result.status
        db.add(
            EvidenceExtraction(
                evidence_id=evidence.id,
                extracted_text=result.text,
                extraction_status=result.status,
                extraction_error=result.error,
                extracted_at=datetime.now(timezone.utc),
                extra_metadata=result.metadata,
            )
        )
        return evidence

    def get_owned(self, db: Session, *, evidence_id, faculty_id) -> Evidence | None:
        return db.scalar(
            select(Evidence).where(Evidence.id == evidence_id, Evidence.faculty_id == faculty_id)
        )

    def read_bytes(self, evidence: Evidence) -> bytes:
        if not evidence.storage_key:
            raise EvidenceError("No stored object")
        return self.storage.get(evidence.storage_key)


def evidence_to_dict(evidence: Evidence) -> dict:
    return {
        "id": str(evidence.id),
        "faculty_id": str(evidence.faculty_id),
        "activity_id": str(evidence.activity_id),
        "appraisal_cycle_id": str(evidence.cycle_id) if evidence.cycle_id else None,
        "original_filename": evidence.original_filename,
        "object_key": evidence.storage_key,
        "content_type": evidence.mime,
        "file_size": evidence.file_size,
        "upload_timestamp": evidence.uploaded_at.isoformat() if evidence.uploaded_at else None,
        "checksum": evidence.checksum_sha256,
        "validation_status": evidence.validation_status,
        "extraction_status": evidence.extraction_status,
        "kind": evidence.kind,
    }
