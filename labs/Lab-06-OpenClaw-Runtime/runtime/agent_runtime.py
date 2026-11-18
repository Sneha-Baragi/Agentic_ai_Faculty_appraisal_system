"""Core Agent Runtime: Interface, Runtime Loop, and Policy Controls.

Course: Agentic AI (26ECAC401)
Lab: 6 - OpenCLA/OpenClaw Runtime
Scenario: Personal Agent Runtime

Implements the six runtime components:
1. Interface: receive_task(task, user, memory, audit)
2. Runtime loop: run_task(task, user, memory, audit)
3. Skills layer: SKILL_REGISTRY and dynamic instantiation
4. Tools layer: TOOLS central registry
5. Memory layer: Memory.scope(user)
6. Audit layer: Audit.log(...)

Includes policy enforcement for:
- Assignment 1: Per-user rate limiting (max 3 tasks per session)
- Assignment 2: Failure escalation (escalates after 2 failures per user & skill)
"""

from typing import Any, Callable, Dict, Optional, Tuple

from runtime.audit import Audit
from runtime.memory import Memory
from skills import SKILL_REGISTRY
from tools import TOOLS


class RateLimitExceededError(Exception):
    """Raised when a user exceeds their allowed task quota for the session."""

    pass


class RateLimiter:
    """Tracks task submission counts per user within a runtime session."""

    def __init__(self, max_tasks: int = 3) -> None:
        """Initialize rate limiter with maximum task allowance per user."""
        self.max_tasks = max_tasks
        self.user_counts: Dict[str, int] = {}

    def get_count(self, user: str) -> int:
        """Return the number of tasks submitted by this user in this session."""
        return self.user_counts.get(user.strip(), 0)

    def is_allowed(self, user: str) -> bool:
        """Check if user is within their allowed task limit."""
        return self.get_count(user) < self.max_tasks

    def record_attempt(self, user: str) -> int:
        """Increment and return the task count for a user."""
        user_key = user.strip()
        count = self.user_counts.get(user_key, 0) + 1
        self.user_counts[user_key] = count
        return count

    def reset(self) -> None:
        """Reset all user rate limits for a new session."""
        self.user_counts.clear()


# Default session rate limiter
SESSION_RATE_LIMITER = RateLimiter(max_tasks=3)


# -----------------------------------------------------------------------------
# RUNTIME LOOP COMPONENT: Skill Selection
# -----------------------------------------------------------------------------


def select_skill(task: Any) -> Optional[str]:
    """Identify the requested skill name from the task.

    This function dynamically queries SKILL_REGISTRY so new skills
    can be added to SKILL_REGISTRY without modifying select_skill().

    Args:
        task: User task payload (dict or string).

    Returns:
        Matched skill name if found, or None.
    """
    if isinstance(task, dict):
        # 1. Explicit skill attribute
        for key in ("skill", "action", "skill_name", "type"):
            val = task.get(key)
            if isinstance(val, str) and val in SKILL_REGISTRY:
                return val

        # 2. Check if any registered skill name appears in dictionary values
        for val in task.values():
            if isinstance(val, str) and val in SKILL_REGISTRY:
                return val

    elif isinstance(task, str):
        cleaned = task.strip().lower()
        # Direct match with registered skill
        if cleaned in SKILL_REGISTRY:
            return cleaned

        # Substring / keyword match against registered skills
        for skill_name in SKILL_REGISTRY:
            if skill_name in cleaned:
                return skill_name

    return None


# -----------------------------------------------------------------------------
# RUNTIME LOOP COMPONENT: Task Execution
# -----------------------------------------------------------------------------


