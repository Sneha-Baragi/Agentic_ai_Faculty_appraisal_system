# Lab 5: MCP-Style Connector (Mini Integration Layer)

- **Course:** Agentic AI (`26ECAC401`)
- **Lab:** 5
- **Topic:** Model Context Protocol (MCP) Style Connector & Multi-Source Agent Integration
- **Scenario:** Campus Data Integration Assistant
- **Repository Location:** `labs/Lab-05-MCP-Connector/`

---

## 1. Executive Summary

This laboratory implements a complete, self-contained **MCP-style integration layer** connecting an autonomous agent (`DataAssistant`) to heterogeneous data sources through a standardized capability discovery protocol, structured tool contracts, and robust permission boundaries.

The implementation strictly avoids external network calls, paid APIs, and third-party libraries, relying entirely on Python's standard library (`sqlite3`, `pathlib`, `dataclasses`, `json`, `re`).

### Key Highlights
- **Dynamic Capability Discovery:** The client queries the server manifest dynamically (`list_capabilities()`). No capability names or methods are hardcoded in the client interface.
- **Heterogeneous Adapters:** Integrates a local file resource (`safe_data/`), an embedded SQLite database (`signups` table), and a deterministic mock API service (`events_today`).
- **Resource vs. Tool Duality:** Standardizes read-only context resources (`read_file`, `list_files`) separately from callable action tools (`query_db`, `call_api`).
- **Strict Permission Boundaries:** Blocks directory traversal attacks (`../../backend/.env`, `C:\Windows\win.ini`), rejects SQL write mutations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`), prevents stacked injections, and requires authorized caller credentials.
- **Traceability & Auditability:** Every agent invocation generates a structured execution trace capturing the user request, discovered manifest, capability selection rationale, structured input/output, summary, and factual final answer.

---

## 2. Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                                 USER REQUEST                                      |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                           DataAssistant (Agent Layer)                             |
|  - Dynamically discovers manifest via MCPClient                                   |
|  - Selects appropriate capability (resource vs tool)                              |
|  - Formulates structured parameters matching input schema                         |
|  - Synthesizes grounded final answer without data fabrication                    |
|  - Maintains complete end-to-end execution audit trace                            |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                             MCPClient (Client Layer)                              |
|  - discover(): Queries server manifest and caches capability contracts            |
|  - call(name, **kwargs): Validates required input schema and dispatches           |
|  * ZERO hardcoded capability names or methods (fully dynamic)                     |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                             MCPServer (Server Layer)                              |
|  - Registry of Capability contracts (name, kind, schemas, handler binding)        |
|  - Dynamic registration / unregistration API                                     |
|  - Unified execute() dispatch routing to backend adapters                        |
+-----------------------------------------------------------------------------------+
       |                                  |                                  |
       v                                  v                                  v
+-----------------------+      +-----------------------+      +-----------------------+
|  FileResource Adapter |      |  DatabaseTool Adapter |      |  LocalApiTool Adapter |
|  (Resource)           |      |  (Tool)               |      |  (Tool)               |
|  - safe_data/ boundary|      |  - SQLite (campus.db) |      |  - Mock event feeds   |
|  - Blocks traversal   |      |  - Read-only SELECT   |      |  - Deterministic json |
|  - read_file          |      |  - Caller token check |      |  - events_today       |
|  - list_files (Assg 1)|      |  - query_db           |      |  - call_api           |
+-----------------------+      +-----------------------+      +-----------------------+
```

---

## 3. Directory Structure

```
labs/Lab-05-MCP-Connector/
│
├── agent/
│   ├── __init__.py               # Exports DataAssistant agent
│   └── data_assistant.py         # Autonomous assistant with intent router & trace logging
│
├── client/
│   ├── __init__.py               # Exports MCPClient
│   └── mcp_client.py             # Dynamic client with schema validation & discovery
│
├── server/
│   ├── __init__.py               # Exports MCPServer and backend adapters
│   ├── api_tool.py               # Local mock campus API tool
│   ├── capabilities.py           # Capability dataclass and default manifest contracts
│   ├── database_tool.py          # SQLite database tool with read-only locks & caller check
│   ├── file_resource.py          # Local file resource adapter with path traversal shield
│   └── mcp_server.py             # Central MCP server dispatch & registry
│
├── safe_data/
│   ├── README.md                 # Designated safe campus activities guide
│   └── announcements.txt         # Designated safe campus announcements
│
├── data/
│   └── campus.db                 # Auto-initialized SQLite database (signups table)
│
├── examples/
│   └── sample_requests.json      # Structured catalog of base, Assg 1, and Assg 2 test cases
│
├── tests/
│   ├── __init__.py
│   ├── test_agent.py             # Unit tests for DataAssistant intent routing & trace export
│   ├── test_client.py            # Unit tests for MCPClient discovery & schema enforcement
│   ├── test_security.py          # Unit tests for path traversal, SQL mutations, and authorization
│   └── test_server.py            # Unit tests for MCPServer dispatch & dynamic registration
│
├── main.py                       # CLI runner with --assignment1, --assignment2, and --all flags
├── requirements.txt              # Standard library declaration (zero external dependencies)
└── README.md                     # Comprehensive lab documentation
```

