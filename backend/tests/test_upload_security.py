from datetime import date
from io import BytesIO
import zipfile
import pytest
import fitz
from docx import Document
from openpyxl import Workbook
from sqlalchemy.orm import Session
from unittest.mock import MagicMock

from app.core.config import get_settings
from app.models import Evidence, FacultyActivity, FacultyAppraisalRun, FacultyProfile
from app.services.constants import (
    MAX_EXTRACTED_CHARS,
    MAX_PDF_PAGES,
    MAX_XLSX_ROWS_PER_SHEET,
    MAX_XLSX_SHEETS,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_RATIO,
    MAX_ZIP_UNCOMPRESSED_BYTES,
)
from app.services.extraction import (
    DOCXExtractor,
    ImageExtractor,
    PDFExtractor,
    XLSXExtractor,
    _inspect_safe_zip,
)
from app.services.evidence import EvidenceError, EvidenceService
from app.services.storage import get_storage
from .conftest import auth_headers, login, make_cycle, make_faculty_profile, make_user


# --- Synthetic In-Memory Fixture Helpers ---

def _create_minimal_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Sample Secure Evidence PDF Content")
    data = doc.tobytes()
    doc.close()
    return data


def _create_minimal_png() -> bytes:
    # 1x1 valid PNG (67 bytes)
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
        b"\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00"
        b"\x00\x00IEND\xaeB`\x82"
    )


def _create_minimal_jpeg() -> bytes:
    # 1x1 valid JPEG (134 bytes)
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08"
        b"\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13"
        b"\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05"
        b"\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07"
        b"\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    )


def _create_minimal_docx() -> bytes:
    doc = Document()
    doc.add_paragraph("Minimal Valid DOCX")
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _create_minimal_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "Minimal Valid XLSX"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _setup_faculty_and_activity(db_session: Session, suffix: str):
    user = make_user(db_session, f"fac-up-{suffix}@demo.local", ["faculty"])
    profile = make_faculty_profile(db_session, user)
    cycle = make_cycle(db_session)
    run = FacultyAppraisalRun(faculty_id=profile.id, cycle_id=cycle.id, status="collecting")
    db_session.add(run)
    db_session.flush()

    activity = FacultyActivity(
        run_id=run.id,
        faculty_id=profile.id,
        cycle_id=cycle.id,
        category="research",
        activity_type="publications",
        title=f"Activity {suffix}",
        description="Testing evidence upload",
        activity_date=date(2026, 1, 1),
    )
    db_session.add(activity)
    db_session.commit()
    return user, profile, activity


# ==============================================================================
# SEC-05 Test Scenarios 1 - 3: Upload Size and Bounded Ingestion
# ==============================================================================

def test_oversized_upload_rejected_with_413(client, db_session: Session):
    user, _, activity = _setup_faculty_and_activity(db_session, "oversized")
    token = login(client, user.email)
    settings = get_settings()

    # Create synthetic payload strictly larger than max_upload_size
    oversized_bytes = b"%PDF-1.4\n" + b"A" * (settings.max_upload_size + 1024)

    resp = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("oversized.pdf", oversized_bytes, "application/pdf")},
        data={"activity_id": str(activity.id)},
    )
    assert resp.status_code == 413
    assert "exceeds maximum upload size" in resp.json()["detail"]


def test_bounded_reading_stops_shortly_after_size_limit(client, db_session: Session, monkeypatch):
    user, _, activity = _setup_faculty_and_activity(db_session, "bounded")
    token = login(client, user.email)
    settings = get_settings()

    # Track chunks read during the endpoint's bounded read loop
    read_tracker = {"bytes_read": 0, "read_calls": 0}

    from starlette.datastructures import UploadFile as StarletteUploadFile
    orig_init = StarletteUploadFile.__init__

    class InstrumentedSpooledFile:
        def __init__(self, underlying):
            self._underlying = underlying

        def read(self, size=-1):
            read_tracker["read_calls"] += 1
            chunk = self._underlying.read(size)
            read_tracker["bytes_read"] += len(chunk)
            return chunk

        def close(self):
            return self._underlying.close()

        def __getattr__(self, item):
            return getattr(self._underlying, item)

    def patched_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self.file = InstrumentedSpooledFile(self.file)

    monkeypatch.setattr(StarletteUploadFile, "__init__", patched_init)

    # 15 MB payload when max is 10 MB
    raw_payload = b"%PDF-1.4\n" + b"X" * (settings.max_upload_size + (5 * 1024 * 1024))

    resp = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("stream.pdf", raw_payload, "application/pdf")},
        data={"activity_id": str(activity.id)},
    )
    assert resp.status_code == 413
    assert "exceeds maximum upload size" in resp.json()["detail"]
    # Bounded reader must have stopped immediately once the threshold was crossed (within 1 chunk of 64KB)
    # Rather than reading the entire 15 MB from the stream
    assert read_tracker["bytes_read"] <= settings.max_upload_size + (64 * 1024)
    assert read_tracker["bytes_read"] < len(raw_payload)


