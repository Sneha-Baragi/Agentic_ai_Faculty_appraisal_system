"""SQLite Database Tool with Read-Only Security Enforcement.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Scenario: Campus Events Database

Provides read-only access to the campus events database (signups table).
Enforces caller authorization and strictly rejects write/mutation operations
(DELETE, INSERT, UPDATE, DROP, ALTER, CREATE, TRUNCATE, etc.).
"""

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Authorized callers permitted to query the database
DEFAULT_AUTHORIZED_CALLERS: Set[str] = {
    "authorized_caller",
    "data_assistant",
    "admin_agent",
    "campus_coordinator",
}

# SQL write and mutation statements strictly prohibited in read-only mode
FORBIDDEN_SQL_KEYWORDS = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bREPLACE\b",
    r"\bTRUNCATE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bVACUUM\b",
    r"\bREINDEX\b",
    r"\bPRAGMA\b",
]


class DatabaseTool:
    """Tool that executes read-only SQL queries against the campus SQLite database."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        authorized_callers: Optional[Set[str]] = None,
    ) -> None:
        if db_path is None:
            # Default to data/campus.db relative to Lab 5 directory
            lab_root = Path(__file__).resolve().parent.parent
            self.db_path = lab_root / "data" / "campus.db"
        else:
            self.db_path = Path(db_path)

        self.authorized_callers = authorized_callers or DEFAULT_AUTHORIZED_CALLERS
        self.ensure_database_initialized()

    def ensure_database_initialized(self) -> None:
        """Create parent directory, initialize SQLite schema, and populate seed data."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL UNIQUE,
                    count INTEGER NOT NULL
                );
            """)
            # Insert official seed data if table is currently empty
            cursor.execute("SELECT COUNT(*) FROM signups;")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.executemany(
                    "INSERT INTO signups (event, count) VALUES (?, ?);",
                    [
                        ("AI Club Talk", 12),
                        ("Hackathon Kickoff", 9),
                        ("Robotics Demo", 15),
                    ],
                )
                conn.commit()
        finally:
            conn.close()

    def is_caller_authorized(self, caller_id: Optional[str]) -> bool:
        """Verify whether caller is permitted to execute database operations."""
        if not caller_id:
            return False
        return caller_id in self.authorized_callers

    def validate_read_only_query(self, sql: str) -> Optional[str]:
        """Verify that the SQL query is strictly a read-only SELECT statement.

        Returns:
            None if valid, or an error message string if prohibited.
        """
        cleaned_sql = sql.strip()
        if not cleaned_sql:
            return "Query string is empty."

        # Check for prohibited write keywords
        for pattern in FORBIDDEN_SQL_KEYWORDS:
            if re.search(pattern, cleaned_sql, re.IGNORECASE):
                matched = re.search(pattern, cleaned_sql, re.IGNORECASE).group(0).upper()  # type: ignore
                return f"Forbidden operation: '{matched}' statements are prohibited in read-only mode."

        # Must start with SELECT or EXPLAIN
        if not re.match(r"^(SELECT|EXPLAIN)\b", cleaned_sql, re.IGNORECASE):
            return "Prohibited query: only read-only SELECT statements are permitted."

        return None

    def query(
        self,
        sql: str,
        caller_id: str = "data_assistant",
    ) -> Dict[str, Any]:
        """Execute a read-only query on the campus database.

        Args:
            sql: SQL statement string.
            caller_id: Identifier of the invoking caller.

        Returns:
            Structured dictionary response indicating success or structured error.
        """
        # 1. Caller Authorization Check
        if not self.is_caller_authorized(caller_id):
            return {
                "status": "error",
                "error_code": "UNAUTHORIZED_CALLER",
                "message": (
                    f"Caller authorization failed: '{caller_id}' is not authorized "
                    "to access the campus database."
                ),
            }

        # 2. Read-Only Query Validation
        validation_error = self.validate_read_only_query(sql)
        if validation_error:
            return {
                "status": "error",
                "error_code": "PERMISSION_DENIED",
                "message": f"Read-only access violation: {validation_error}",
            }

        # 3. Safe Execution
        try:
            # Connect in read-only URI mode to enforce database-level protection
            uri_path = f"file:{self.db_path.resolve()}?mode=ro"
            conn = sqlite3.connect(uri_path, uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows_raw = cursor.fetchall()

            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = [dict(row) for row in rows_raw]
            conn.close()

            return {
                "status": "success",
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "query": sql,
            }

        except sqlite3.OperationalError as err:
            return {
                "status": "error",
                "error_code": "DATABASE_ERROR",
                "message": f"SQLite operational error: {str(err)}",
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "EXECUTION_ERROR",
                "message": f"Unexpected error during query execution: {str(exc)}",
            }
