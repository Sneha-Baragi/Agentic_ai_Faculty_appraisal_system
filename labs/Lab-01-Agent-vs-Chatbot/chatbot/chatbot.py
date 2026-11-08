"""Conventional Study Planning Chatbot.

This module implements a conventional single-turn conversational chatbot for study planning.
In contrast to an autonomous agent, this chatbot:
1. Generates a single, direct text response without maintaining structured state.
2. Cannot autonomously call external tools (e.g., does not inspect institutional schedules).
3. Does not run an iterative Goal-Plan-Act-Observe-Revise loop.
4. Makes arbitrary static assumptions about missing requirements rather than proactively clarifying them.
5. Treats subsequent feedback as a disconnected prompt rather than mutating a persistent plan object.
"""

from typing import Any, Dict, List, Optional


class StudyChatbot:
    """Conventional single-turn chatbot for study planning.

    Illustrates traditional prompt-response mechanics without autonomous
    tool-use, structured state tracking, or iterative plan revision.
    """

    def __init__(self, name: str = "ConventionalStudyBot") -> None:
        self.name = name
        self.tool_calls_count: int = 0
        self.has_autonomous_loop: bool = False
        self.maintains_structured_state: bool = False
        self.last_response: Optional[str] = None

    def respond(self, message: str) -> str:
        """Process a user prompt and return a static text response.

        The chatbot does not verify calendar availability, does not ask structured
        clarifying questions to fill missing parameters, and does not retain a
        persisted schedule data structure.
        """
        lower_msg = message.lower()

        # If user provides feedback on a previously suggested schedule
        if "move" in lower_msg or "change" in lower_msg or "feedback" in lower_msg or "evening" in lower_msg:
            response = (
                f"[{self.name} Response]\n"
                "Sure, I can adjust that for you! Here is a newly rewritten generic schedule:\n"
                "• Monday: Study session (Morning, 2 hours)\n"
                "• Tuesday: Study session (Evening, 2 hours)\n"
                "• Wednesday: Study session (Morning, 2 hours)\n"
                "• Thursday: Study session (Morning, 2 hours)\n"
                "• Friday: Study session (Morning, 2 hours)\n"
                "• Saturday: Study session (Morning, 2 hours)\n"
                "• Sunday: Study session (Morning, 2 hours)\n\n"
                "Note: I generated this fresh response from scratch. I do not maintain your previous "
                "schedule object, nor do I have access to your calendar or institutional timetable."
            )
            self.last_response = response
            return response

        # Standard initial request (incomplete or complete)
        response = (
            f"[{self.name} Response]\n"
            "Hello! Here is a general study plan for your request:\n\n"
            "• Monday: 2 hours of Data Structures\n"
            "• Tuesday: 2 hours of Operating Systems\n"
            "• Wednesday: 2 hours of AI Agents\n"
            "• Thursday: 2 hours of Data Structures\n"
            "• Friday: 2 hours of Operating Systems\n"
            "• Saturday: 2 hours of AI Agents\n"
            "• Sunday: 2 hours of General Review\n\n"
            "Assumptions made by chatbot:\n"
            "- Assumed 2 hours per day across all 7 days.\n"
            "- Assumed you are available on Wednesday (did not check university timetable).\n"
            "- Assumed you are available on Sunday (did not clarify preferred rest days).\n"
            "- No tools were invoked; no persistent state was stored."
        )
        self.last_response = response
        return response

    def inspect_capabilities(self) -> Dict[str, Any]:
        """Return diagnostic metrics contrasting with an agent."""
        return {
            "model_type": "conventional_chatbot",
            "autonomous_loop": self.has_autonomous_loop,
            "tool_calls_count": self.tool_calls_count,
            "maintains_structured_state": self.maintains_structured_state,
            "can_mutate_plan_in_place": False,
        }

