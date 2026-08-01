"""PostgreSQL connection and readiness helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping

import psycopg


def get_database_url(environ: Mapping[str, str] | None = None) -> str:
    """Return the configured PostgreSQL URL without logging it."""

    source = os.environ if environ is None else environ
    return source.get("BRIDGEAI_DATABASE_URL", "").strip()


def connect(database_url: str):
    """Open a psycopg connection for the supplied database URL."""

    return psycopg.connect(database_url)


def probe_database(database_url: str) -> bool:
    """Report whether PostgreSQL and the V0.2 task tables are ready."""

    if not database_url:
        return False
    try:
        with connect(database_url) as connection:
            tables = connection.execute(
                "SELECT to_regclass('public.inspection_tasks'), "
                "to_regclass('public.inspection_task_runs')",
            ).fetchone()
        return bool(tables and all(tables))
    except psycopg.Error:
        return False
