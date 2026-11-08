"""
Tool 3 – Mock Events API
========================
A deterministic, local mock API that returns event date and location.

This is NOT a real external API call. It uses an in-memory dictionary
so that the tool-calling architecture can be demonstrated offline without
any network access or API key.

Input  : {"event_name": str}
Output on success (event found AND has metadata):
    {
        "status":     "ok",
        "event_name": str,
        "date":       str,   # ISO 8601 date, e.g. "2026-07-02"
        "location":   str
    }
Output when the event exists but metadata is unavailable:
    {
        "status":     "no_metadata",
        "event_name": str,
        "message":    str
    }
Output when the event is completely unknown:
    {
        "status":  "not_found",
        "error":   str
    }

The API never invents dates or locations for events that are not in the
registry.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Internal mock data store
# ---------------------------------------------------------------------------
# Sentinel value used to indicate a known event that intentionally has no
# date/location metadata yet.
_NO_METADATA = object()

_EVENT_DATABASE: dict[str, object] = {
    "AI Club Talk": {
        "date": "2026-07-02",
        "location": "CS Block Auditorium",
    },
    "Hackathon Kickoff": {
        "date": "2026-07-05",
        "location": "Innovation Lab",
    },
    "Robotics Demo": {
        "date": "2026-07-10",
        "location": "Engineering Workshop",
    },
    "GenAI Workshop": {
        "date": "2026-07-14",
        "location": "Seminar Hall B",
    },
    # Capstone Expo is a known event but its metadata is intentionally absent
    # to demonstrate graceful missing-record handling.
    "Capstone Expo": _NO_METADATA,
    "Career Panel": {
        "date": "2026-07-20",
        "location": "Main Auditorium",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_event_info(event_name: str) -> dict:
    """
    Retrieve date and location for a named campus event from the mock API.

    Args:
        event_name: The exact name of the event (case-sensitive).

    Returns:
        A dict with status "ok", "no_metadata", or "not_found".

    Examples
    --------
    >>> get_event_info("Hackathon Kickoff")
    {'status': 'ok', 'event_name': 'Hackathon Kickoff', 'date': '2026-07-05', 'location': 'Innovation Lab'}

    >>> get_event_info("Capstone Expo")
    {'status': 'no_metadata', 'event_name': 'Capstone Expo', 'message': "No date/location metadata available for 'Capstone Expo' in the events registry."}

    >>> get_event_info("Unknown Event")
    {'status': 'not_found', 'error': "Event 'Unknown Event' was not found in the mock events API. Known events: ..."}
    """
    if not isinstance(event_name, str) or not event_name.strip():
        return {
            "status": "not_found",
            "error": "event_name must be a non-empty string.",
        }

    event_name = event_name.strip()
    record = _EVENT_DATABASE.get(event_name, None)

    # --- completely unknown event -------------------------------------------
    if record is None:
        known = sorted(
            k for k, v in _EVENT_DATABASE.items() if v is not _NO_METADATA
        ) + sorted(
            k for k, v in _EVENT_DATABASE.items() if v is _NO_METADATA
        )
        return {
            "status": "not_found",
            "error": (
                f"Event '{event_name}' was not found in the mock events API. "
                f"Known events: {known}."
            ),
        }

    # --- event exists but metadata is intentionally absent ------------------
    if record is _NO_METADATA:
        return {
            "status": "no_metadata",
            "event_name": event_name,
            "message": (
                f"No date/location metadata available for '{event_name}' "
                f"in the events registry."
            ),
        }

    # --- successful response ------------------------------------------------
    metadata = dict(record)  # type: ignore[arg-type]
    return {
        "status": "ok",
        "event_name": event_name,
        "date": metadata["date"],
        "location": metadata["location"],
    }

