from __future__ import annotations

import psycopg
import pytest

from backend.app.repositories.postgres.migrate import apply_migrations
from tests.backend.postgres_test_support import (
    require_test_database_url,
    reset_test_tables,
)


@pytest.mark.postgres
def test_migrations_apply_in_order_and_are_repeatable():
    database_url = require_test_database_url()
    reset_test_tables(database_url)

    first = apply_migrations(database_url)
    second = apply_migrations(database_url)

    assert first == [
        "0001_v0_2_skeleton.sql",
        "0002_task_history.sql",
        "0003_langgraph_runtime.sql",
    ]
    assert second == []
    with psycopg.connect(database_url) as connection:
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = 'inspection_task_runs'",
        ).fetchall()
    assert {row[0] for row in columns} >= {
        "run_id",
        "task_id",
        "run_number",
        "status",
        "agent_model",
        "workflow",
        "tool_results",
        "error_message",
        "started_at",
        "completed_at",
        "workflow_runtime",
        "checkpoint_thread_id",
    }
    with psycopg.connect(database_url) as connection:
        connection.execute(
            "INSERT INTO inspection_tasks "
            "(task_id, task_type, objective, title, status) "
            "VALUES ('task_legacy', 'bridge_inspection', '检查影像', '桥梁巡检', 'draft')",
        )
        connection.execute(
            "INSERT INTO inspection_task_runs (run_id, task_id, run_number, status) "
            "VALUES ('run_legacy', 'task_legacy', 1, 'running')",
        )
        legacy_run = connection.execute(
            "SELECT workflow_runtime, checkpoint_thread_id "
            "FROM inspection_task_runs WHERE run_id = 'run_legacy'",
        ).fetchone()
    assert legacy_run == ("legacy", None)
