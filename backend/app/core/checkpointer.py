"""SEC-02: PostgreSQL-backed LangGraph checkpointer lifecycle and connection management."""

from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import get_settings

_pool: Optional[ConnectionPool] = None
_saver: Optional[PostgresSaver] = None


def is_postgres_url(url: str) -> bool:
    """Check whether a database URL targets PostgreSQL."""
    clean = (url or "").strip().lower()
    return (
        clean.startswith("postgresql://")
        or clean.startswith("postgresql+psycopg://")
        or clean.startswith("postgres://")
    )


def is_sqlite_url(url: str) -> bool:
    """Check whether a database URL targets SQLite."""
    clean = (url or "").strip().lower()
    return clean.startswith("sqlite://") or clean.startswith("sqlite:///")


def clean_pg_url(url: str) -> str:
    """Normalize SQLAlchemy dialect URLs for psycopg3."""
    clean = (url or "").strip()
    if clean.startswith("postgresql+psycopg://"):
        return "postgresql://" + clean[len("postgresql+psycopg://") :]
    return clean


def get_checkpointer_pool() -> ConnectionPool:
    """Returns the singleton ConnectionPool created with open=False.

    Zero network connections or database queries are made at instantiation.
    """
    global _pool
    if _pool is None:
        settings = get_settings()
        dsn = clean_pg_url(settings.database_url)
        _pool = ConnectionPool(
            conninfo=dsn,
            open=False,
            min_size=1,
            max_size=20,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
    return _pool


def get_postgres_saver() -> PostgresSaver:
    """Instantiates the official PostgresSaver backed by the deferred connection pool."""
    global _saver
    if _saver is None:
        _saver = PostgresSaver(get_checkpointer_pool())
    return _saver


def init_checkpointer() -> None:
    """FastAPI startup: opens connection pool and initializes checkpoint tables.

    Fail-closed: If PostgreSQL is configured and initialization fails at any point
    (connection, pool opening, or table setup), the pool is cleaned up safely and
    a fatal RuntimeError is raised unconditionally. Zero fallback to MemorySaver.
    """
    settings = get_settings()
    url = (settings.database_url or "").strip()

    if is_postgres_url(url):
        pool = get_checkpointer_pool()
        opened = False
        try:
            pool.open()
            opened = True
            saver = get_postgres_saver()
            saver.setup()
        except Exception as exc:
            if opened:
                try:
                    pool.close()
                except Exception:
                    pass
            close_checkpointer()
            raise RuntimeError(
                f"Fail-closed: Unable to initialize durable PostgreSQL checkpointer ({exc}). "
                "Aborting startup."
            ) from exc


def close_checkpointer() -> None:
    """FastAPI shutdown: closes all pool connections cleanly and resets globals."""
    global _pool, _saver
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
        finally:
            _pool = None
            _saver = None
