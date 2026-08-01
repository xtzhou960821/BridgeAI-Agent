"""Application service for persistent task creation and execution."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping

from agent.model_gateway import ModelGatewayConfigurationError
from backend.app.domain.task_errors import (
    DatabaseUnavailableError,
    TaskExecutionError,
    TaskInputConflictError,
    TaskNotFoundError,
)
from backend.app.domain.tasks import (
    TaskCreate,
    TaskRecord,
    TaskRepository,
    TaskRunRecord,
)
from backend.app.repositories.postgres.connection import get_database_url
from backend.app.repositories.postgres.tasks import PostgresTaskRepository
from backend.app.services.task_runs import run_inspection_task


RunInspection = Callable[[dict[str, object]], dict[str, object]]


class TaskService:
    """Coordinate task persistence with the existing Agent execution path."""

    def __init__(
        self,
        repository: TaskRepository,
        run_inspection: RunInspection,
    ) -> None:
        self._repository = repository
        self._run_inspection = run_inspection

    def create_task(
        self,
        command: TaskCreate,
        idempotency_key: str | None = None,
    ) -> TaskRecord:
        return self._repository.create_task(
            _new_id("task"),
            command,
            idempotency_key,
        )

    def list_tasks(self) -> list[TaskRecord]:
        return self._repository.list_tasks(limit=50)

    def get_task(self, task_id: str) -> TaskRecord:
        return self._repository.get_task(task_id)

    def list_runs(self, task_id: str) -> list[TaskRunRecord]:
        return self._repository.list_runs(task_id)

    def execute_task(self, task_id: str) -> TaskRunRecord:
        task = self._repository.get_task(task_id)
        started = self._repository.start_run(task_id, _new_id("run"))
        payload: dict[str, object] = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "objective": task.objective,
            "artifact_ids": task.artifact_ids,
        }
        try:
            result = self._run_inspection(payload)
            return self._repository.complete_run(
                started.run_id,
                dict(result["agent_model"]),
                dict(result["workflow"]),
                [dict(item) for item in result["tool_results"]],
            )
        except ModelGatewayConfigurationError as exc:
            self._repository.fail_run(started.run_id, _sanitize_error(exc))
            raise
        except Exception as exc:
            message = _sanitize_error(exc)
            self._repository.fail_run(started.run_id, message)
            raise TaskExecutionError(started.run_id, message) from exc

    def execute_legacy_task(
        self,
        task_id: str,
        command: TaskCreate,
    ) -> TaskRunRecord:
        try:
            task = self._repository.get_task(task_id)
        except TaskNotFoundError:
            task = self._repository.create_task(task_id, command, None)
        if not _execution_input_matches(task, command):
            raise TaskInputConflictError(
                "Persisted task input differs from the compatibility request",
            )
        return self.execute_task(task.task_id)


def build_task_service_from_environment(
    environ: Mapping[str, str] | None = None,
) -> TaskService:
    """Build the persistent task service without eagerly connecting."""

    database_url = get_database_url(environ)
    if not database_url:
        raise DatabaseUnavailableError("PostgreSQL task store is unavailable")
    return TaskService(
        PostgresTaskRepository(database_url),
        run_inspection=run_inspection_task,
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _execution_input_matches(task: TaskRecord, command: TaskCreate) -> bool:
    return (
        task.task_type == command.task_type
        and task.objective == command.objective
        and task.artifact_ids == command.artifact_ids
    )


def _sanitize_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    message = re.sub(r"Bearer\s+\S+", "Bearer ***", message, flags=re.IGNORECASE)
    message = re.sub(
        r"(postgresql(?:\+\w+)?://)[^@\s]+@",
        r"\1***@",
        message,
        flags=re.IGNORECASE,
    )
    return message[:500]
