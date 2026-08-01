from contextlib import contextmanager

import psycopg
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from backend.app.domain.task_errors import LangGraphCheckpointerNotReadyError


def test_run_inspection_task_returns_completed_workflow_and_tool_result():
    from backend.app.services.task_runs import run_inspection_task

    result = run_inspection_task(
        "run_001",
        {
            "task_id": "task_001",
            "task_type": "bridge_inspection",
            "objective": "检查桥梁无人机影像质量",
            "artifact_ids": ["art_001"],
        },
        model_gateway=_FakeModelGateway(),
        checkpointer=InMemorySaver(),
    )

    assert result == {
        "task_id": "task_001",
        "status": "completed",
        "agent_model": {
            "model_id": "DeepSeek-V4-Flash-4bit",
            "model_version": "omlx-current",
            "alias": "omlx-deepseek-v4-flash",
            "provider": "omlx",
            "runtime": "openai-compatible",
            "api_base_url": "https://omlx.cpolar.cn/v1",
            "is_stub": False,
        },
        "workflow": {
            "task_id": "task_001",
            "status": "completed",
            "current_step": "completed",
            "history": [
                {
                    "step_name": "task_understanding",
                    "output": {
                        "task_type": "bridge_inspection",
                        "objective": "检查桥梁无人机影像质量",
                        "model_result": {
                            "ok": True,
                            "model_id": "DeepSeek-V4-Flash-4bit",
                            "provider": "omlx",
                            "runtime": "openai-compatible",
                            "content": "任务理解完成：检查桥梁无人机影像质量",
                            "usage": {"total_tokens": 12},
                            "error_message": None,
                        },
                    },
                },
                {
                    "step_name": "data_check",
                    "output": {"artifact_id": "art_001"},
                },
                {
                    "step_name": "image_quality_check",
                    "output": {
                        "tool_result": {
                            "tool_id": "image_quality_check",
                            "version": "0.1.0",
                            "ok": True,
                            "output": {"quality_status": "pass", "artifact_id": "art_001"},
                            "error_code": None,
                            "error_message": None,
                        },
                    },
                },
                {
                    "step_name": "completed",
                    "output": {"tool_id": "image_quality_check"},
                },
            ],
            "error_step": None,
            "error_message": None,
        },
        "tool_results": [
            {
                "tool_id": "image_quality_check",
                "version": "0.1.0",
                "ok": True,
                "output": {"quality_status": "pass", "artifact_id": "art_001"},
                "error_code": None,
                "error_message": None,
            },
        ],
    }


@pytest.mark.parametrize(
    ("database_url", "environment_url", "probe_status", "expected_url"),
    [
        (
            "postgresql://explicit_user:explicit-secret@db.example/bridgeai",
            "postgresql://environment_user:environment-secret@db.example/bridgeai",
            "unavailable",
            "postgresql://explicit_user:explicit-secret@db.example/bridgeai",
        ),
        (
            None,
            "postgresql://environment_user:environment-secret@db.example/bridgeai",
            "not_initialized",
            "postgresql://environment_user:environment-secret@db.example/bridgeai",
        ),
    ],
)
def test_run_inspection_task_rejects_unready_checkpointer_without_fallback(
    monkeypatch,
    database_url,
    environment_url,
    probe_status,
    expected_url,
):
    from backend.app.services import task_runs

    probe_calls = []
    monkeypatch.setenv("BRIDGEAI_DATABASE_URL", environment_url)
    monkeypatch.setattr(
        task_runs,
        "probe_langgraph_checkpointer",
        lambda url: probe_calls.append(url) or probe_status,
    )
    monkeypatch.setattr(task_runs, "open_postgres_checkpointer", _unexpected_opener)

    with pytest.raises(LangGraphCheckpointerNotReadyError) as error:
        task_runs.run_inspection_task(
            "run_adapter_not_ready",
            _payload(),
            database_url=database_url,
            model_gateway=_FakeModelGateway(),
        )

    assert error.value.run_id == "run_adapter_not_ready"
    assert "not ready" in str(error.value)
    assert "secret" not in str(error.value)
    assert probe_calls == [expected_url]


def test_run_inspection_task_translates_postgres_saver_failure_without_credentials(
    monkeypatch,
):
    from backend.app.services import task_runs

    database_url = "postgresql://checkpoint_user:checkpoint-secret@db.example/bridgeai"
    open_calls = []
    monkeypatch.setattr(task_runs, "probe_langgraph_checkpointer", lambda _url: "ready")
    monkeypatch.setattr(
        task_runs,
        "open_postgres_checkpointer",
        _failing_opener(open_calls),
    )

    with pytest.raises(LangGraphCheckpointerNotReadyError) as error:
        task_runs.run_inspection_task(
            "run_adapter_psycopg",
            _payload(),
            database_url=database_url,
            model_gateway=_FakeModelGateway(),
        )

    assert error.value.run_id == "run_adapter_psycopg"
    assert "not ready" in str(error.value)
    assert "checkpoint-secret" not in str(error.value)
    assert open_calls == [database_url]


def _payload():
    return {
        "task_id": "task_001",
        "task_type": "bridge_inspection",
        "objective": "检查桥梁无人机影像质量",
        "artifact_ids": ["art_001"],
    }


def _unexpected_opener(_database_url):
    raise AssertionError("unready checkpointer must not be opened or replaced")


def _failing_opener(open_calls):
    @contextmanager
    def opener(database_url):
        open_calls.append(database_url)
        raise psycopg.OperationalError(
            "connection rejected for checkpoint-secret",
        )
        yield None

    return opener


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
