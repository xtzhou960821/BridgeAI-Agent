from contextlib import contextmanager

import psycopg
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from backend.app.domain.task_errors import LangGraphCheckpointerNotReadyError
from tests.backend.artifact_test_support import (
    artifact_path,
    service_with_local_store,
    upload_jpeg,
)


def test_run_inspection_task_analyzes_verified_artifact_bytes(tmp_path):
    from backend.app.services.task_runs import run_inspection_task

    artifact_service, _repository = service_with_local_store(tmp_path)
    artifact = upload_jpeg(artifact_service)
    result = run_inspection_task(
        "run_001",
        {
            "task_id": "task_001",
            "task_type": "bridge_inspection",
            "objective": "检查桥梁无人机影像质量",
            "artifact_ids": [artifact.artifact_id],
        },
        model_gateway=_FakeModelGateway(),
        checkpointer=InMemorySaver(),
        artifact_service=artifact_service,
    )

    assert result["status"] == "completed"
    assert result["workflow"]["error_code"] is None
    data_check = result["workflow"]["history"][1]["output"]
    assert data_check == {
        "ok": True,
        "artifact": artifact.as_checkpoint_payload(),
    }
    tool_result = result["tool_results"][0]
    assert tool_result["ok"] is True
    assert tool_result["output"]["artifact_id"] == artifact.artifact_id
    assert tool_result["output"]["quality_status"] == "fail"
    assert tool_result["output"]["metrics"]["short_side_px"] == 800.0
    assert tool_result["output"]["metrics"]["total_pixels"] == 1_024_000.0
    assert tool_result["output"]["thresholds"]["resolution"] == {
        "min_short_side_px": 720,
        "min_total_pixels": 1_000_000,
    }
    persisted = repr(result)
    assert artifact.storage_key not in persisted
    assert artifact.original_filename not in persisted


def test_run_inspection_task_fails_data_check_for_tampered_artifact(tmp_path):
    from backend.app.services.task_runs import run_inspection_task

    artifact_service, _repository = service_with_local_store(tmp_path)
    artifact = upload_jpeg(artifact_service)
    artifact_path(tmp_path, artifact.storage_key).write_bytes(b"tampered")

    result = run_inspection_task(
        "run_tampered",
        {**_payload(), "artifact_ids": [artifact.artifact_id]},
        model_gateway=_FakeModelGateway(),
        checkpointer=InMemorySaver(),
        artifact_service=artifact_service,
    )

    assert result["status"] == "failed"
    assert result["workflow"]["error_step"] == "data_check"
    assert result["workflow"]["error_code"] == "ARTIFACT_INTEGRITY_MISMATCH"
    assert result["tool_results"] == []


def test_run_inspection_task_maps_artifact_loss_during_tool_execution(tmp_path):
    from backend.app.services.task_runs import run_inspection_task

    artifact_service, _repository = service_with_local_store(tmp_path)
    artifact = upload_jpeg(artifact_service)
    service = _RemoveContentAfterVerify(
        artifact_service,
        artifact_path(tmp_path, artifact.storage_key),
    )

    result = run_inspection_task(
        "run_tool_storage_failure",
        {**_payload(), "artifact_ids": [artifact.artifact_id]},
        model_gateway=_FakeModelGateway(),
        checkpointer=InMemorySaver(),
        artifact_service=service,
    )

    assert result["status"] == "failed"
    assert result["workflow"]["error_step"] == "image_quality_check"
    assert result["workflow"]["error_code"] == "ARTIFACT_CONTENT_MISSING"
    assert result["tool_results"][0]["ok"] is False
    assert result["tool_results"][0]["error_code"] == "ARTIFACT_CONTENT_MISSING"


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


def test_run_inspection_task_hands_opened_saver_to_runner_and_serializes_result(
    monkeypatch,
):
    from agent.model_profile import AgentModelProfile
    from agent.runner import AgentRunResult
    from agent.workflow import WorkflowState, WorkflowStatus, WorkflowStep
    from backend.app.services import task_runs
    from tools.sdk import ToolResult

    database_url = "postgresql://checkpoint_user@db.example/bridgeai"
    run_id = "run_adapter_opened_saver"
    saver = object()
    calls = {"probe": [], "open": []}
    profile = AgentModelProfile(
        model_id="test-model",
        model_version="test-version",
        alias="test-alias",
        provider="test-provider",
        runtime="test-runtime",
        api_base_url="https://model.example/v1",
        is_stub=False,
    )

    @contextmanager
    def opener(url):
        calls["open"].append(url)
        yield saver

    class Runner:
        def __init__(
            self,
            _registry,
            *,
            artifact_verifier,
            checkpointer,
            model_gateway,
        ):
            calls["checkpointer"] = checkpointer
            calls["model_gateway"] = model_gateway
            calls["artifact_verifier"] = artifact_verifier

        def run(self, context, *, thread_id):
            calls["context"] = context
            calls["thread_id"] = thread_id
            return AgentRunResult(
                task_id=context.task_id,
                status="completed",
                model_profile=profile,
                workflow=WorkflowState(
                    task_id=context.task_id,
                    status=WorkflowStatus.COMPLETED,
                    current_step="completed",
                    history=(
                        WorkflowStep("completed", {"tool_id": "image_quality_check"}),
                    ),
                ),
                tool_results=[
                    ToolResult(
                        tool_id="image_quality_check",
                        version="0.1.0",
                        ok=True,
                        output={"quality_status": "pass", "artifact_id": "art_001"},
                    ),
                ],
            )

    def ready_probe(url):
        calls["probe"].append(url)
        return "ready"

    monkeypatch.setattr(task_runs, "probe_langgraph_checkpointer", ready_probe)
    monkeypatch.setattr(task_runs, "open_postgres_checkpointer", opener)
    monkeypatch.setattr(task_runs, "AgentRunner", Runner)

    result = task_runs.run_inspection_task(
        run_id,
        _payload(),
        database_url=database_url,
        model_gateway=_FakeModelGateway(),
        artifact_service=_FakeArtifactService(),
    )

    assert calls["probe"] == [database_url]
    assert calls["open"] == [database_url]
    assert calls["checkpointer"] is saver
    assert calls["artifact_verifier"]("art_001") == {
        "ok": True,
        "artifact": {"artifact_id": "art_001", "status": "ready"},
    }
    assert calls["thread_id"] == run_id
    assert result == {
        "task_id": "task_001",
        "status": "completed",
        "agent_model": profile.as_payload(),
        "workflow": {
            "task_id": "task_001",
            "status": "completed",
            "current_step": "completed",
            "history": [
                {"step_name": "completed", "output": {"tool_id": "image_quality_check"}},
            ],
            "error_step": None,
            "error_code": None,
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


class _FakeArtifactRecord:
    def as_checkpoint_payload(self):
        return {"artifact_id": "art_001", "status": "ready"}


class _FakeArtifactService:
    def verify(self, _artifact_id):
        return _FakeArtifactRecord()


class _RemoveContentAfterVerify:
    def __init__(self, service, path):
        self._service = service
        self._path = path

    def verify(self, artifact_id):
        record = self._service.verify(artifact_id)
        self._path.unlink()
        return record

    def open_verified(self, artifact_id):
        return self._service.open_verified(artifact_id)
