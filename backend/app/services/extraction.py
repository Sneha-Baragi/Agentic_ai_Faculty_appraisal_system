from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import fitz
from docx import Document
from openpyxl import load_workbook

from app.services.constants import (
    MAX_EXTRACTED_CHARS,
    MAX_PDF_PAGES,
    MAX_XLSX_ROWS_PER_SHEET,
    MAX_XLSX_SHEETS,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_RATIO,
    MAX_ZIP_UNCOMPRESSED_BYTES,
)


@dataclass
class ExtractionResult:
    text: str
    status: str
    error: str | None = None
    metadata: dict = field(default_factory=dict)


def _inspect_safe_zip(content: bytes, required_entry: str | None = None) -> tuple[bool, str | None]:
    """Inspects a ZIP/OpenXML archive in-memory before decompression.

    Guards against decompression bombs, excessive uncompressed size, too many
    members, and directory traversal.
    """
    try:
        with zipfile.ZipFile(BytesIO(content)) as zf:
            infolist = zf.infolist()
            if len(infolist) > MAX_ZIP_MEMBERS:
                return False, f"Archive exceeds member count limit ({len(infolist)} > {MAX_ZIP_MEMBERS})"

            total_uncompressed = 0
            has_required_entry = False if required_entry else True

            for info in infolist:
                # Path traversal guard
                if ".." in info.filename or info.filename.startswith(("/", "\\")):
                    return False, f"Archive contains illegal file path '{info.filename}'"

                if required_entry and (info.filename.startswith(required_entry) or info.filename == required_entry):
                    has_required_entry = True

                total_uncompressed += info.file_size
                if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                    return False, f"Archive uncompressed size exceeds limit ({total_uncompressed} > {MAX_ZIP_UNCOMPRESSED_BYTES} bytes)"

                # Check ratio for members with meaningful size (> 1024 bytes)
                if info.compress_size > 0 and info.file_size > 1024:
                    ratio = info.file_size / info.compress_size
                    if ratio > MAX_ZIP_RATIO:
                        return False, f"Archive member '{info.filename}' exceeds safe compression ratio ({ratio:.1f} > {MAX_ZIP_RATIO})"

            if required_entry and not has_required_entry:
                return False, f"Archive missing required OpenXML structure '{required_entry}'"

            return True, None
    except zipfile.BadZipFile as exc:
        return False, f"Corrupted or invalid ZIP archive: {exc}"
    except Exception as exc:
        return False, f"Archive inspection failed: {exc}"


class PDFExtractor:
    def extract(self, content: bytes) -> ExtractionResult:
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            return ExtractionResult(text="", status="failed", error=f"Invalid or corrupted PDF: {exc}")

        try:
            if getattr(document, "is_encrypted", False):
                return ExtractionResult(
                    text="",
                    status="failed",
                    error="Encrypted/password-protected PDFs are not supported",
                    metadata={"encrypted": True},
                )

            total_pages = len(document)
            pages_to_read = min(total_pages, MAX_PDF_PAGES)
            parts: list[str] = []
            total_chars = 0
            text_truncated = False

            for page_idx in range(pages_to_read):
                try:
                    page_text = document[page_idx].get_text()
                except Exception as exc:
                    page_text = f"[Error reading page {page_idx + 1}: {exc}]"

                if total_chars + len(page_text) > MAX_EXTRACTED_CHARS:
                    remaining = MAX_EXTRACTED_CHARS - total_chars
                    if remaining > 0:
                        parts.append(page_text[:remaining])
                        total_chars += remaining
                    text_truncated = True
                    break
                parts.append(page_text)
                total_chars += len(page_text)

            extracted_text = "\n".join(parts).strip()
            if len(extracted_text) > MAX_EXTRACTED_CHARS:
                extracted_text = extracted_text[:MAX_EXTRACTED_CHARS]
                text_truncated = True
            is_page_truncated = total_pages > MAX_PDF_PAGES

            metadata = {
                "pages": total_pages,
                "extracted_pages": pages_to_read,
                "truncated_pages": is_page_truncated,
                "truncated_text": text_truncated,
                "char_count": len(extracted_text),
            }
            return ExtractionResult(text=extracted_text, status="extracted", metadata=metadata)
        finally:
            document.close()


