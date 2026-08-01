"""Synchronous PostgreSQL repository for V0.2 task persistence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.app.domain.task_errors import (
    DatabaseUnavailableError,
    IdempotencyConflictError,
    TaskNotFoundError,
)
from backend.app.domain.tasks import TaskCreate, TaskRecord, TaskRunRecord
from backend.app.repositories.postgres.connection import connect


_TASK_COLUMNS = (
    "task_id, title, task_type, objective, artifact_ids, status, "
    "created_at, updated_at"
)
_RUN_COLUMNS = (
    "run_id, task_id, run_number, status, workflow_runtime, checkpoint_thread_id, "
    "agent_model, workflow, tool_results, error_message, started_at, completed_at"
)


class PostgresTaskRepository:
    """Store tasks and immutable-identity run snapshots in PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def create_task(
        self,
        task_id: str,
        command: TaskCreate,
        idempotency_key: str | None,
    ) -> TaskRecord:
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    if idempotency_key is not None:
                        cursor.execute(
                            f"SELECT {_TASK_COLUMNS} FROM inspection_tasks "
                            "WHERE idempotency_key = %s",
                            (idempotency_key,),
                        )
                        existing = cursor.fetchone()
                        if existing is not None:
                            record = _task_from_row(existing)
                            if _task_matches(record, command):
                                return record
                            raise IdempotencyConflictError(
                                "Idempotency key was reused with different task input",
                            )
                    cursor.execute(
                        "INSERT INTO inspection_tasks ("
                        "task_id, title, task_type, objective, artifact_ids, status, "
                        "idempotency_key"
                        ") VALUES (%s, %s, %s, %s, %s, 'draft', %s) "
                        f"RETURNING {_TASK_COLUMNS}",
                        (
                            task_id,
                            command.title,
                            command.task_type,
                            command.objective,
                            Jsonb(command.artifact_ids),
                            idempotency_key,
                        ),
                    )
                    return _task_from_row(cursor.fetchone())
        except psycopg.Error as exc:
            raise _database_unavailable() from exc

    def list_tasks(self, limit: int = 50) -> list[TaskRecord]:
        bounded_limit = min(max(limit, 1), 50)
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"SELECT {_TASK_COLUMNS} FROM inspection_tasks "
                        "ORDER BY updated_at DESC, task_id DESC LIMIT %s",
                        (bounded_limit,),
                    )
                    return [_task_from_row(row) for row in cursor.fetchall()]
        except psycopg.Error as exc:
            raise _database_unavailable() from exc

    def get_task(self, task_id: str) -> TaskRecord:
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"SELECT {_TASK_COLUMNS} FROM inspection_tasks "
                        "WHERE task_id = %s",
                        (task_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise TaskNotFoundError(f"Task {task_id} was not found")
                    return _task_from_row(row)
        except psycopg.Error as exc:
            raise _database_unavailable() from exc

    def start_run(
        self,
        task_id: str,
        run_id: str,
        *,
        workflow_runtime: str = "legacy",
        checkpoint_thread_id: str | None = None,
    ) -> TaskRunRecord:
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT task_id FROM inspection_tasks "
                        "WHERE task_id = %s FOR UPDATE",
                        (task_id,),
                    )
                    if cursor.fetchone() is None:
                        raise TaskNotFoundError(f"Task {task_id} was not found")
                    cursor.execute(
                        "SELECT COALESCE(MAX(run_number), 0) + 1 AS run_number "
                        "FROM inspection_task_runs WHERE task_id = %s",
                        (task_id,),
                    )
                    run_number = int(cursor.fetchone()["run_number"])
                    cursor.execute(
                        "INSERT INTO inspection_task_runs ("
                        "run_id, task_id, run_number, status, workflow_runtime, "
                        "checkpoint_thread_id"
                        ") VALUES (%s, %s, %s, 'running', %s, %s) "
                        f"RETURNING {_RUN_COLUMNS}",
                        (
                            run_id,
                            task_id,
                            run_number,
                            workflow_runtime,
                            checkpoint_thread_id,
                        ),
                    )
                    run = _run_from_row(cursor.fetchone())
                    cursor.execute(
                        "UPDATE inspection_tasks "
                        "SET status = 'running', updated_at = NOW() "
                        "WHERE task_id = %s",
                        (task_id,),
                    )
                    return run
        except psycopg.Error as exc:
            raise _database_unavailable() from exc

    def complete_run(
        self,
        run_id: str,
        agent_model: dict[str, object],
        workflow: dict[str, object],
        tool_results: list[dict[str, object]],
    ) -> TaskRunRecord:
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "UPDATE inspection_task_runs SET "
                        "status = 'completed', agent_model = %s, workflow = %s, "
                        "tool_results = %s, error_message = NULL, completed_at = NOW() "
                        "WHERE run_id = %s "
                        f"RETURNING {_RUN_COLUMNS}",
                        (
                            Jsonb(agent_model),
                            Jsonb(workflow),
                            Jsonb(tool_results),
                            run_id,
                        ),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise TaskNotFoundError(f"Run {run_id} was not found")
                    run = _run_from_row(row)
                    cursor.execute(
                        "UPDATE inspection_tasks "
                        "SET status = 'completed', updated_at = NOW() "
                        "WHERE task_id = %s",
                        (run.task_id,),
                    )
                    return run
        except psycopg.Error as exc:
            raise _database_unavailable() from exc

    def fail_run(
        self,
        run_id: str,
        error_message: str,
        *,
        agent_model: dict[str, object] | None = None,
        workflow: dict[str, object] | None = None,
        tool_results: list[dict[str, object]] | None = None,
    ) -> TaskRunRecord:
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "UPDATE inspection_task_runs SET "
                        "status = 'failed', agent_model = COALESCE(%s, agent_model), "
                        "workflow = COALESCE(%s, workflow), "
                        "tool_results = COALESCE(%s, tool_results), "
                        "error_message = %s, completed_at = NOW() "
                        "WHERE run_id = %s "
                        f"RETURNING {_RUN_COLUMNS}",
                        (
                            Jsonb(agent_model) if agent_model is not None else None,
                            Jsonb(workflow) if workflow is not None else None,
                            Jsonb(tool_results) if tool_results is not None else None,
                            error_message,
                            run_id,
                        ),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise TaskNotFoundError(f"Run {run_id} was not found")
                    run = _run_from_row(row)
                    cursor.execute(
                        "UPDATE inspection_tasks "
                        "SET status = 'failed', updated_at = NOW() "
                        "WHERE task_id = %s",
                        (run.task_id,),
                    )
                    return run
        except psycopg.Error as exc:
            raise _database_unavailable() from exc

    def list_runs(self, task_id: str) -> list[TaskRunRecord]:
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT task_id FROM inspection_tasks WHERE task_id = %s",
                        (task_id,),
                    )
                    if cursor.fetchone() is None:
                        raise TaskNotFoundError(f"Task {task_id} was not found")
                    cursor.execute(
                        f"SELECT {_RUN_COLUMNS} FROM inspection_task_runs "
                        "WHERE task_id = %s ORDER BY run_number DESC",
                        (task_id,),
                    )
                    return [_run_from_row(row) for row in cursor.fetchall()]
        except psycopg.Error as exc:
            raise _database_unavailable() from exc


