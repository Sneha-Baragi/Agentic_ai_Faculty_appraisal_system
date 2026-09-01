from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import get_settings
from app.services.constants import ALLOWED_EXTENSIONS, ALLOWED_MIME_PREFIXES
from app.services.storage import ObjectStorage


@dataclass
class ValidationOutcome:
    ok: bool
    status: str
    reasons: list[str] = field(default_factory=list)


class EvidenceValidationService:
    """Deterministic Phase 2 checks. LLM-based validation can wrap this later."""

    def validate_upload_candidate(self, *, filename: str, content_type: str | None, size: int) -> ValidationOutcome:
        settings = get_settings()
        reasons: list[str] = []
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            reasons.append(f"unsupported_file_type:{suffix or 'none'}")
        if content_type and content_type.split(";")[0].strip() not in ALLOWED_MIME_PREFIXES and suffix not in ALLOWED_EXTENSIONS:
            reasons.append(f"unsupported_mime:{content_type}")
        if size <= 0:
            reasons.append("empty_file")
        if size > settings.max_upload_size:
            reasons.append("file_too_large")
        if reasons:
            return ValidationOutcome(ok=False, status="invalid", reasons=reasons)
        return ValidationOutcome(ok=True, status="valid", reasons=[])

    def validate_stored(
        self,
        *,
        storage: ObjectStorage,
        object_key: str | None,
        filename: str,
        content_type: str | None,
        size: int,
        checksum: str | None,
        activity_faculty_id,
        authenticated_faculty_id,
        cycle_status: str | None,
    ) -> ValidationOutcome:
        candidate = self.validate_upload_candidate(filename=filename, content_type=content_type, size=size)
        reasons = list(candidate.reasons)
        if not object_key:
            reasons.append("missing_object_key")
        elif not storage.exists(object_key):
            reasons.append("object_missing_in_storage")
        if not checksum:
            reasons.append("missing_checksum")
        if activity_faculty_id != authenticated_faculty_id:
            reasons.append("activity_ownership_mismatch")
        if cycle_status not in {"open", "under_review"}:
            reasons.append(f"invalid_cycle_status:{cycle_status}")
        if reasons:
            return ValidationOutcome(ok=False, status="invalid", reasons=reasons)
        return ValidationOutcome(ok=True, status="valid", reasons=["file_exists", "type_ok", "size_ok", "checksum_ok", "owned"])
