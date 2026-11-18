# Lab 6: OpenCLA/OpenClaw Runtime – Personal Agent Runtime

- **Course:** Agentic AI (`26ECAC401`)
- **Lab:** 6
- **Topic:** Agent Runtime Pattern, Dynamic Skill Dispatch, Scoped Memory, and Operational Auditing
- **Scenario:** Personal Agent Runtime (OpenCLA / OpenClaw)
- **Repository Location:** `labs/Lab-06-OpenClaw-Runtime/`

---

## 1. Executive Summary & Objective

This laboratory implements a modular, extensible **Personal Agent Runtime** modeled after OpenCLA / OpenClaw architectures. The runtime orchestrates task requests across six decoupled subsystems:
1. **Public Interface Layer (`receive_task`):** Single point of entry enforcing session policies.
2. **Generic Runtime Loop (`run_task`, `select_skill`):** Dynamic dispatch without hardcoded `if/elif` ladders.
3. **Skills Layer (`SKILL_REGISTRY` & Skill Classes):** Extensible domain behaviors (`SummarizeNotesSkill`, `DraftEmailSkill`, `TranslateTextSkill`).
4. **Tools Layer (`TOOLS`):** Reusable discrete capabilities (`word_count`, `contact_lookup`).
5. **Memory Layer (`Memory.scope(user)`):** Strict per-user isolated memory scopes preventing cross-tenant leakage.
6. **Audit Layer (`Audit.log`):** Chronological compliance and operational trail recording timestamps, payloads, tool calls, results, and failures.

The runtime strictly relies on Python's standard library, requiring no external packages, paid APIs, or network requests.

---

## 2. Architecture & Task Execution Flow

```text
+-------------------------------------------------------------------------------+
|                                USER TASK INPUT                                |
|             {"skill": "summarize_notes", "text": "...", ...}                  |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                       INTERFACE LAYER: receive_task()                         |
|  - Assignment 1 Policy: Per-user session rate limit check (max 3/session)     |
|  - Assignment 2 Policy: Failure escalation check (audit failures >= 2)       |
+-------------------------------------------------------------------------------+
                                       | (If allowed & unescalated)
                                       v
+-------------------------------------------------------------------------------+
|                      RUNTIME LOOP LAYER: run_task()                           |
|  1. select_skill(task) queries dynamic SKILL_REGISTRY                        |
|  2. Fetches user's private memory scope: memory.scope(user)                  |
|  3. Dynamically instantiates skill: skill_cls()                               |
|  4. Injects TOOLS and invokes skill.execute(task, user, user_mem, TOOLS)     |
+-------------------------------------------------------------------------------+
          |                                                   |
          v                                                   v
+-----------------------+                           +-----------------------+
|     SKILLS LAYER      |                           |      TOOLS LAYER      |
| - SummarizeNotesSkill | --- invokes via TOOLS --> | - word_count()        |
| - DraftEmailSkill     |                           | - contact_lookup()    |
| - TranslateTextSkill  |                           |                       |
+-----------------------+                           +-----------------------+
          |                                                   |
          +-------------------------+-------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------------+
|                               STATE & AUDIT                                   |
|  - Memory.scope(user): Read/write persistent state private to current user   |
|  - Audit.log(): Writes ISO-stamped entry (task, skill, tools, result, error)  |
+-------------------------------------------------------------------------------+
```

---

## 3. Directory Structure

```text
labs/Lab-06-OpenClaw-Runtime/
│
├── runtime/
│   ├── __init__.py               # Exports Memory, Audit, RateLimiter, run_task, receive_task
│   ├── agent_runtime.py          # Core runtime loop, select_skill, and receive_task interface
│   ├── audit.py                  # Audit logger with ISO timestamps and failure query helpers
│   └── memory.py                 # Multi-tenant memory manager with strict per-user scopes
│
├── skills/
│   ├── __init__.py               # Exports SKILL_REGISTRY, register_skill, and skill classes
│   ├── base_skill.py             # Abstract base class defining skill interface & tool call tracking
│   ├── summarize_notes.py        # SummarizeNotesSkill (uses word_count tool, records memory)
│   ├── draft_email.py            # DraftEmailSkill (uses contact_lookup tool, error handling)
│   └── translate_text.py         # TranslateTextSkill (dynamically added third skill)
│
├── tools/
│   ├── __init__.py               # Central TOOLS dictionary and exports
│   ├── contact_lookup.py         # Mock directory lookup tool (Dr. Meena -> meena@example.edu)
│   └── word_count.py             # Reusable word count tool
│
├── examples/
│   └── sample_tasks.json         # JSON catalog of base runs, Assg 1, and Assg 2 tasks
│
├── tests/
│   ├── __init__.py
│   ├── test_audit.py             # Unit tests for audit logging & failure counting
│   ├── test_failure_escalation.py# Unit tests for Assignment 2 (audit-based human escalation)
│   ├── test_memory.py            # Unit tests for per-user memory scoping & isolation
│   ├── test_rate_limiting.py     # Unit tests for Assignment 1 (per-user session rate limit)
│   └── test_runtime.py           # Unit tests for runtime loop, error propagation & extensibility
│
├── main.py                       # Interactive CLI demonstration runner
├── requirements.txt              # Standard library declaration (zero third-party dependencies)
└── README.md                     # Comprehensive lab documentation
```