---

## 4. MCP Concepts Implemented

| MCP Concept | Implementation in Lab 5 |
| :--- | :--- |
| **Capability Discovery** | The client invokes `server.list_capabilities()` to retrieve structured schemas rather than hardcoding endpoints or functions. |
| **Structured Contracts** | Every capability is defined by a JSON Schema object for `input_schema` and `output_schema`, guaranteeing predictable payloads. |
| **Resource Classification** | Data sources like `read_file` and `list_files` are categorized as `"resource"`, representing contextual, read-only data. |
| **Tool Classification** | Data sources like `query_db` and `call_api` are categorized as `"tool"`, representing callable operational interfaces. |
| **Permission Boundaries** | Strict containment enforces that file operations cannot escape `safe_data/`, database operations cannot mutate rows, and API queries cannot invoke unwhitelisted endpoints. |
| **Traceability** | All capability selections, inputs, outputs, execution statuses, and generated answers are logged to an audit trace. |

---

## 5. Walkthrough of Base Requests

When executed via `python main.py`, the agent executes three diverse requests demonstrating all core capabilities:

### Request 1: Local File Resource (`read_file`)
- **User Request:** `"Read the README file."`
- **Capability Selected:** `read_file` (Kind: `resource`)
- **Reasoning:** User requested file contents; selected `read_file` resource targeting `README.md`.
- **Tool Input:**
  ```json
  {"file_path": "README.md"}
  ```
- **Tool Output (excerpt):**
  ```json
  {
    "status": "success",
    "file_name": "README.md",
    "size_bytes": 536,
    "relative_path": "README.md"
  }
  ```
- **Output Summary:** `Successfully read 'README.md' (536 bytes).`
- **Final Grounded Answer:**
  > Contents of README.md:
  > `# Campus Activities & Event Portal`
  > Welcome to the campus event management information guide...

---

### Request 2: SQLite Database Tool (`query_db`)
- **User Request:** `"Show me the campus event signup counts."`
- **Capability Selected:** `query_db` (Kind: `tool`)
- **Reasoning:** User requested structured signup counts; selected `query_db` tool to execute read-only SQL.
- **Tool Input:**
  ```json
  {
    "sql": "SELECT event, count FROM signups;",
    "caller_id": "data_assistant"
  }
  ```
- **Tool Output:**
  ```json
  {
    "status": "success",
    "columns": ["event", "count"],
    "rows": [
      {"event": "AI Club Talk", "count": 12},
      {"event": "Hackathon Kickoff", "count": 9},
      {"event": "Robotics Demo", "count": 15}
    ],
    "row_count": 3
  }
  ```
- **Output Summary:** `Database query returned 3 record(s).`
- **Final Grounded Answer:**
  > Here are the current campus event signup counts from the database:
  > - AI Club Talk: 12 signups
  > - Hackathon Kickoff: 9 signups
  > - Robotics Demo: 15 signups
  >
  > Total participants across all events: 36

---

### Request 3: Local Mock API Tool (`call_api`)
- **User Request:** `"Which events are happening today?"`
- **Capability Selected:** `call_api` (Kind: `tool`)
- **Reasoning:** User requested real-time campus schedule; selected `call_api` with endpoint `events_today`.
- **Tool Input:**
  ```json
  {
    "endpoint": "events_today",
    "params": {}
  }
  ```
- **Tool Output:**
  ```json
  {
    "status": "success",
    "endpoint": "events_today",
    "data": {
      "date": "Today",
      "total_events": 2,
      "events": [
        {"event": "AI Club Talk", "time": "14:00 - 15:30", "room": "Auditorium Hall B"},
        {"event": "Robotics Demo", "time": "16:00 - 17:30", "room": "Robotics Lab 204"}
      ]
    }
  }
  ```
- **Output Summary:** `API 'events_today' returned 2 scheduled events.`
- **Final Grounded Answer:**
  > Campus events scheduled for Today:
  > - AI Club Talk at 14:00 - 15:30 (Auditorium Hall B)
  > - Robotics Demo at 16:00 - 17:30 (Robotics Lab 204)

---

## 6. Assignment 1: Dynamic Discovery of 4th Capability (`list_files`)

### Implementation Details
Assignment 1 requires adding a 4th capability (`list_files`) as a `resource` and verifying that the `MCPClient` discovers and executes it **without hardcoding**:
1. Defined `LIST_FILES_CAPABILITY` in `server/capabilities.py` specifying input schema (`subdir`) and output schema (`files`, `file_count`).
2. Bound handler `file_resource.list_files` in `MCPServer`.
3. Verified `MCPClient` contains zero string references to `"list_files"` or methods named `list_files`.

### Execution
Run via CLI:
```bash
python main.py --assignment1
```

