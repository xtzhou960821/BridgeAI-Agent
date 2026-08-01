from __future__ import annotations

from datetime import UTC, datetime

import pytest

try:
    from fastapi.testclient import TestClient
except (ModuleNotFoundError, RuntimeError) as exc:
    pytest.skip(f"FastAPI test client is not available: {exc}", allow_module_level=True)

from agent.model_gateway import ModelGatewayConfigurationError
from backend.app.domain.task_errors import (
    DatabaseUnavailableError,
    IdempotencyConflictError,
    TaskExecutionError,
    TaskInputConflictError,
    TaskNotFoundError,
)
from backend.app.domain.tasks import TaskRecord, TaskRunRecord
from backend.app.main import create_app


def test_create_list_detail_run_and_history_routes(monkeypatch):
    from backend.app.api.v1 import tasks

    service = _FakeTaskService()
    monkeypatch.setattr(
        tasks,
        "build_task_service_from_environment",
        lambda: service,
    )
    client = TestClient(create_app())

    created = client.post(
        "/api/v1/tasks",
        headers={"Idempotency-Key": "create-alpha"},
        json={
            "title": "桥梁巡检",
            "task_type": "bridge_inspection",
            "objective": "检查无人机影像",
            "artifact_ids": ["art_001"],
        },
    )
    listed = client.get("/api/v1/tasks")
    detail = client.get("/api/v1/tasks/task_001")
    run = client.post("/api/v1/tasks/task_001/runs")
    history = client.get("/api/v1/tasks/task_001/runs")

    assert created.status_code == 201
    assert created.json()["task_id"] == "task_001"
    assert service.create_idempotency_key == "create-alpha"
    assert listed.json()["items"][0]["task_id"] == "task_001"
    assert detail.json()["objective"] == "检查无人机影像"
    assert run.status_code == 201
    assert run.json()["run_number"] == 1
    assert history.json()["items"][0]["run_id"] == "run_001"


def test_compatibility_route_maps_objective_to_title(monkeypatch):
    from backend.app.api.v1 import tasks

    service = _FakeTaskService()
    monkeypatch.setattr(
        tasks,
        "build_task_service_from_environment",
        lambda: service,
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/tasks/runs",
        json={
            "task_id": "task_001",
            "task_type": "bridge_inspection",
            "objective": "检查无人机影像",
            "artifact_ids": ["art_001"],
        },
    )

    assert response.status_code == 201
    assert service.legacy_command.title == "检查无人机影像"
    assert service.legacy_command.artifact_ids == ["art_001"]