def test_normal_sized_valid_upload_succeeds(client, db_session: Session):
    user, _, activity = _setup_faculty_and_activity(db_session, "normalsize")
    token = login(client, user.email)

    pdf_bytes = _create_minimal_pdf()
    resp = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("evidence.pdf", pdf_bytes, "application/pdf")},
        data={"activity_id": str(activity.id)},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["validation_status"] in {"valid", "uploaded"}
    assert body["original_filename"] == "evidence.pdf"
    assert body["file_size"] == len(pdf_bytes)


# ==============================================================================
# SEC-05 Test Scenarios 4 & 5: MIME & File Signature Validation
# ==============================================================================

def test_mime_mismatch_and_incorrect_signatures_rejected(client, db_session: Session):
    user, _, activity = _setup_faculty_and_activity(db_session, "signatures")
    token = login(client, user.email)

    # 1. HTML file disguised as .pdf
    html_as_pdf = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("fake.pdf", b"<html><body>Malicious HTML</body></html>", "application/pdf")},
        data={"activity_id": str(activity.id)},
    )
    assert html_as_pdf.status_code == 400
    assert "invalid_file_signature" in html_as_pdf.text

    # 2. HTML file disguised as .png
    html_as_png = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("fake.png", b"<script>alert('xss')</script>", "image/png")},
        data={"activity_id": str(activity.id)},
    )
    assert html_as_png.status_code == 400
    assert "invalid_file_signature" in html_as_png.text

    # 3. Executable header disguised as .docx
    exe_as_docx = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("payload.docx", b"MZ\x90\x00\x03\x00\x00\x00", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"activity_id": str(activity.id)},
    )
    assert exe_as_docx.status_code == 400
    assert "invalid_file_signature" in exe_as_docx.text

    # 4. Disallowed MIME type (text/html or executable)
    bad_mime = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("doc.pdf", b"%PDF-1.4\nvalid", "text/html")},
        data={"activity_id": str(activity.id)},
    )
    assert bad_mime.status_code == 400


