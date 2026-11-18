"""Tools Layer Package.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from typing import Any, Callable, Dict

from tools.contact_lookup import DEFAULT_CONTACTS, tool_lookup_contact
from tools.word_count import tool_word_count

# Central TOOLS registry
TOOLS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "word_count": tool_word_count,
    "contact_lookup": tool_lookup_contact,
}

__all__ = [
    "TOOLS",
    "DEFAULT_CONTACTS",
    "tool_word_count",
    "tool_lookup_contact",
]
