"""
Tool 2 – CSV File Reader
========================
Reads the local event-signup CSV file and returns structured rows.

Default CSV path: data/event_signups.csv (relative to the Lab-02 root).

Expected columns:
    Event    – event name (str)
    Signups  – number of sign-ups (int)
    Category – event category, e.g. "technical" or "social" (str, optional
               for base questions; required for Assignment 2)

Input  : {"csv_path": str}  (optional; defaults to the standard data file)
Output on success:
    {
        "rows":      [{"Event": str, "Signups": int, "Category": str}, ...],
        "row_count": int,
        "columns":   [str, ...]
    }
Output on failure:
    {"error": str}

The CSV reader never computes totals or averages; that is the calculator's job.
No external dependencies are used.
"""

from __future__ import annotations
import csv
import os
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Columns that MUST exist in the file for the base Lab-2 scenario.
REQUIRED_COLUMNS: list[str] = ["Event", "Signups"]

# Default path relative to the Lab-02 root directory.
_DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "event_signups.csv",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_csv(csv_path: str | None = None) -> dict:
    """
    Read the event-signup CSV file and return structured rows.

    Args:
        csv_path: Absolute or relative path to the CSV file.
                  Defaults to data/event_signups.csv inside the Lab-02 folder.

    Returns:
        A dict with keys "rows", "row_count", "columns" on success,
        or "error" on failure.

    Examples
    --------
    >>> result = read_csv()
    >>> result["row_count"]
    6
    >>> result["rows"][0]
    {'Event': 'AI Club Talk', 'Signups': 12, 'Category': 'technical'}
    """
    path = csv_path or _DEFAULT_CSV_PATH

    # --- file existence check -----------------------------------------------
    if not os.path.exists(path):
        return {
            "error": (
                f"CSV file not found at path: '{path}'. "
                "Ensure data/event_signups.csv exists in the Lab-02 directory."
            )
        }

    # --- file size / empty check --------------------------------------------
    if os.path.getsize(path) == 0:
        return {
            "error": (
                f"CSV file at '{path}' is empty. "
                "Populate it with event data before querying."
            )
        }

    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            columns: list[str] = list(reader.fieldnames or [])

            # --- column validation -------------------------------------------
            missing_cols = [c for c in REQUIRED_COLUMNS if c not in columns]
            if missing_cols:
                return {
                    "error": (
                        f"CSV is missing required column(s): {missing_cols}. "
                        f"Found columns: {columns}."
                    )
                }

            rows: list[dict[str, Any]] = []
            for line_num, raw_row in enumerate(reader, start=2):
                # Convert Signups to int; flag non-numeric values.
                signup_raw = raw_row.get("Signups", "").strip()
                try:
                    signup_int = int(signup_raw)
                except ValueError:
                    return {
                        "error": (
                            f"Non-integer value in 'Signups' column at "
                            f"line {line_num}: '{signup_raw}'."
                        )
                    }

                row: dict[str, Any] = {
                    "Event": raw_row.get("Event", "").strip(),
                    "Signups": signup_int,
                }

                # Include Category if present (required for Assignment 2).
                if "Category" in columns:
                    row["Category"] = raw_row.get("Category", "").strip()

                rows.append(row)

        # --- empty-data guard (header-only file) ----------------------------
        if len(rows) == 0:
            return {
                "error": (
                    f"CSV file at '{path}' contains only a header row "
                    "with no data."
                )
            }

        return {
            "rows": rows,
            "row_count": len(rows),
            "columns": columns,
        }

    except (OSError, csv.Error) as exc:
        return {"error": f"Failed to read CSV file: {exc}"}

