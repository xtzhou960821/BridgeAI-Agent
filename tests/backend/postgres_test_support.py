from __future__ import annotations

import os

import psycopg
from psycopg.conninfo import conninfo_to_dict


EXPECTED_TEST_DATABASE = "bridgeai_agent_test"


def require_test_database_url() -> str:
    url = os.environ.get("BRIDGEAI_TEST_DATABASE_URL", "").strip()
    _validate_test_database_url(
        url,
        "BRIDGEAI_TEST_DATABASE_URL must target bridgeai_agent_test",
    )
    return url


def reset_test_tables(database_url: str) -> None:
    _validate_test_database_url(
        database_url,
        "BRIDGEAI_TEST_DATABASE_URL must target bridgeai_agent_test",
    )
    with psycopg.connect(database_url) as connection:
        connection.execute(
            "DROP TABLE IF EXISTS inspection_artifacts, inspection_task_runs, "
            "inspection_tasks, bridgeai_schema_migrations CASCADE",
        )


def reset_langgraph_checkpoint_tables(database_url: str) -> None:
    _validate_test_database_url(
        database_url,
        "Checkpoint reset is restricted to bridgeai_agent_test",
    )
    with psycopg.connect(database_url) as connection:
        connection.execute(
            "DROP TABLE IF EXISTS checkpoint_writes, checkpoint_blobs, "
            "checkpoints, checkpoint_migrations CASCADE",
        )


def _validate_test_database_url(database_url: str, message: str) -> None:
    try:
        database_name = conninfo_to_dict(database_url).get("dbname", "")
    except psycopg.Error as error:
        raise RuntimeError(message) from error
    if database_name != EXPECTED_TEST_DATABASE:
        raise RuntimeError(message)
