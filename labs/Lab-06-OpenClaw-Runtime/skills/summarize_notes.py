"""Skill: Summarize Notes.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from typing import Any, Callable, Dict
from skills.base_skill import BaseSkill


class SummarizeNotesSkill(BaseSkill):
    """Summarizes user notes using the word-count tool and stores length in memory."""

    name: str = "summarize_notes"

    def execute(
        self,
        task: Any,
        user: str,
        memory_scope: Dict[str, Any],
        tools: Dict[str, Callable[..., Any]],
    ) -> Dict[str, Any]:
        """Summarize notes text and update the user's memory scope.

        Args:
            task: Task dictionary containing 'text' or raw text string.
            user: Invoking user identifier.
            memory_scope: The user's private memory scope.
            tools: Registered tools dictionary.

        Returns:
            Dictionary containing the summary stub, word count, and text.
        """
        # Extract text from task dictionary or raw string
        if isinstance(task, dict):
            text = task.get("text") or task.get("note") or task.get("content") or ""
        elif isinstance(task, str):
            text = task
        else:
            text = str(task)

        # Retrieve word count tool
        if "word_count" not in tools:
            raise KeyError("Required tool 'word_count' is not registered in TOOLS.")

        word_count_tool = tools["word_count"]
        tool_res = word_count_tool(text)
        self.record_tool_call("word_count", {"text": text}, tool_res)

        count = tool_res.get("count", 0)

        # Store note length in user's scoped memory
        memory_scope["last_note_length"] = count
        memory_scope["last_summarized_text"] = text

        summary_text = f"Summary stub: note has {count} words."

        return {
            "status": "success",
            "summary": summary_text,
            "word_count": count,
            "text": text,
            "user": user,
        }
