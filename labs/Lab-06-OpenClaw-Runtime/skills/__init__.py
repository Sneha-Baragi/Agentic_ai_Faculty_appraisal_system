"""Skills Layer Package and Central Skill Registry.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime
"""

from typing import Dict, Type

from skills.base_skill import BaseSkill
from skills.draft_email import DraftEmailSkill
from skills.summarize_notes import SummarizeNotesSkill
from skills.translate_text import TranslateTextSkill

# Central SKILL_REGISTRY mapping skill name to its class
# Initially contains summarize_notes and draft_email (translate_text added dynamically)
SKILL_REGISTRY: Dict[str, Type[BaseSkill]] = {
    "summarize_notes": SummarizeNotesSkill,
    "draft_email": DraftEmailSkill,
}


def register_skill(name: str, skill_cls: Type[BaseSkill]) -> None:
    """Dynamically register a new skill class in SKILL_REGISTRY.

    Args:
        name: Unique string name of the skill (e.g. 'translate_text').
        skill_cls: Subclass of BaseSkill to instantiate.
    """
    SKILL_REGISTRY[name] = skill_cls


def unregister_skill(name: str) -> bool:
    """Dynamically remove a skill from SKILL_REGISTRY."""
    if name in SKILL_REGISTRY:
        del SKILL_REGISTRY[name]
        return True
    return False


def reset_skill_registry() -> None:
    """Reset SKILL_REGISTRY to the initial two base skills."""
    SKILL_REGISTRY.clear()
    SKILL_REGISTRY["summarize_notes"] = SummarizeNotesSkill
    SKILL_REGISTRY["draft_email"] = DraftEmailSkill


__all__ = [
    "BaseSkill",
    "SummarizeNotesSkill",
    "DraftEmailSkill",
    "TranslateTextSkill",
    "SKILL_REGISTRY",
    "register_skill",
    "unregister_skill",
    "reset_skill_registry",
]