---

## 4. The Six Core Runtime Components

### Component 1: Interface (`receive_task`)
- **Function:** `receive_task(task, user, memory, audit, rate_limiter=None, ...)`
- Acts as the sole public gateway for task ingestion.
- Enforces session policies (rate limiting and human escalation) before delegating to `run_task()`.

### Component 2: Runtime Loop (`run_task` & `select_skill`)
- **Skill Selection:** `select_skill(task)` queries `SKILL_REGISTRY` dynamically. It matches dictionary keys (`task["skill"]`) or text keywords without maintaining any hardcoded list of skills.
- **Execution Loop:** `run_task()` resolves the class from `SKILL_REGISTRY`, scopes memory to `user`, executes the skill, and ensures both successes and exceptions are audited before propagating errors.

### Component 3: Skills Layer (`SKILL_REGISTRY`)
- Central dictionary: `SKILL_REGISTRY: Dict[str, Type[BaseSkill]]`.
- Pre-registered base skills:
  - `"summarize_notes"`: `SummarizeNotesSkill`
  - `"draft_email"`: `DraftEmailSkill`
- Dynamically registered skill:
  - `"translate_text"`: `TranslateTextSkill`
- All skills inherit from `BaseSkill` and manage their own `tool_calls` audit history.

### Component 4: Tools Layer (`TOOLS`)
- Central dictionary mapping tool names to callable functions:
  ```python
  TOOLS = {
      "word_count": tool_word_count,
      "contact_lookup": tool_lookup_contact,
  }
  ```
- Separates raw operational logic (string parsing, directory lookup) from agent reasoning.

### Component 5: Memory Layer (`Memory.scope(user)`)
- Provides partitioned dictionary storage: `memory.scope(user)`.
- Automatically provisions a clean dictionary for new users.
- Guarantee: Changes in `memory.scope("uday")` cannot alter or expose data in `memory.scope("priya")`.

### Component 6: Audit Layer (`Audit.log`)
- Structured logging records:
  - `timestamp`: ISO-8601 UTC timestamp.
  - `user`: Identifier of invoking user.
  - `task`: Original task payload.
  - `skill_name`: Target skill name.
  - `tool_calls`: List of executed tool names, inputs, and outputs.
  - `result`: Result dictionary on success.
  - `error`: Error string on failure.

---

## 5. Dynamic Extensibility: Adding a New Skill Without Code Rewrite

A critical grading requirement is that the runtime must accept new skills dynamically without modifying `run_task()` or `select_skill()`.

### Demonstration:
1. `TranslateTextSkill` is defined in `skills/translate_text.py`.
2. Initially, `"translate_text"` is **not** in `SKILL_REGISTRY`.
3. To register the skill at runtime:
   ```python
   from skills import register_skill, TranslateTextSkill
   register_skill("translate_text", TranslateTextSkill)
   ```
4. Submitting a task:
   ```python
   task = {"skill": "translate_text", "text": "Hello, team", "target_language": "Kannada"}
   result = receive_task(task, user="uday", memory=memory, audit=audit)
   # Result: "[translated to Kannada] Hello, team"
   ```
5. Verified by AST/source inspection: Neither `run_task` nor `select_skill` contains any string literals or references to `TranslateTextSkill` or `translate_text`.

---

## 6. Base Demonstration Results (`python main.py`)

Executing `python main.py` runs all five base scenarios:

```text
============================================================================
  LAB 6: BASE OPENCLA/OPENCLAW RUNTIME DEMONSTRATION
============================================================================
Runtime Architecture: Interface -> Loop -> Skills -> Tools -> Memory -> Audit
Initial Registered Skills: ['summarize_notes', 'draft_email']

--- [RUN 1] Successful Note Summarization (summarize_notes) --------------
User       : 'uday'
Task Input : {"skill": "summarize_notes", "text": "Agentic AI systems combine goals tools skills memory"}
Execution  : SUCCESS
Output     : Summary stub: note has 8 words.
Word Count : 8
Audit Log Entry:
  Timestamp  : 2026-11-18T15:38:00.190067+00:00
  User       : uday
  Skill      : summarize_notes
  Tool Calls : [{"tool": "word_count", "args": {"text": "Agentic AI systems combine goals tools skills memory"}, "output": {"count": 8}}]
  Result     : {"status": "success", "summary": "Summary stub: note has 8 words.", "word_count": 8, "text": "Agentic AI systems combine goals tools skills memory", "user": "uday"}

--- [RUN 2] Successful Email Drafting (draft_email) ----------------------
User       : 'uday'
Task Input : {"skill": "draft_email", "recipient": "Dr. Meena", "subject": "Lab guide review"}
Execution  : SUCCESS
Recipient  : Dr. Meena (meena@example.edu)
Draft Email:
To: meena@example.edu
Subject: Lab guide review

Dear Dr. Meena,

This is a draft message regarding 'Lab guide review'.

Best regards,
uday
Audit Log Entry:
  Timestamp  : 2026-11-18T15:38:00.190143+00:00
  User       : uday
  Skill      : draft_email
  Tool Calls : [{"tool": "contact_lookup", "args": {"name": "Dr. Meena"}, "output": {"status": "success", "name": "Dr. Meena", "email": "meena@example.edu"}}]
  Result     : {"status": "success", "recipient": "Dr. Meena", "email": "meena@example.edu", "subject": "Lab guide review", "draft": "To: meena@example.edu\nSubject: Lab guide review\n\nDear Dr. Meena,\n\nThis is a draft message regarding 'Lab guide review'.\n\nBest regards,\nuday", "user": "uday"}

--- [RUN 3] Failed Email Drafting (Unknown Contact) ----------------------
User       : 'uday'
Task Input : {"skill": "draft_email", "recipient": "Unknown Person", "subject": "Hello"}
Execution  : CAUGHT EXPECTED ERROR -> Contact lookup failed: Contact 'Unknown Person' was not found in directory.
Audit Verification (Error captured in log):
Audit Log Entry:
  Timestamp  : 2026-11-18T15:38:00.190201+00:00
  User       : uday
  Skill      : draft_email
  Tool Calls : [{"tool": "contact_lookup", "args": {"name": "Unknown Person"}, "output": {"status": "error", "error": "Contact not found: Unknown Person", "name": "Unknown Person"}}]
  Error      : Contact lookup failed: Contact 'Unknown Person' was not found in directory.

--- [RUN 4] Dynamic Skill Extensibility (TranslateTextSkill) -------------
Action     : Registering 'translate_text' into SKILL_REGISTRY at runtime...
Updated SKILL_REGISTRY: ['summarize_notes', 'draft_email', 'translate_text']
Task Input : {"skill": "translate_text", "text": "Hello, team", "target_language": "Kannada"}
Execution  : SUCCESS
Result     : [translated to Kannada] Hello, team
Audit Log Entry:
  Timestamp  : 2026-11-18T15:38:00.190251+00:00
  User       : uday
  Skill      : translate_text
  Tool Calls : []
  Result     : {"status": "success", "source_text": "Hello, team", "target_language": "Kannada", "translated_text": "[translated to Kannada] Hello, team", "user": "uday"}
Code Integrity: Generic dispatch preserved, hardcoding = False

--- [RUN 5] Per-User Scoped Memory Verification --------------------------
Memory Scope for 'uday' : {
  "last_note_length": 8,
  "last_summarized_text": "Agentic AI systems combine goals tools skills memory",
  "last_drafted_recipient": "Dr. Meena",
  "last_drafted_email": "meena@example.edu",
  "last_drafted_subject": "Lab guide review",
  "last_translation_language": "Kannada",
  "last_translated_text": "[translated to Kannada] Hello, team"
}
Memory Scope for 'priya': {
  "project": "Faculty Appraisal Agent"
}
Memory Isolation: uday keys present in priya scope = False (Strictly Isolated)
```

---

## 7. Assignment 1: Per-User Session Rate Limiting

### Policy Invariant:
- Users can execute at most **3 tasks per runtime session**.
- The **4th task** from the same user is rejected with a clear descriptive error.
- Quotas are maintained independently per user.
- Rejections are audited without executing the skill.
- Quotas reset upon initializing a new session.

### Execution Command:
```bash
python main.py --assignment1
```

