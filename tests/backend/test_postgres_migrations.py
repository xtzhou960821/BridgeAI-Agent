from __future__ import annotations

import psycopg
import pytest

from backend.app.repositories.postgres.migrate import MIGRATIONS_DIR, apply_migrations
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


@pytest.mark.postgres
def test_runtime_migration_ignores_same_named_constraints_on_other_tables(tmp_path):
    database_url = require_test_database_url()
    reset_test_tables(database_url)
    _apply_history_migrations(database_url, tmp_path)

    try:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "CREATE TABLE runtime_constraint_name_collision (value TEXT)",
            )
            for constraint_name in (
                "ck_inspection_task_runs_workflow_runtime",
                "ck_inspection_task_runs_checkpoint_thread_nonblank",
                "ck_inspection_task_runs_runtime_thread",
            ):
                connection.execute(
                    "ALTER TABLE runtime_constraint_name_collision "
                    f"ADD CONSTRAINT {constraint_name} CHECK (value IS NOT NULL)",
                )

        assert apply_migrations(database_url) == ["0003_langgraph_runtime.sql"]
        with psycopg.connect(database_url) as connection:
            target_constraints = {
                row[0]
                for row in connection.execute(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'public.inspection_task_runs'::regclass",
                ).fetchall()
            }
        assert target_constraints >= {
            "ck_inspection_task_runs_workflow_runtime",
            "ck_inspection_task_runs_checkpoint_thread_nonblank",
            "ck_inspection_task_runs_runtime_thread",
        }
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DROP TABLE IF EXISTS runtime_constraint_name_collision")
        reset_test_tables(database_url)


@pytest.mark.postgres
def test_runtime_migration_rejects_same_named_index_on_other_table(tmp_path):
    database_url = require_test_database_url()
    reset_test_tables(database_url)
    _apply_history_migrations(database_url, tmp_path)

    try:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "CREATE TABLE runtime_index_name_collision (value TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE UNIQUE INDEX uq_inspection_task_runs_checkpoint_thread "
                "ON runtime_index_name_collision (value)",
            )

        with pytest.raises(psycopg.errors.DuplicateTable):
            apply_migrations(database_url)
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DROP TABLE IF EXISTS runtime_index_name_collision")
        reset_test_tables(database_url)


def _apply_history_migrations(database_url: str, tmp_path) -> None:
    history_directory = tmp_path / "history_migrations"
    history_directory.mkdir()
    for filename in ("0001_v0_2_skeleton.sql", "0002_task_history.sql"):
        source = MIGRATIONS_DIR / filename
        (history_directory / filename).write_text(source.read_text(encoding="utf-8"))
    apply_migrations(database_url, history_directory)
