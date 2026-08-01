"""Persistent FastAPI task routes for V0.2 local development."""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn, TypeVar

from agent.model_gateway import ModelGatewayConfigurationError
from backend.app.domain.task_errors import (
    DatabaseUnavailableError,
    IdempotencyConflictError,
    TaskExecutionError,
    TaskInputConflictError,
    TaskNotFoundError,
)
from backend.app.domain.tasks import TaskCreate
from backend.app.services.tasks import (
    TaskService,
    build_task_service_from_environment,
)

try:
    from fastapi import APIRouter, Header, HTTPException, status
except ModuleNotFoundError:  # pragma: no cover - depends on optional runtime dependency.
    APIRouter = None  # type: ignore[assignment]
    Header = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    status = None  # type: ignore[assignment]


_Result = TypeVar("_Result")


if APIRouter is not None:
    from pydantic import BaseModel, Field, field_validator

    class TaskCreateRequest(BaseModel):
        title: str = Field(min_length=1, max_length=200)
        task_type: str = Field(min_length=1, max_length=100)
        objective: str = Field(min_length=1, max_length=2000)
        artifact_ids: list[str] = Field(min_length=1, max_length=100)

        @field_validator("title", "task_type", "objective")
        @classmethod
        def strip_nonblank_text(cls, value: str) -> str:
            normalized = value.strip()
            if not normalized:
                raise ValueError("value must not be blank")
            return normalized

        @field_validator("artifact_ids")
        @classmethod
        def normalize_artifact_ids(cls, values: list[str]) -> list[str]:
            normalized = [value.strip() for value in values]
            if any(not value for value in normalized):
                raise ValueError("artifact_ids must not contain blank values")
            return normalized

        def as_command(self) -> TaskCreate:
            return TaskCreate(
                title=self.title,
                task_type=self.task_type,
                objective=self.objective,
                artifact_ids=self.artifact_ids,
            )

    class LegacyTaskRunRequest(BaseModel):
        task_id: str = Field(min_length=1, max_length=200)
        task_type: str = Field(min_length=1, max_length=100)
        objective: str = Field(min_length=1, max_length=2000)
        artifact_ids: list[str] = Field(min_length=1, max_length=100)

        @field_validator("task_id", "task_type", "objective")
        @classmethod
        def strip_nonblank_text(cls, value: str) -> str:
            normalized = value.strip()
            if not normalized:
                raise ValueError("value must not be blank")
            return normalized

        @field_validator("artifact_ids")
        @classmethod
        def normalize_artifact_ids(cls, values: list[str]) -> list[str]:
            normalized = [value.strip() for value in values]
            if any(not value for value in normalized):
                raise ValueError("artifact_ids must not contain blank values")
            return normalized

        def as_command(self) -> TaskCreate:
            return TaskCreate(
                title=self.objective,
                task_type=self.task_type,
                objective=self.objective,
                artifact_ids=self.artifact_ids,
            )

    router = APIRouter(prefix="/tasks", tags=["tasks"])

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_task(
        request: TaskCreateRequest,
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
    ) -> dict[str, object]:
        return _service_call(
            lambda service: service.create_task(
                request.as_command(),
                idempotency_key=idempotency_key,
            ).as_payload(),
        )

    @router.get("")
    def list_tasks() -> dict[str, object]:
        return _service_call(
            lambda service: {
                "items": [item.as_payload() for item in service.list_tasks()],
            },
        )

    @router.post("/runs", status_code=status.HTTP_201_CREATED)
    def run_legacy_task(request: LegacyTaskRunRequest) -> dict[str, object]:
        return _service_call(
            lambda service: service.execute_legacy_task(
                request.task_id,
                request.as_command(),
            ).as_payload(),
        )

    @router.get("/{task_id}")
    def get_task(task_id: str) -> dict[str, object]:
        return _service_call(
            lambda service: service.get_task(task_id).as_payload(),
        )

    @router.post("/{task_id}/runs", status_code=status.HTTP_201_CREATED)
    def run_task(task_id: str) -> dict[str, object]:
        return _service_call(
            lambda service: service.execute_task(task_id).as_payload(),
        )

    @router.get("/{task_id}/runs")
    def list_task_runs(task_id: str) -> dict[str, object]:
        return _service_call(
            lambda service: {
                "items": [
                    item.as_payload() for item in service.list_runs(task_id)
                ],
            },
        )
else:
    router = None


def _service_call(operation: Callable[[TaskService], _Result]) -> _Result:
    try:
        return operation(build_task_service_from_environment())
    except (
        TaskNotFoundError,
        IdempotencyConflictError,
        TaskInputConflictError,
        DatabaseUnavailableError,
        ModelGatewayConfigurationError,
        TaskExecutionError,
    ) as exc:
        _raise_http_error(exc)


def _raise_http_error(exc: Exception) -> NoReturn:
    if HTTPException is None:  # pragma: no cover - FastAPI-only path.
        raise RuntimeError("FastAPI is not installed") from exc
    if isinstance(exc, TaskNotFoundError):
        status_code = 404
        detail = {"code": "TASK_NOT_FOUND", "message": "未找到指定任务。"}
    elif isinstance(exc, IdempotencyConflictError):
        status_code = 409
        detail = {
            "code": "IDEMPOTENCY_CONFLICT",
            "message": "该幂等键已用于不同的任务内容。",
        }
    elif isinstance(exc, TaskInputConflictError):
        status_code = 409
        detail = {
            "code": "TASK_INPUT_CONFLICT",
            "message": "该任务 ID 已存在，但执行输入不一致。",
        }
    elif isinstance(exc, DatabaseUnavailableError):
        status_code = 503
        detail = {
            "code": "DATABASE_UNAVAILABLE",
            "message": "PostgreSQL 任务存储当前不可用，请检查配置、连接和迁移状态。",
        }
    elif isinstance(exc, ModelGatewayConfigurationError):
        status_code = 503
        detail = {
            "code": "MODEL_GATEWAY_NOT_CONFIGURED",
            "message": (
                "模型网关未配置：请在后端启动环境中设置 BRIDGEAI_AGENT_API_KEY，"
                "或将 BRIDGEAI_AGENT_MODEL_IS_STUB=true 用于本地演示。"
            ),
        }
    else:
        status_code = 502
        detail = {
            "code": "TASK_EXECUTION_FAILED",
            "message": "任务执行失败，可在执行历史中查看失败记录。",
            "run_id": exc.run_id,
        }
    raise HTTPException(status_code=status_code, detail=detail) from exc