class DOCXExtractor:
    def extract(self, content: bytes) -> ExtractionResult:
        safe, err = _inspect_safe_zip(content, required_entry="word/")
        if not safe:
            return ExtractionResult(text="", status="failed", error=f"Unsafe or invalid DOCX: {err}")

        try:
            document = Document(BytesIO(content))
            parts: list[str] = []
            total_chars = 0
            truncated = False

            for p in document.paragraphs:
                if p.text:
                    if total_chars + len(p.text) > MAX_EXTRACTED_CHARS:
                        remaining = MAX_EXTRACTED_CHARS - total_chars
                        if remaining > 0:
                            parts.append(p.text[:remaining])
                        truncated = True
                        break
                    parts.append(p.text)
                    total_chars += len(p.text)

            text = "\n".join(parts).strip()
            return ExtractionResult(
                text=text,
                status="extracted",
                metadata={"truncated_text": truncated, "char_count": len(text)},
            )
        except Exception as exc:
            return ExtractionResult(text="", status="failed", error=f"DOCX parsing error: {exc}")


class XLSXExtractor:
    def extract(self, content: bytes) -> ExtractionResult:
        safe, err = _inspect_safe_zip(content, required_entry="xl/")
        if not safe:
            return ExtractionResult(text="", status="failed", error=f"Unsafe or invalid XLSX: {err}")

        workbook = None
        try:
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            lines: list[str] = []
            total_chars = 0
            truncated = False
            sheet_count = 0

            for sheet in workbook.worksheets:
                if sheet_count >= MAX_XLSX_SHEETS:
                    truncated = True
                    break
                sheet_count += 1
                row_count = 0
                for row in sheet.iter_rows(values_only=True):
                    if row_count >= MAX_XLSX_ROWS_PER_SHEET:
                        truncated = True
                        break
                    row_count += 1
                    cells = [str(cell) for cell in row if cell is not None]
                    if cells:
                        line = "\t".join(cells)
                        if total_chars + len(line) > MAX_EXTRACTED_CHARS:
                            remaining = MAX_EXTRACTED_CHARS - total_chars
                            if remaining > 0:
                                lines.append(line[:remaining])
                            truncated = True
                            break
                        lines.append(line)
                        total_chars += len(line)
                if truncated and total_chars >= MAX_EXTRACTED_CHARS:
                    break

            text = "\n".join(lines).strip()
            return ExtractionResult(
                text=text,
                status="extracted",
                metadata={
                    "sheets_processed": sheet_count,
                    "truncated": truncated,
                    "char_count": len(text),
                },
            )
        except Exception as exc:
            return ExtractionResult(text="", status="failed", error=f"XLSX parsing error: {exc}")
        finally:
            if workbook is not None:
                workbook.close()


class ImageExtractor:
    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        suffix = Path(filename).suffix.lower()
        if suffix == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
            return ExtractionResult(text="", status="failed", error="Invalid PNG file signature")
        if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
            return ExtractionResult(text="", status="failed", error="Invalid JPEG file signature")

        return ExtractionResult(
            text="",
            status="extracted",
            metadata={
                "note": "Phase 2 stores images without OCR",
                "filename": filename,
                "bytes": len(content),
                "format": suffix.lstrip("."),
            },
        )


class DocumentExtractor:
    def extract(self, content: bytes, filename: str, content_type: str | None = None) -> ExtractionResult:
        suffix = Path(filename).suffix.lower()
        try:
            if suffix == ".pdf":
                return PDFExtractor().extract(content)
            if suffix == ".docx":
                return DOCXExtractor().extract(content)
            if suffix == ".xlsx":
                return XLSXExtractor().extract(content)
            if suffix in {".png", ".jpg", ".jpeg"}:
                return ImageExtractor().extract(content, filename)
            return ExtractionResult(text="", status="failed", error=f"Unsupported type: {suffix}")
        except Exception as exc:  # noqa: BLE001 — surface extractor failures to the record
            return ExtractionResult(text="", status="failed", error=str(exc))