### Actual Output:
```text
============================================================================
  ASSIGNMENT 1: PER-USER SESSION RATE LIMITING
============================================================================
Policy Invariant: Each user may execute at most 3 tasks per session.
The 4th task from the same user is rejected; distinct users have independent limits.

--- Submitting Task 1 for 'uday' ---
Status: SUCCESS | Count: 1/3
--- Submitting Task 2 for 'uday' ---
Status: SUCCESS | Count: 2/3
--- Submitting Task 3 for 'uday' ---
Status: SUCCESS | Count: 3/3

--- Submitting Task 4 for 'uday' (Expected: REJECTED) ---
Status: REJECTED
Message: Rate limit exceeded: User 'uday' has reached the maximum allowance of 3 tasks per session.
Audit Log Entry for Rejection:
Audit Log Entry:
  Timestamp  : 2026-11-18T15:38:16.262977+00:00
  User       : uday
  Skill      : summarize_notes
  Tool Calls : []
  Error      : Rate limit exceeded: User 'uday' has reached the maximum allowance of 3 tasks per session.

--- Submitting Task 1 for 'priya' (Independent Limit) ---
Status: SUCCESS | User 'priya' Count: 1/3

[Assignment 1 Verification Passed]: Rate limits enforced per-user and per-session.
```

---

## 8. Assignment 2: Escalate After Two Failures

### Policy Invariant:
- If a skill fails **twice** in one session for a user, the **third attempt** escalates to a human supervisor.
- **Audit-Log Driven:** Failure counts are queried directly from `audit.count_failures(user, skill_name)` rather than hidden counter state.
- The 3rd attempt is blocked from invoking the skill.
- Successful executions do not increase failure counts.
- Failures do not cross user or skill boundaries.

### Structured Escalation Response:
```json
{
  "status": "escalated",
  "reason": "The skill has failed twice in this session.",
  "skill": "draft_email",
  "user": "uday",
  "previous_failures": 2
}
```

### Execution Command:
```bash
python main.py --assignment2
```

### Actual Output:
```text
============================================================================
  ASSIGNMENT 2: ESCALATE AFTER TWO FAILURES
============================================================================
Policy Invariant: If a skill fails twice for a user in a session,
the 3rd attempt is escalated to a human supervisor instead of re-executing.

--- [ATTEMPT 1] Executing draft_email for unknown contact ---
Outcome: FAILED (Expected) -> Contact lookup failed: Contact 'Unknown Ghost Contact' was not found in directory.
Audit Log Failures Count: 1

--- [ATTEMPT 2] Repeating draft_email for unknown contact ---
Outcome: FAILED (Expected) -> Contact lookup failed: Contact 'Unknown Ghost Contact' was not found in directory.
Audit Log Failures Count: 2

--- [ATTEMPT 3] Third Attempt (Expected: ESCALATED TO HUMAN) ---
Outcome: ESCALATED
Escalation Payload: {
  "status": "escalated",
  "reason": "The skill has failed twice in this session.",
  "skill": "draft_email",
  "user": "uday",
  "previous_failures": 2
}

Audit Log Entry for Escalated Attempt (Skill was NOT executed):
Audit Log Entry:
  Timestamp  : 2026-11-18T15:38:29.744407+00:00
  User       : uday
  Skill      : draft_email
  Tool Calls : []
  Result     : {"status": "escalated", "reason": "The skill has failed twice in this session.", "skill": "draft_email", "user": "uday", "previous_failures": 2}

[Assignment 2 Verification Passed]: Skill was prevented from executing; escalation triggered.
```

---

## 9. Test Suite Verification

Run all unit tests using Python's built-in `unittest` runner:

```bash
python -m unittest discover -s tests -v
```

### Test Suite Breakdown:
| Test Module | Test Count | Focus Area |
| :--- | :---: | :--- |
| `tests/test_runtime.py` | 8 | Skill selection, note summarization, email drafting, error propagation, and dynamic registration of `TranslateTextSkill`. |
| `tests/test_memory.py` | 6 | Per-user memory provisioning, mutable persistence, cross-user isolation, helper methods (`get`, `set`, `has`, `clear`). |
| `tests/test_audit.py` | 4 | Timestamp ISO compliance, success/failure logging, failure counting queries. |
| `tests/test_rate_limiting.py` | 6 | First 3 tasks allowed, 4th task rejected, non-execution of rejected skills, independent user limits, session reset. |
| `tests/test_failure_escalation.py` | 5 | 1st/2nd failures logged, 3rd attempt escalation, non-execution of escalated skills, user/skill isolation, success non-pollution. |
| **Total** | **29** | **All 29 tests pass with 0 failures and 0 errors** |

---

## 10. CLI Execution Commands

From `labs/Lab-06-OpenClaw-Runtime/`:

```bash
# 1. Run full unit test suite
python -m unittest discover -s tests -v

# 2. Run Base Demonstration (Runs 1 to 5)
python main.py

# 3. Run Assignment 1 (Rate Limiting)
python main.py --assignment1

# 4. Run Assignment 2 (Failure Escalation)
python main.py --assignment2

# 5. Run All Demonstrations Sequentially
python main.py --all
```
