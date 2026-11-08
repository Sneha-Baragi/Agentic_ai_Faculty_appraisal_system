"""
Tool 1 – Calculator
===================
Supports two operations on a list of numeric values:
  - "sum"     → returns the total
  - "average" → returns the mean, rounded to 2 decimal places

Input  : {"operation": str, "values": list[int | float]}
Output : {"result": int | float}        on success
         {"error": str}                 on failure

The calculator never silently returns incorrect results.
No external dependencies are used.
"""

from __future__ import annotations
from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculator(operation: str, values: list[Any]) -> dict:
    """
    Perform a supported arithmetic operation on a list of values.

    Args:
        operation: One of "sum" or "average".
        values:    A non-empty list of int or float values.

    Returns:
        A dict with key "result" on success, or "error" on failure.

    Examples
    --------
    >>> calculator(operation="sum", values=[12, 9, 15])
    {'result': 36}
    >>> calculator(operation="average", values=[12, 9, 15])
    {'result': 12.0}
    """
    # --- validate operation -------------------------------------------------
    supported = {"sum", "average"}
    if not isinstance(operation, str) or operation.lower() not in supported:
        return {
            "error": (
                f"Unsupported operation '{operation}'. "
                f"Supported operations are: {sorted(supported)}."
            )
        }
    operation = operation.lower()

    # --- validate values type -----------------------------------------------
    if not isinstance(values, list):
        return {
            "error": (
                f"'values' must be a list, got {type(values).__name__}."
            )
        }

    # --- validate empty list -------------------------------------------------
    if len(values) == 0:
        return {
            "error": (
                "Cannot perform operation on an empty list. "
                "Provide at least one numeric value."
            )
        }

    # --- validate each element is numeric ------------------------------------
    invalid = [
        (i, v) for i, v in enumerate(values)
        if not isinstance(v, (int, float)) or isinstance(v, bool)
    ]
    if invalid:
        bad_items = ", ".join(
            f"index {i}: {v!r}" for i, v in invalid
        )
        return {
            "error": (
                f"All values must be int or float. "
                f"Invalid entries: [{bad_items}]."
            )
        }

    # --- compute -------------------------------------------------------------
    if operation == "sum":
        result = sum(values)
        # Return int if the result is a whole number, else float
        result = int(result) if result == int(result) else result
        return {"result": result}

    if operation == "average":
        avg = sum(values) / len(values)
        return {"result": round(avg, 2)}

    # This line is unreachable given the validation above but satisfies linters.
    return {"error": f"Internal error: operation '{operation}' fell through."}

