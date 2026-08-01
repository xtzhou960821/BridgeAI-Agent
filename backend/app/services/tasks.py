"""Application service for persistent task creation and execution."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping
from functools import partial

from agent.model_gateway import ModelGatewayConfigurationError
from backend.app.domain.artifact_errors import ArtifactNotReadyError
from backend.app.domain.artifacts import ArtifactRecord
from backend.app.domain.task_errors import (
    DatabaseUnavailableError,
    LangGraphCheckpointerNotReadyError,
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
from backend.app.services.artifacts import build_artifact_service_from_environment
from backend.app.services.task_runs import run_inspection_task


RunInspection = Callable[[str, dict[str, object]], dict[str, object]]
RequireReadyArtifact = Callable[[str], ArtifactRecord]
_POSTGRES_URI_CREDENTIALS = re.compile(
    r"\b(postgres(?:ql)?(?:\+[a-z0-9_.-]+)?://)[^/@\s?#]+@",
    flags=re.IGNORECASE,
)
_KEYWORD_DSN_PASSWORD = re.compile(
    r"(?<![a-z0-9_])(password\s*=\s*)"
    r"(?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|(?:\\.|[^\s])+)",
    flags=re.IGNORECASE,
)


class TaskService:
    """Coordinate task persistence with the existing Agent execution path."""

    def __init__(
        self,
        repository: TaskRepository,
        run_inspection: RunInspection,
        require_ready_artifact: RequireReadyArtifact,
    ) -> None:
        self._repository = repository
        self._run_inspection = run_inspection
        self._require_ready_artifact = require_ready_artifact

    def create_task(
        self,
        command: TaskCreate,
        idempotency_key: str | None = None,
    ) -> TaskRecord:
        self._validate_new_task_artifact(command)
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
        run_id = _new_id("run")
        started = self._repository.start_run(
            task_id,
            run_id,
            workflow_runtime="langgraph",
            checkpoint_thread_id=run_id,
        )
        payload: dict[str, object] = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "objective": task.objective,
            "artifact_ids": task.artifact_ids,
        }
        try:
            result = self._run_inspection(run_id, payload)
            agent_model = dict(result["agent_model"])
            workflow = dict(result["workflow"])
            tool_results = [dict(item) for item in result["tool_results"]]
            if result["status"] == "completed":
                return self._repository.complete_run(
                    started.run_id,
                    agent_model,
                    workflow,
                    tool_results,
                )
            if result["status"] == "failed":
                return self._repository.fail_run(
                    started.run_id,
                    _graph_failure_message(workflow, tool_results),
                    agent_model=agent_model,
                    workflow=workflow,
                    tool_results=tool_results,
                )
            raise TaskExecutionError(
                started.run_id,
                f"Unsupported graph terminal status: {result['status']}",
            )
        except LangGraphCheckpointerNotReadyError as exc:
            self._repository.fail_run(started.run_id, _sanitize_error(exc))
            raise
        except ModelGatewayConfigurationError as exc:
            self._repository.fail_run(started.run_id, _sanitize_error(exc))
            raise
        except TaskExecutionError as exc:
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
            self._validate_new_task_artifact(command)
            task = self._repository.create_task(task_id, command, None)
        if not _execution_input_matches(task, command):
            raise TaskInputConflictError(
                "Persisted task input differs from the compatibility request",
            )
        return self.execute_task(task.task_id)

    def _validate_new_task_artifact(self, command: TaskCreate) -> None:
        if len(command.artifact_ids) != 1:
            raise ArtifactNotReadyError("Exactly one ready Artifact is required")
        self._require_ready_artifact(command.artifact_ids[0])


def build_task_service_from_environment(
    environ: Mapping[str, str] | None = None,
) -> TaskService:
    """Build the persistent task service without eagerly connecting."""

    database_url = get_database_url(environ)
    if not database_url:
        raise DatabaseUnavailableError("PostgreSQL task store is unavailable")
    artifact_service = build_artifact_service_from_environment(environ)
    return TaskService(
        PostgresTaskRepository(database_url),
        run_inspection=partial(run_inspection_task, database_url=database_url),
        require_ready_artifact=artifact_service.require_ready,
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
    message = _POSTGRES_URI_CREDENTIALS.sub(r"\1***@", message)
    message = _KEYWORD_DSN_PASSWORD.sub(r"\1***", message)
    return message[:500]


def _graph_failure_message(
    workflow: dict[str, object],
    tool_results: list[dict[str, object]],
) -> str:
    workflow_message = workflow.get("error_message")
    if isinstance(workflow_message, str) and workflow_message.strip():
        return workflow_message.strip()
    for tool_result in tool_results:
        if tool_result.get("ok") is False:
            tool_message = tool_result.get("error_message")
            if isinstance(tool_message, str) and tool_message.strip():
                return tool_message.strip()
    return "workflow failed"