def run_task(
    task: Any,
    user: str,
    memory: Memory,
    audit: Audit,
) -> Dict[str, Any]:
    """Generic runtime loop for executing a single task.

    Execution Flow:
    1. Identify the requested skill via select_skill(task).
    2. Look up the skill class in SKILL_REGISTRY.
    3. Retrieve the current user's isolated memory scope via memory.scope(user).
    4. Instantiate the skill dynamically (no if/elif dispatch).
    5. Execute the task.
    6. Record a successful execution in the audit log.
    7. If execution fails, record error in audit log and propagate exception.

    Args:
        task: Task input payload.
        user: Invoking user identifier.
        memory: Memory layer instance.
        audit: Audit layer instance.

    Returns:
        Structured result dictionary from the skill execution.

    Raises:
        ValueError: If skill cannot be identified or is unregistered.
        Exception: Propagates any error raised during skill execution.
    """
    # 1. Identify requested skill
    skill_name = select_skill(task)
    if not skill_name or skill_name not in SKILL_REGISTRY:
        error_msg = f"Unknown or unregistered skill: '{skill_name}'"
        audit.log(
            task=task,
            skill_name=skill_name or "unknown",
            tool_calls=[],
            error=error_msg,
            user=user,
        )
        raise ValueError(error_msg)

    # 2. Look up skill class dynamically from registry
    skill_cls = SKILL_REGISTRY[skill_name]

    # 3. Get user's isolated memory scope
    user_mem = memory.scope(user)

    # 4. Instantiate skill dynamically
    skill_instance = skill_cls()

    # 5. Execute task with error handling
    try:
        result = skill_instance.execute(
            task=task,
            user=user,
            memory_scope=user_mem,
            tools=TOOLS,
        )
        # 6. Audit successful execution
        audit.log(
            task=task,
            skill_name=skill_name,
            tool_calls=skill_instance.tool_calls,
            result=result,
            error=None,
            user=user,
        )
        return result

    except Exception as exc:
        # 7. Audit failed execution and propagate exception
        audit.log(
            task=task,
            skill_name=skill_name,
            tool_calls=getattr(skill_instance, "tool_calls", []),
            result=None,
            error=str(exc),
            user=user,
        )
        raise


# -----------------------------------------------------------------------------
# INTERFACE COMPONENT: receive_task
# -----------------------------------------------------------------------------


def receive_task(
    task: Any,
    user: str,
    memory: Memory,
    audit: Audit,
    rate_limiter: Optional[RateLimiter] = None,
    enable_rate_limiting: bool = True,
    enable_escalation: bool = True,
    raise_on_rate_limit: bool = False,
) -> Dict[str, Any]:
    """Public entry point for submitting a task to the runtime.

    Orchestrates policy controls before delegating execution to run_task():
    1. Assignment 1: Enforces per-user session rate limit (max 3 tasks per session).
       Rejects the 4th task and records rejection in the audit log.
    2. Assignment 2: Checks audit log for previous failures of this skill by this user.
       If the same skill has failed twice, escalates to a human instead of executing.
    3. Delegates to run_task() for core execution.

    Args:
        task: Task input payload.
        user: Invoking user identifier.
        memory: Memory instance.
        audit: Audit instance.
        rate_limiter: Optional custom RateLimiter instance (defaults to SESSION_RATE_LIMITER).
        enable_rate_limiting: Whether rate limiting policy is active.
        enable_escalation: Whether failure escalation policy is active.
        raise_on_rate_limit: Whether to raise RateLimitExceededError instead of returning dict.

    Returns:
        Structured result, escalation response, or rejection error dictionary.
    """
    limiter = rate_limiter if rate_limiter is not None else SESSION_RATE_LIMITER
    skill_name = select_skill(task) or "unknown"

    # -------------------------------------------------------------------------
    # ASSIGNMENT 1: Per-User Session Rate Limiting Check
    # -------------------------------------------------------------------------
    if enable_rate_limiting:
        if not limiter.is_allowed(user):
            error_msg = (
                f"Rate limit exceeded: User '{user}' has reached the maximum allowance "
                f"of {limiter.max_tasks} tasks per session."
            )
            audit.log(
                task=task,
                skill_name=skill_name,
                tool_calls=[],
                result=None,
                error=error_msg,
                user=user,
            )
            if raise_on_rate_limit:
                raise RateLimitExceededError(error_msg)
            return {
                "status": "rejected",
                "error": error_msg,
                "user": user,
                "task_count": limiter.get_count(user),
                "limit": limiter.max_tasks,
            }

        # User is within limits; record task attempt in rate limiter
        limiter.record_attempt(user)

    # -------------------------------------------------------------------------
    # ASSIGNMENT 2: Escalate After Two Failures Check (Audit Log Driven)
    # -------------------------------------------------------------------------
    if enable_escalation and skill_name != "unknown":
        previous_failures = audit.count_failures(user=user, skill_name=skill_name)
        if previous_failures >= 2:
            escalation_response = {
                "status": "escalated",
                "reason": "The skill has failed twice in this session.",
                "skill": skill_name,
                "user": user,
                "previous_failures": previous_failures,
            }
            # Record escalation in audit log without calling skill.execute()
            audit.log(
                task=task,
                skill_name=skill_name,
                tool_calls=[],
                result=escalation_response,
                error=None,
                user=user,
            )
            return escalation_response

    # -------------------------------------------------------------------------
    # DELEGATE TO RUN_TASK
    # -------------------------------------------------------------------------
    return run_task(task=task, user=user, memory=memory, audit=audit)
