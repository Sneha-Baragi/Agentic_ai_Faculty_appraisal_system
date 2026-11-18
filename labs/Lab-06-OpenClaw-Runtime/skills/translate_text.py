"""Skill: Translate Text.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Extensible Skill Demonstration
"""

from typing import Any, Callable, Dict
from skills.base_skill import BaseSkill


class TranslateTextSkill(BaseSkill):
    """Demonstrates dynamic skill extensibility by generating translated text stubs."""

    name: str = "translate_text"

    def execute(
        self,
        task: Any,
        user: str,
        memory_scope: Dict[str, Any],
        tools: Dict[str, Callable[..., Any]],
    ) -> Dict[str, Any]:
        """Translate supplied text to target language stub.

        Args:
            task: Task dictionary containing 'text' and 'target_language'.
            user: Invoking user identifier.
            memory_scope: The user's private memory scope.
            tools: Registered tools dictionary.

        Returns:
            Dictionary containing source text, target language, and translation stub.
        """
        if isinstance(task, dict):
            text = task.get("text", "")
            target_language = (
                task.get("target_language") or task.get("language") or "Kannada"
            )
        elif isinstance(task, str):
            text = task
            target_language = "Kannada"
        else:
            text = str(task)
            target_language = "Kannada"

        translated_text = f"[translated to {target_language}] {text}"

        # Record into user's scoped memory
        memory_scope["last_translation_language"] = target_language
        memory_scope["last_translated_text"] = translated_text

        return {
            "status": "success",
            "source_text": text,
            "target_language": target_language,
            "translated_text": translated_text,
            "user": user,
        }
