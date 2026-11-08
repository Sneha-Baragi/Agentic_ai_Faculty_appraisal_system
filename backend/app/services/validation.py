from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import get_settings
from app.services.constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_BY_EXT,
    ALLOWED_MIME_PREFIXES,
    DISALLOWED_MIME_TYPES,
)
from app.services.storage import ObjectStorage


@dataclass
class ValidationOutcome:
    ok: bool
    status: str
    reasons: list[str] = field(default_factory=list)


class EvidenceValidationService:
    """Deterministic Phase 2 checks. LLM-based validation can wrap this later."""

    def validate_upload_candidate(
        self,
        *,
        filename: str,
        content_type: str | None,
        size: int,
        data: bytes | None = None,
    ) -> ValidationOutcome:
        settings = get_settings()
        reasons: list[str] = []
        suffix = Path(filename).suffix.lower()

        if suffix not in ALLOWED_EXTENSIONS:
            reasons.append(f"unsupported_file_type:{suffix or 'none'}")

        if content_type:
            mime_clean = content_type.split(";")[0].strip().lower()
            if mime_clean in DISALLOWED_MIME_TYPES:
                reasons.append(f"disallowed_mime:{mime_clean}")
            elif suffix in ALLOWED_MIME_BY_EXT:
                if mime_clean not in ALLOWED_MIME_BY_EXT[suffix]:
                    reasons.append(f"unsupported_mime:{content_type}")
            elif mime_clean not in ALLOWED_MIME_PREFIXES:
                reasons.append(f"unsupported_mime:{content_type}")

        if size <= 0:
            reasons.append("empty_file")
        if size > settings.max_upload_size:
            reasons.append("file_too_large")

        if data is not None and len(data) > 0:
            header_sample = data[:1024].lower()
            if header_sample.startswith(b"mz") or header_sample.startswith(b"\x7felf"):
                reasons.append("invalid_file_signature:executable")
            elif (
                b"<html" in header_sample
                or b"<!doctype html" in header_sample
                or b"<script" in header_sample
                or b"<?php" in header_sample
            ):
                reasons.append("invalid_file_signature:html_or_script")
            elif suffix == ".pdf":
                if not (data.startswith(b"%PDF") or b"%pdf-" in header_sample):
                    reasons.append("invalid_file_signature:not_a_pdf")
            elif suffix == ".png":
                if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    reasons.append("invalid_file_signature:not_a_png")
            elif suffix in {".jpg", ".jpeg"}:
                if not data.startswith(b"\xff\xd8\xff"):
                    reasons.append("invalid_file_signature:not_a_jpeg")
            elif suffix in {".docx", ".xlsx"}:
                if not data.startswith(b"PK\x03\x04"):
                    reasons.append("invalid_file_signature:not_a_zip")

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
        data: bytes | None = None,
    ) -> ValidationOutcome:
        candidate = self.validate_upload_candidate(
            filename=filename, content_type=content_type, size=size, data=data
        )
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
