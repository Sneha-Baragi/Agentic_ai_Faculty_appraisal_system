"""Tool: Contact Lookup.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from typing import Any, Dict, Optional

# Mock contacts database with required Dr. Meena contact
DEFAULT_CONTACTS: Dict[str, str] = {
    "Dr. Meena": "meena@example.edu",
    "Prof. Priya": "priya@example.edu",
    "Dr. Aarav": "aarav@example.edu",
    "Campus Coordinator": "coordinator@example.edu",
}


def tool_lookup_contact(
    name: str, contacts_db: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Look up a contact in a mock contacts database.

    Args:
        name: Name of the contact to find.
        contacts_db: Optional dictionary mapping contact names to email addresses.
                     Defaults to DEFAULT_CONTACTS.

    Returns:
        Structured dictionary containing contact details on success,
        or structured error when contact does not exist.
    """
    db = contacts_db if contacts_db is not None else DEFAULT_CONTACTS
    cleaned_name = name.strip() if isinstance(name, str) else ""

    if cleaned_name in db:
        return {
            "status": "success",
            "name": cleaned_name,
            "email": db[cleaned_name],
        }

    return {
        "status": "error",
        "error": f"Contact not found: {cleaned_name}",
        "name": cleaned_name,
    }
