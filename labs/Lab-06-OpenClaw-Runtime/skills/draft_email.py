"""Skill: Draft Email.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from typing import Any, Callable, Dict
from skills.base_skill import BaseSkill


class DraftEmailSkill(BaseSkill):
    """Drafts an email message by verifying contact email via the lookup tool."""

    name: str = "draft_email"

    def execute(
        self,
        task: Any,
        user: str,
        memory_scope: Dict[str, Any],
        tools: Dict[str, Callable[..., Any]],
    ) -> Dict[str, Any]:
        """Draft an email if contact is found in the contact database.

        Args:
            task: Task dictionary containing 'recipient' and 'subject'.
            user: Invoking user identifier.
            memory_scope: The user's private memory scope.
            tools: Registered tools dictionary.

        Returns:
            Dictionary containing the draft email and recipient details.

        Raises:
            KeyError: If required tool is missing.
            ValueError: If contact cannot be found or required task fields are missing.
        """
        if not isinstance(task, dict):
            raise ValueError("DraftEmailSkill requires a dictionary task with recipient and subject.")

        recipient = task.get("recipient")
        subject = task.get("subject", "No Subject")

        if not recipient:
            raise ValueError("DraftEmailSkill requires a non-empty 'recipient' field.")

        if "contact_lookup" not in tools:
            raise KeyError("Required tool 'contact_lookup' is not registered in TOOLS.")

        lookup_tool = tools["contact_lookup"]
        tool_res = lookup_tool(recipient)
        self.record_tool_call("contact_lookup", {"name": recipient}, tool_res)

        if tool_res.get("status") != "success":
            raise ValueError(
                f"Contact lookup failed: Contact '{recipient}' was not found in directory."
            )

        email = tool_res["email"]
        draft_body = (
            f"To: {email}\n"
            f"Subject: {subject}\n\n"
            f"Dear {recipient},\n\n"
            f"This is a draft message regarding '{subject}'.\n\n"
            f"Best regards,\n"
            f"{user}"
        )

        # Store in user's scoped memory
        memory_scope["last_drafted_recipient"] = recipient
        memory_scope["last_drafted_email"] = email
        memory_scope["last_drafted_subject"] = subject

        return {
            "status": "success",
            "recipient": recipient,
            "email": email,
            "subject": subject,
            "draft": draft_body,
            "user": user,
        }
