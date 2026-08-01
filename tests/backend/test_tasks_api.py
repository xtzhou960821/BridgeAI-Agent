import pytest


try:
    from fastapi.testclient import TestClient
except (ModuleNotFoundError, RuntimeError) as exc:
    pytest.skip(f"FastAPI test client is not available: {exc}", allow_module_level=True)

from backend.app.main import create_app


def test_task_run_route_executes_inspection_task(monkeypatch):
    from backend.app.services import task_runs

    monkeypatch.setattr(
        task_runs,
        "build_model_gateway_from_environment",
        lambda profile=None: _FakeModelGateway(),
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/tasks/runs",
        json={
            "task_id": "task_001",
            "task_type": "bridge_inspection",
            "objective": "检查桥梁无人机影像质量",
            "artifact_ids": ["art_001"],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["agent_model"]["model_id"] == "DeepSeek-V4-Flash-4bit"
    assert response.json()["agent_model"]["api_base_url"] == "https://omlx.cpolar.cn/v1"
    assert response.json()["agent_model"]["is_stub"] is False
    assert response.json()["workflow"]["current_step"] == "completed"
    assert response.json()["workflow"]["history"][0]["output"]["model_result"]["content"] == (
        "任务理解完成：检查桥梁无人机影像质量"
    )
    assert response.json()["tool_results"][0]["output"] == {
        "quality_status": "pass",
        "artifact_id": "art_001",
    }


def test_task_run_route_returns_503_when_model_gateway_is_not_configured(monkeypatch):
    from agent.model_gateway import ModelGatewayConfigurationError
    from backend.app.api.v1 import tasks

    def raise_configuration_error(_payload):
        raise ModelGatewayConfigurationError("API key is required")

    monkeypatch.setattr(tasks, "run_inspection_task", raise_configuration_error)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/tasks/runs",
        json={
            "task_id": "task_001",
            "task_type": "bridge_inspection",
            "objective": "检查桥梁无人机影像质量",
            "artifact_ids": ["art_001"],
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "MODEL_GATEWAY_NOT_CONFIGURED",
        "message": (
            "模型网关未配置：请在后端启动环境中设置 BRIDGEAI_AGENT_API_KEY，"
            "或将 BRIDGEAI_AGENT_MODEL_IS_STUB=true 用于本地演示。"
        ),
    }


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


class _FakeModelGateway:
    def understand_task(self, request):
        return _FakeModelResult(
            {
                "ok": True,
                "model_id": "DeepSeek-V4-Flash-4bit",
                "provider": "omlx",
                "runtime": "openai-compatible",
                "content": f"任务理解完成：{request.objective}",
                "usage": {"total_tokens": 12},
                "error_message": None,
            },
        )


class _FakeModelResult:
    def __init__(self, payload):
        self._payload = payload

    def as_payload(self):
        return self._payload