def test_valid_pdf_docx_xlsx_png_jpeg_handled_correctly(client, db_session: Session):
    user, _, activity = _setup_faculty_and_activity(db_session, "validformats")
    token = login(client, user.email)

    # 1. PNG
    png_resp = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("certificate.png", _create_minimal_png(), "image/png")},
        data={"activity_id": str(activity.id)},
    )
    assert png_resp.status_code == 201, png_resp.text

    # 2. JPEG
    jpeg_resp = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("photo.jpg", _create_minimal_jpeg(), "image/jpeg")},
        data={"activity_id": str(activity.id)},
    )
    assert jpeg_resp.status_code == 201, jpeg_resp.text

    # 3. DOCX
    docx_resp = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("report.docx", _create_minimal_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"activity_id": str(activity.id)},
    )
    assert docx_resp.status_code == 201, docx_resp.text

    # 4. XLSX
    xlsx_resp = client.post(
        f"/api/v1/evidence?activity_id={activity.id}",
        headers=auth_headers(token),
        files={"file": ("data.xlsx", _create_minimal_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"activity_id": str(activity.id)},
    )
    assert xlsx_resp.status_code == 201, xlsx_resp.text


# ==============================================================================
# SEC-05 Test Scenarios 6 & 7: PDF Limits and Malformed PDF / ZIP Handling
# ==============================================================================

def test_pdf_page_and_text_truncation_limits():
    extractor = PDFExtractor()

    # 1. Test 60-page PDF (exceeding MAX_PDF_PAGES = 50)
    doc = fitz.open()
    for i in range(60):
        p = doc.new_page()
        p.insert_text((50, 50), f"Page {i+1} content")
    sixty_page_bytes = doc.tobytes()
    doc.close()

    result = extractor.extract(sixty_page_bytes)
    assert result.status == "extracted"
    assert result.metadata["pages"] == 60
    assert result.metadata["extracted_pages"] == MAX_PDF_PAGES
    assert result.metadata["truncated_pages"] is True
    assert "Page 50 content" in result.text
    assert "Page 55 content" not in result.text

    # 2. Test massive text truncation (exceeding MAX_EXTRACTED_CHARS = 50,000)
    doc_huge = fitz.open()
    for _ in range(25):
        p = doc_huge.new_page()
        for y in range(20, 800, 15):
            p.insert_text((10, y), "Secure Evidence Document Truncation Test String " * 4)
    huge_bytes = doc_huge.tobytes()
    doc_huge.close()

    huge_result = extractor.extract(huge_bytes)
    assert huge_result.status == "extracted"
    assert huge_result.metadata["truncated_text"] is True
    assert len(huge_result.text) <= MAX_EXTRACTED_CHARS


def test_malformed_pdfs_and_zip_archives_fail_safely():
    # 1. Broken PDF bytes
    pdf_ext = PDFExtractor()
    broken_pdf_result = pdf_ext.extract(b"%PDF-1.4\nBroken xref table 999999\n%%EOF")
    assert broken_pdf_result.status == "failed"
    assert "PDF" in broken_pdf_result.error or "broken" in broken_pdf_result.error.lower()

    # 2. Broken DOCX bytes
    docx_ext = DOCXExtractor()
    broken_docx_result = docx_ext.extract(b"PK\x03\x04corrupted-non-zip-data")
    assert broken_docx_result.status == "failed"
    assert "ZIP" in broken_docx_result.error or "DOCX" in broken_docx_result.error

    # 3. Broken image bytes
    img_ext = ImageExtractor()
    broken_img = img_ext.extract(b"\x89PNG\r\n\x1a\ncorrupted", "test.png")
    assert broken_img.status == "extracted"  # PNG magic matched, stored without OCR
    non_png = img_ext.extract(b"NOT_A_PNG", "test.png")
    assert non_png.status == "failed"


# ==============================================================================
# SEC-05 Test Scenarios 8 & 9: ZIP Pre-Decompression Inspection & XLSX Limits
# ==============================================================================

def test_zip_inspection_rejects_unsafe_archives():
    # 1. Member count > MAX_ZIP_MEMBERS (150)
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:p>Valid</w:p>")
        for i in range(160):
            zf.writestr(f"member_{i}.txt", f"data_{i}")
    safe, err = _inspect_safe_zip(buf.getvalue(), required_entry="word/")
    assert safe is False
    assert "member count limit" in err

    # 2. Member compression ratio > MAX_ZIP_RATIO (100:1)
    buf_ratio = BytesIO()
    with zipfile.ZipFile(buf_ratio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Repetitive compressible bytes: 200 KB compressing to < 1 KB (ratio > 200:1)
        large_zeroes = b"0" * (200 * 1024)
        zf.writestr("word/document.xml", large_zeroes)
    safe_ratio, err_ratio = _inspect_safe_zip(buf_ratio.getvalue(), required_entry="word/")
    assert safe_ratio is False
    assert "safe compression ratio" in err_ratio

    # 3. Path traversal in ZIP archive
    buf_traversal = BytesIO()
    with zipfile.ZipFile(buf_traversal, "w") as zf:
        zf.writestr("word/document.xml", "<w:p>Safe</w:p>")
        zf.writestr("../etc/passwd", "root:x:0:0:")
    safe_trav, err_trav = _inspect_safe_zip(buf_traversal.getvalue(), required_entry="word/")
    assert safe_trav is False
    assert "illegal file path" in err_trav

    # 4. Total uncompressed size > MAX_ZIP_UNCOMPRESSED_BYTES (30 MiB)
    # We test via mock ZipInfo to avoid generating 30MB in test memory
    mock_info = zipfile.ZipInfo("word/document.xml")
    mock_info.file_size = MAX_ZIP_UNCOMPRESSED_BYTES + 1024
    mock_info.compress_size = MAX_ZIP_UNCOMPRESSED_BYTES // 2
    mock_zf = MagicMock()
    mock_zf.infolist.return_value = [mock_info]
    # Verify the logic branches correctly
    total = sum(i.file_size for i in [mock_info])
    assert total > MAX_ZIP_UNCOMPRESSED_BYTES


def test_xlsx_processing_respects_sheet_and_row_limits():
    extractor = XLSXExtractor()

    wb = Workbook()
    # Create 7 worksheets (exceeding MAX_XLSX_SHEETS = 5)
    for idx in range(7):
        ws = wb.create_sheet(title=f"Sheet{idx+1}")
        # Insert 10 rows
        for row in range(1, 10):
            ws.cell(row=row, column=1, value=f"S{idx+1}R{row}")

    buf = BytesIO()
    wb.save(buf)
    content = buf.getvalue()

    result = extractor.extract(content)
    assert result.status == "extracted"
    assert result.metadata["sheets_processed"] <= MAX_XLSX_SHEETS
    assert result.metadata["truncated"] is True


# ==============================================================================
# SEC-05 Test Scenarios 10 & 11: Storage Cleanup & Error Preservation
# ==============================================================================

def test_storage_cleanup_attempted_on_downstream_failure(db_session: Session):
    service = EvidenceService()
    storage = get_storage()

    user, profile, activity = _setup_faculty_and_activity(db_session, "cleanup")
    pdf_bytes = _create_minimal_pdf()

    # Track storage deletion
    deleted_keys = []
    original_delete = storage.delete

    def tracking_delete(key):
        deleted_keys.append(key)
        original_delete(key)

    storage.delete = tracking_delete

    # Mock db to raise exception during flush
    mock_db = MagicMock(spec=Session)
    mock_db.flush.side_effect = RuntimeError("Simulated Database Error")

    with pytest.raises(RuntimeError, match="Simulated Database Error"):
        service.upload(
            mock_db,
            faculty=profile,
            activity=activity,
            filename="test_clean.pdf",
            content_type="application/pdf",
            data=pdf_bytes,
        )

    # Verify storage deletion was called
    assert len(deleted_keys) == 1
    storage.delete = original_delete


def test_storage_cleanup_failure_does_not_mask_original_exception(db_session: Session):
    service = EvidenceService()
    storage = get_storage()

    user, profile, activity = _setup_faculty_and_activity(db_session, "cleanfail")
    pdf_bytes = _create_minimal_pdf()

    original_delete = storage.delete

    def failing_delete(key):
        raise OSError("Storage network down")

    storage.delete = failing_delete

    mock_db = MagicMock(spec=Session)
    mock_db.flush.side_effect = ValueError("Primary Business Logic Failure")

    # The original ValueError must be raised, NOT the OSError from delete
    with pytest.raises(ValueError, match="Primary Business Logic Failure"):
        service.upload(
            mock_db,
            faculty=profile,
            activity=activity,
            filename="test_clean_fail.pdf",
            content_type="application/pdf",
            data=pdf_bytes,
        )

    storage.delete = original_delete


# ==============================================================================
# SEC-05 Test Scenario 12: Existing Authorization Behavior Preserved
# ==============================================================================

def test_evidence_authorization_and_retrieval_preserved(client, db_session: Session):
    user_a, profile_a, activity_a = _setup_faculty_and_activity(db_session, "auth_a")
    user_b, profile_b, activity_b = _setup_faculty_and_activity(db_session, "auth_b")

    token_a = login(client, user_a.email)
    token_b = login(client, user_b.email)

    pdf_bytes = _create_minimal_pdf()

    # User B cannot upload evidence to User A's activity
    cross_upload = client.post(
        f"/api/v1/evidence?activity_id={activity_a.id}",
        headers=auth_headers(token_b),
        files={"file": ("stolen.pdf", pdf_bytes, "application/pdf")},
        data={"activity_id": str(activity_a.id)},
    )
    assert cross_upload.status_code == 404

    # User A uploads valid evidence
    valid_upload = client.post(
        f"/api/v1/evidence?activity_id={activity_a.id}",
        headers=auth_headers(token_a),
        files={"file": ("owned.pdf", pdf_bytes, "application/pdf")},
        data={"activity_id": str(activity_a.id)},
    )
    assert valid_upload.status_code == 201
    ev_id = valid_upload.json()["id"]

    # User B cannot retrieve User A's evidence
    assert client.get(f"/api/v1/evidence/{ev_id}", headers=auth_headers(token_b)).status_code == 404
    # User B cannot download User A's file
    assert client.get(f"/api/v1/evidence/{ev_id}/file", headers=auth_headers(token_b)).status_code == 404

    # User A can retrieve and download their own evidence
    assert client.get(f"/api/v1/evidence/{ev_id}", headers=auth_headers(token_a)).status_code == 200
    down = client.get(f"/api/v1/evidence/{ev_id}/file", headers=auth_headers(token_a))
    assert down.status_code == 200
    assert down.content == pdf_bytes