@pytest.mark.parametrize(
    ("method", "path", "service_error", "expected_status", "expected_detail"),
    [
        (
            "get",
            "/api/v1/tasks/task_missing",
            TaskNotFoundError("missing"),
            404,
            {
                "code": "TASK_NOT_FOUND",
                "message": "未找到指定任务。",
            },
        ),
        (
            "post",
            "/api/v1/tasks",
            IdempotencyConflictError("conflict"),
            409,
            {
                "code": "IDEMPOTENCY_CONFLICT",
                "message": "该幂等键已用于不同的任务内容。",
            },
        ),
        (
            "get",
            "/api/v1/tasks",
            DatabaseUnavailableError("database unavailable"),
            503,
            {
                "code": "DATABASE_UNAVAILABLE",
                "message": "PostgreSQL 任务存储当前不可用，请检查配置、连接和迁移状态。",
            },
        ),
        (
            "post",
            "/api/v1/tasks/task_001/runs",
            ModelGatewayConfigurationError("API key is required"),
            503,
            {
                "code": "MODEL_GATEWAY_NOT_CONFIGURED",
                "message": (
                    "模型网关未配置：请在后端启动环境中设置 BRIDGEAI_AGENT_API_KEY，"
                    "或将 BRIDGEAI_AGENT_MODEL_IS_STUB=true 用于本地演示。"
                ),
            },
        ),
        (
            "post",
            "/api/v1/tasks/task_001/runs",
            TaskExecutionError("run_failed", "gateway timeout"),
            502,
            {
                "code": "TASK_EXECUTION_FAILED",
                "message": "任务执行失败，可在执行历史中查看失败记录。",
                "run_id": "run_failed",
            },
        ),
        (
            "post",
            "/api/v1/tasks/runs",
            TaskInputConflictError("input conflict"),
            409,
            {
                "code": "TASK_INPUT_CONFLICT",
                "message": "该任务 ID 已存在，但执行输入不一致。",
            },
        ),
    ],
)
def test_task_routes_translate_known_errors(
    monkeypatch,
    method,
    path,
    service_error,
    expected_status,
    expected_detail,
):
    from backend.app.api.v1 import tasks

    monkeypatch.setattr(
        tasks,
        "build_task_service_from_environment",
        lambda: _ErrorTaskService(service_error),
    )
    client = TestClient(create_app())
    json_payload = None
    if path == "/api/v1/tasks":
        json_payload = {
            "title": "桥梁巡检",
            "task_type": "bridge_inspection",
            "objective": "检查影像",
            "artifact_ids": ["art_001"],
        }
    elif path == "/api/v1/tasks/runs":
        json_payload = {
            "task_id": "task_001",
            "task_type": "bridge_inspection",
            "objective": "检查影像",
            "artifact_ids": ["art_001"],
        }

    response = client.request(method, path, json=json_payload)

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_task_create_rejects_blank_artifact_id(monkeypatch):
    from backend.app.api.v1 import tasks

    monkeypatch.setattr(
        tasks,
        "build_task_service_from_environment",
        lambda: _FakeTaskService(),
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/tasks",
        json={
            "title": "桥梁巡检",
            "task_type": "bridge_inspection",
            "objective": "检查影像",
            "artifact_ids": ["   "],
        },
    )

    assert response.status_code == 422


def test_api_allows_vite_frontend_origin_preflight():
    client = TestClient(create_app())

    responses = [
        client.options(
            "/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        for origin in ("http://127.0.0.1:5173", "http://127.0.0.1:5174")
    ]

    assert [response.status_code for response in responses] == [200, 200]
    assert [
        response.headers["access-control-allow-origin"]
        for response in responses
    ] == ["http://127.0.0.1:5173", "http://127.0.0.1:5174"]


class _FakeTaskService:
    def __init__(self):
        timestamp = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
        self.task = TaskRecord(
            task_id="task_001",
            title="桥梁巡检",
            task_type="bridge_inspection",
            objective="检查无人机影像",
            artifact_ids=["art_001"],
            status="completed",
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.run = TaskRunRecord(
            run_id="run_001",
            task_id="task_001",
            run_number=1,
            status="completed",
            agent_model={"model_id": "DeepSeek-V4-Flash-4bit"},
            workflow={"current_step": "completed", "history": []},
            tool_results=[{"tool_id": "image_quality_check", "ok": True}],
            error_message=None,
            started_at=timestamp,
            completed_at=timestamp,
        )
        self.create_idempotency_key = None
        self.legacy_command = None

    def create_task(self, command, idempotency_key=None):
        self.create_idempotency_key = idempotency_key
        return self.task

    def list_tasks(self):
        return [self.task]

    def get_task(self, task_id):
        return self.task

    def execute_task(self, task_id):
        return self.run

    def list_runs(self, task_id):
        return [self.run]

    def execute_legacy_task(self, task_id, command):
        self.legacy_command = command
        return self.run


class _ErrorTaskService:
    def __init__(self, error):
        self._error = error

    def _raise(self, *args, **kwargs):
        raise self._error

    create_task = _raise
    list_tasks = _raise
    get_task = _raise
    execute_task = _raise
    list_runs = _raise
    execute_legacy_task = _raise
