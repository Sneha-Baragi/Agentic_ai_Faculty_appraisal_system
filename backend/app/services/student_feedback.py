"""Institutional Student Feedback ingestion and matching service.

Reads and validates official student feedback CSV files, matches records to
faculty members without fuzzy ambiguity, and provides linear conversion to
rubric-scaled points.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any
import unicodedata

DEFAULT_FEEDBACK_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_student_feedback.csv"
REQUIRED_COLUMNS = ("Faculty Name", "Feedback Percentage")

# Recognized leading honorifics with an unspaced period (e.g. 'Dr.Uday' -> 'Dr. Uday')
LEADING_HONORIFIC_UNSPACED_PATTERN = re.compile(
    r"^(dr|prof|professor|mr|mrs|ms)\.(?=\w)",
    re.IGNORECASE,
)


class StudentFeedbackError(ValueError):
    """Base exception for student feedback errors."""


class StudentFeedbackFileNotFoundError(StudentFeedbackError, FileNotFoundError):
    """Raised when the student feedback CSV file cannot be found."""


class StudentFeedbackDataError(StudentFeedbackError):
    """Raised when the student feedback CSV file fails validation."""


@dataclass(frozen=True)
class FeedbackRecord:
    faculty_name: str
    normalized_name: str
    percentage: float
    row_number: int


def get_default_feedback_csv_path() -> Path:
    """Return the resolved path to the default student feedback CSV."""
    return DEFAULT_FEEDBACK_CSV_PATH


def normalize_faculty_name(name: str | None) -> str:
    """Normalize a faculty name for exact matching without fuzzy logic.

    Performs Unicode NFKC normalization, whitespace stripping, normalized spacing
    after recognized leading honorific periods, internal whitespace collapsing,
    and case folding.
    """
    if name is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(name)).strip()
    normalized = LEADING_HONORIFIC_UNSPACED_PATTERN.sub(r"\g<1>. ", normalized)
    return " ".join(normalized.split()).casefold()


def calculate_student_feedback_points(
    feedback_percentage: float,
    item_cap: float,
) -> float:
    """Convert feedback percentage (0-100) to rubric points clamped to item cap.

    Formula: feedback_points = (feedback_percentage / 100) * item_cap
    """
    if not (0.0 <= feedback_percentage <= 100.0):
        raise ValueError(
            f"Feedback percentage {feedback_percentage} is outside valid range [0, 100]"
        )
    if item_cap < 0:
        raise ValueError(f"Rubric item cap {item_cap} cannot be negative")
    raw_points = (feedback_percentage / 100.0) * item_cap
    return round(min(raw_points, item_cap), 4)


def load_student_feedback_csv(
    csv_path: Path | str | None = None,
) -> dict[str, FeedbackRecord]:
    """Load and strictly validate a student feedback CSV file.

    Returns:
        dict mapping normalized faculty name to FeedbackRecord.

    Raises:
        StudentFeedbackFileNotFoundError: If the CSV file does not exist.
        StudentFeedbackDataError: If headers are missing, rows are malformed,
            percentages are non-numeric or out-of-range, or duplicate faculty
            names are encountered.
    """
    target_path = Path(csv_path) if csv_path is not None else DEFAULT_FEEDBACK_CSV_PATH
    if not target_path.is_file():
        raise StudentFeedbackFileNotFoundError(
            f"Student feedback CSV file not found at: {target_path}"
        )

    records: dict[str, FeedbackRecord] = {}

    try:
        with target_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)

            try:
                header = next(reader)
            except StopIteration:
                raise StudentFeedbackDataError(
                    f"Student feedback CSV at {target_path} is empty"
                )

            cleaned_header = [col.strip() for col in header]

            name_col = "Faculty Name"
            perc_col = "Feedback Percentage"
            if name_col not in cleaned_header or perc_col not in cleaned_header:
                raise StudentFeedbackDataError(
                    f"Student feedback CSV at {target_path} is missing required headers. "
                    f"Expected {REQUIRED_COLUMNS}, got {header}"
                )

            name_idx = cleaned_header.index(name_col)
            perc_idx = cleaned_header.index(perc_col)

            for row_idx, row in enumerate(reader, start=2):
                if not row or not any(cell.strip() for cell in row):
                    continue

                if len(row) <= max(name_idx, perc_idx):
                    raise StudentFeedbackDataError(
                        f"Student feedback CSV at {target_path} has malformed row {row_idx}: "
                        f"expected at least {max(name_idx, perc_idx) + 1} columns, found {len(row)}: {row}"
                    )

                raw_name = row[name_idx].strip()
                if not raw_name:
                    raise StudentFeedbackDataError(
                        f"Student feedback CSV at {target_path} has empty Faculty Name at row {row_idx}"
                    )

                normalized = normalize_faculty_name(raw_name)
                if normalized in records:
                    prev = records[normalized]
                    raise StudentFeedbackDataError(
                        f"Duplicate faculty name '{raw_name}' at row {row_idx} in {target_path} "
                        f"(previously defined at row {prev.row_number} as '{prev.faculty_name}')"
                    )

                raw_perc = row[perc_idx].strip()
                try:
                    perc_val = float(raw_perc)
                except (ValueError, TypeError):
                    raise StudentFeedbackDataError(
                        f"Invalid numeric percentage '{raw_perc}' for faculty '{raw_name}' at row {row_idx} in {target_path}"
                    )

                if not (0.0 <= perc_val <= 100.0):
                    raise StudentFeedbackDataError(
                        f"Feedback percentage {perc_val} is out of valid range [0, 100] for faculty '{raw_name}' at row {row_idx} in {target_path}"
                    )

                records[normalized] = FeedbackRecord(
                    faculty_name=raw_name,
                    normalized_name=normalized,
                    percentage=perc_val,
                    row_number=row_idx,
                )

    except (OSError, UnicodeDecodeError) as exc:
        if isinstance(exc, StudentFeedbackError):
            raise
        raise StudentFeedbackDataError(
            f"Failed to read student feedback CSV at {target_path}: {exc}"
        ) from exc

    return records


HONORIFIC_FAMILIES: dict[str, str] = {
    "dr.": "dr",
    "dr": "dr",
    "prof.": "prof",
    "prof": "prof",
    "professor": "prof",
    "mr.": "mr",
    "mr": "mr",
    "mrs.": "mrs",
    "mrs": "mrs",
    "ms.": "ms",
    "ms": "ms",
}


def extract_honorific_and_base_name(normalized_name: str) -> tuple[str | None, str]:
    """Extract (canonical_honorific_family, base_name) from a normalized name.

    Examples:
        'dr. uday kulkarni' -> ('dr', 'uday kulkarni')
        'dr uday kulkarni' -> ('dr', 'uday kulkarni')
        'uday kulkarni' -> (None, 'uday kulkarni')
        'prof. rohan deshmukh' -> ('prof', 'rohan deshmukh')
    """
    tokens = normalized_name.split()
    if tokens:
        first = tokens[0]
        if first in HONORIFIC_FAMILIES:
            return HONORIFIC_FAMILIES[first], " ".join(tokens[1:])
        for hon_prefix, family in HONORIFIC_FAMILIES.items():
            if hon_prefix.endswith(".") and first.startswith(hon_prefix) and len(first) > len(hon_prefix):
                base_first = first[len(hon_prefix):]
                rest = [base_first] + tokens[1:]
                return family, " ".join(rest)
    return None, normalized_name


def get_student_feedback_record(
    faculty_name: str | None,
    csv_path: Path | str | None = None,
) -> dict[str, Any] | None:
    """Find student feedback for a given faculty name.

    Deterministic two-tier matching:
    - Tier 1: Exact normalized matching.
    - Tier 2: If the profile has no honorific, matches a CSV record with an honorific
      provided the base name maps to exactly one CSV record. If punctuation differs
      (e.g. 'Dr' vs 'Dr.'), matches within the same honorific family.
      Different explicit honorifics (e.g. 'Prof.' vs 'Dr.') are rejected.
    - If multiple CSV records share the same base name, returns status 'ambiguous_match'.
    - Never uses fuzzy matching, partial names, or fallback across faculty.

    Returns:
        Dict with keys: faculty_name, feedback_percentage, status, source_file.
    """
    target_path = Path(csv_path) if csv_path is not None else DEFAULT_FEEDBACK_CSV_PATH
    source_file = target_path.name

    if not faculty_name or not str(faculty_name).strip():
        return {
            "faculty_name": faculty_name,
            "feedback_percentage": None,
            "status": "missing_faculty_name",
            "source_file": source_file,
        }

    records = load_student_feedback_csv(target_path)
    normalized = normalize_faculty_name(faculty_name)

    # Tier 1: Exact normalized matching
    record = records.get(normalized)
    if record is not None:
        return {
            "faculty_name": record.faculty_name,
            "feedback_percentage": record.percentage,
            "status": "matched",
            "source_file": source_file,
        }

    # Tier 2: Honorific-aware base name matching
    input_hon, input_base = extract_honorific_and_base_name(normalized)

    # Index candidate CSV records sharing this base name
    base_name_candidates: list[tuple[str | None, FeedbackRecord]] = []
    for rec in records.values():
        rec_hon, rec_base = extract_honorific_and_base_name(rec.normalized_name)
        if rec_base == input_base:
            base_name_candidates.append((rec_hon, rec))

    if not base_name_candidates:
        return {
            "faculty_name": faculty_name,
            "feedback_percentage": None,
            "status": "unmatched",
            "source_file": source_file,
        }

    # Case 2A: Faculty profile has NO honorific (e.g. 'Uday Kulkarni')
    if input_hon is None:
        if len(base_name_candidates) > 1:
            # Multiple CSV records share the base name -> ambiguous collision
            return {
                "faculty_name": faculty_name,
                "feedback_percentage": None,
                "status": "ambiguous_match",
                "source_file": source_file,
            }
        # Exactly one CSV record has this base name -> unique match!
        rec_hon, rec = base_name_candidates[0]
        return {
            "faculty_name": rec.faculty_name,
            "feedback_percentage": rec.percentage,
            "status": "matched",
            "source_file": source_file,
        }

    # Case 2B: Faculty profile explicitly has an honorific (e.g. 'Dr' or 'Prof.')
    # Filter candidates to those within the same honorific family (e.g. Dr vs Dr.)
    matching_candidates = [
        (rec_hon, rec) for rec_hon, rec in base_name_candidates if rec_hon == input_hon
    ]

    if len(matching_candidates) == 1:
        rec_hon, rec = matching_candidates[0]
        return {
            "faculty_name": rec.faculty_name,
            "feedback_percentage": rec.percentage,
            "status": "matched",
            "source_file": source_file,
        }

    if len(matching_candidates) > 1:
        return {
            "faculty_name": faculty_name,
            "feedback_percentage": None,
            "status": "ambiguous_match",
            "source_file": source_file,
        }

    # Different explicit honorific (e.g. Prof. vs Dr., or Mr. vs Dr./Prof.)
    return {
        "faculty_name": faculty_name,
        "feedback_percentage": None,
        "status": "unmatched",
        "source_file": source_file,
    }
