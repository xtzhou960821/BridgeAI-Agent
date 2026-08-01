"""Explicit PostgreSQL lifecycle helpers for LangGraph checkpoints."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Literal

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

from backend.app.repositories.postgres.connection import connect, get_database_url


CheckpointerStatus = Literal["ready", "not_initialized", "unavailable"]
REQUIRED_CHECKPOINT_TABLES = (
    "checkpoint_migrations",
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
)


@contextmanager
def open_postgres_checkpointer(database_url: str) -> Iterator[PostgresSaver]:
    """Open a PostgreSQL checkpointer without initializing its schema."""

    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        yield checkpointer


def setup_langgraph_checkpointer(database_url: str) -> None:
    """Explicitly create or upgrade the LangGraph checkpoint schema."""

    with open_postgres_checkpointer(database_url) as checkpointer:
        checkpointer.setup()


def probe_langgraph_checkpointer(database_url: str) -> CheckpointerStatus:
    """Report whether the explicit LangGraph checkpoint schema is ready."""

    if not database_url:
        return "unavailable"
    try:
        with connect(database_url) as connection:
            tables = connection.execute(
                "SELECT "
                "to_regclass('public.checkpoint_migrations'), "
                "to_regclass('public.checkpoints'), "
                "to_regclass('public.checkpoint_blobs'), "
                "to_regclass('public.checkpoint_writes')",
            ).fetchone()
    except psycopg.Error:
        return "unavailable"
    return "ready" if tables and all(tables) else "not_initialized"


def main() -> None:
    """Initialize the configured LangGraph checkpointer schema."""

    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("BRIDGEAI_DATABASE_URL is required")
    setup_langgraph_checkpointer(database_url)
    print("langgraph checkpointer ready")


if __name__ == "__main__":
    main()