def _task_matches(record: TaskRecord, command: TaskCreate) -> bool:
    return (
        record.title == command.title
        and record.task_type == command.task_type
        and record.objective == command.objective
        and record.artifact_ids == command.artifact_ids
    )


def _task_from_row(row: Mapping[str, Any]) -> TaskRecord:
    return TaskRecord(
        task_id=str(row["task_id"]),
        title=str(row["title"]),
        task_type=str(row["task_type"]),
        objective=str(row["objective"]),
        artifact_ids=list(row["artifact_ids"]),
        status=str(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _run_from_row(row: Mapping[str, Any]) -> TaskRunRecord:
    return TaskRunRecord(
        run_id=str(row["run_id"]),
        task_id=str(row["task_id"]),
        run_number=int(row["run_number"]),
        status=str(row["status"]),
        workflow_runtime=str(row["workflow_runtime"]),
        checkpoint_thread_id=(
            str(row["checkpoint_thread_id"])
            if row["checkpoint_thread_id"] is not None
            else None
        ),
        agent_model=dict(row["agent_model"]),
        workflow=dict(row["workflow"]),
        tool_results=[dict(item) for item in row["tool_results"]],
        error_message=(
            str(row["error_message"]) if row["error_message"] is not None else None
        ),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _database_unavailable() -> DatabaseUnavailableError:
    return DatabaseUnavailableError("PostgreSQL task store is unavailable")