### Sample Output
```
==============================================================================
  ASSIGNMENT 1: DYNAMIC DISCOVERY OF 4TH CAPABILITY ('LIST_FILES')
==============================================================================
Requirement: Add 'list_files' resource. Client must discover and invoke dynamically
without any hardcoded 'list_files' methods or references in MCPClient.

Manifest verification: 'list_files' discovered = True
Capability Name : list_files
Capability Kind : resource (Resource)
Input Schema    : {"type": "object", "properties": {"subdir": {"type": "string", "description": "Optional relative subdirectory within safe_data/ to inspect", "default": ""}}, "required": []}
Output Schema   : {"type": "object", "properties": {"status": {"type": "string", "enum": ["success", "error"]}, "directory": {"type": "string"}, "file_count": {"type": "integer"}, "files": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "size_bytes": {"type": "integer"}, "extension": {"type": "string"}}}}}, "required": ["status"]}

--- [STEP 1] Agent Invoking Discovered 'list_files' Capability --------------
User Request        : "List the available files in safe_data."
Selected Capability : list_files (Kind: resource)
Tool Input          : {"subdir": ""}
Execution Success   : YES
Output Summary      : Discovered 2 accessible file(s) in safe boundary.
Final Answer        :
Accessible files in directory (.):
- announcements.txt (228 bytes)
- README.md (536 bytes)

[Assignment 1 Verification Passed]: 'list_files' was discovered and invoked dynamically.
```

---

## 7. Assignment 2: Safe Boundary Enforcement & Security Defenses

Assignment 2 hardens the integration layer by enforcing strict permission boundaries across file access, database queries, and API endpoints.

### 1. Safe Directory Boundary (`FileResource`)
- Safe boundary root: `labs/Lab-05-MCP-Connector/safe_data/`.
- Path resolution uses `Path(target).resolve()`.
- Enforces `target_resolved.relative_to(safe_dir)`.
- If the resolved path falls outside `safe_data/`, access is immediately aborted with `error_code: "PERMISSION_DENIED"`.
- Prevents system path disclosure: client-facing error messages never print absolute server directory paths.

#### Adversarial Probes Evaluated:
| Adversarial Probe | Description | Result | Error Code |
| :--- | :--- | :--- | :--- |
| `../../backend/.env` | Parent traversal to backend environment variables | **BLOCKED** | `PERMISSION_DENIED` |
| `../README.md` | Relative traversal to lab directory root | **BLOCKED** | `PERMISSION_DENIED` |
| `C:\Windows\win.ini` | Absolute Windows system file path | **BLOCKED** | `PERMISSION_DENIED` |
| `/some/unauthorized/file.txt` | Absolute Unix root path | **BLOCKED** | `PERMISSION_DENIED` |
| `non_existent.txt` | File inside `safe_data/` that does not exist | **FILE NOT FOUND** | `FILE_NOT_FOUND` |

### 2. Read-Only Database Locks (`DatabaseTool`)
- Uses SQLite read-only URI mode: `file:<path>?mode=ro`.
- Regex validation rejects mutation keywords: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `TRUNCATE`, `ATTACH`, `DETACH`, `VACUUM`, `PRAGMA`.
- Rejects stacked SQL injection queries containing semicolon separators (`SELECT * FROM signups; DROP TABLE signups;`).
- Rejects unauthorized caller tokens (`caller_id="intruder"` returns `UNAUTHORIZED_CALLER`).

### 3. API Endpoint Whitelist (`LocalApiTool`)
- Whitelisted endpoints: `events_today`, `event_details`, `system_status`.
- Requesting any unregistered endpoint returns structured error `ENDPOINT_NOT_FOUND`.

### Execution
Run via CLI:
```bash
python main.py --assignment2
```

---

## 8. Verification & Test Suite

The test suite contains **31 comprehensive unit tests** testing all layers independently and end-to-end.

### Running the Test Suite
From the lab directory:
```bash
python -m unittest discover -s tests -v
```

### Test Suite Breakdown
| Test Module | Tests | Focus Area |
| :--- | :---: | :--- |
| `tests/test_server.py` | 8 | Manifest listing, adapter execution, dynamic capability registration and unregistration. |
| `tests/test_client.py` | 6 | Dynamic manifest caching, input schema validation, dynamic execution, zero hardcoded `list_files` check. |
| `tests/test_agent.py` | 6 | Intent routing, tool input formulation, factual grounded answer synthesis, trace logging, unhandled query handling. |
| `tests/test_security.py` | 11 | Path traversal prevention, absolute path blocking, SQL write keyword rejection, stacked query rejection, caller token check, API whitelisting. |
| **Total** | **31** | **All Passed (0 failures, 0 errors, 0 skipped)** |

---

## 9. CLI Usage Guide

```bash
# 1. Run Base Demonstration (Requests 1, 2, 3 with trace summary)
python main.py

# 2. Run Assignment 1 (4th capability: list_files)
python main.py --assignment1

# 3. Run Assignment 2 (Security boundaries & adversarial probe defenses)
python main.py --assignment2

# 4. Run Full Demonstration (Base + Assignment 1 + Assignment 2)
python main.py --all

# 5. Interactive Assistant Shell
python main.py --interactive
```
