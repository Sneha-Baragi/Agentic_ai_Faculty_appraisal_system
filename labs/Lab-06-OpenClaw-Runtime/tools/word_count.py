"""Tool: Word Count.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from typing import Any, Dict


def tool_word_count(text: str) -> Dict[str, Any]:
    """Count the words in the supplied text.

    Args:
        text: Input string to analyze.

    Returns:
        Structured dictionary containing word count, e.g. {"count": 8}.
    """
    if not isinstance(text, str):
        return {"count": 0}
    words = text.strip().split()
    return {"count": len(words)}
