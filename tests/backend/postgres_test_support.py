from __future__ import annotations

import os
from urllib.parse import urlparse

import psycopg


EXPECTED_TEST_DATABASE = "bridgeai_agent_test"


def require_test_database_url() -> str:
    url = os.environ.get("BRIDGEAI_TEST_DATABASE_URL", "").strip()
    if urlparse(url).path.lstrip("/") != EXPECTED_TEST_DATABASE:
        raise RuntimeError(
            "BRIDGEAI_TEST_DATABASE_URL must target bridgeai_agent_test",
        )
    return url


def reset_test_tables(database_url: str) -> None:
    with psycopg.connect(database_url) as connection:
        connection.execute(
            "DROP TABLE IF EXISTS inspection_task_runs, "
            "inspection_tasks, bridgeai_schema_migrations CASCADE",
        )
