"""
Tool 4 – Notification Drafter (Assignment 1)
============================================
Drafts a low-turnout notification message. It does NOT send anything.
No email, SMS, or network call is made.

Input  : {"message": str, "threshold": float, "actual_average": float}
Output :
    {
        "status":   "drafted",
        "message":  str,       # the drafted notification text
        "drafted":  True
    }
    or {"error": str} on invalid input.

This tool is called only when the computed average falls below a threshold
(default: 10 sign-ups per event). The execution trace records why it was
invoked.
"""

from __future__ import annotations

# Default threshold for low-turnout detection.
LOW_TURNOUT_THRESHOLD: float = 10.0


def send_notification(
    message: str,
    threshold: float = LOW_TURNOUT_THRESHOLD,
    actual_average: float | None = None,
) -> dict:
    """
    Draft a notification message for low-turnout events.

    This function only DRAFTS the message; it does NOT actually send anything.

    Args:
        message:        The notification text to draft.
        threshold:      The sign-up average threshold below which a notice
                        is warranted. Defaults to 10.
        actual_average: The computed average that triggered this call.

    Returns:
        A dict with keys "status", "message", and "drafted" on success,
        or "error" on invalid input.

    Examples
    --------
    >>> send_notification("Average sign-ups dropped below threshold.", actual_average=8.5)
    {'status': 'drafted', 'message': '...', 'drafted': True, ...}
    """
    if not isinstance(message, str) or not message.strip():
        return {"error": "message must be a non-empty string."}

    drafted_text = (
        f"[DRAFT – NOT SENT] Low-Turnout Notice:\n"
        f"{message.strip()}\n"
    )
    if actual_average is not None:
        drafted_text += (
            f"\nActual average sign-ups: {actual_average} "
            f"(threshold: {threshold})."
        )

    return {
        "status": "drafted",
        "message": drafted_text,
        "drafted": True,
        "threshold_used": threshold,
        "actual_average": actual_average,
    }

