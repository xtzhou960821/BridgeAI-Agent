from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agent.model_gateway import ModelGatewayConfigurationError
from backend.app.domain.artifact_errors import (
    ArtifactNotFoundError,
    ArtifactNotReadyError,
)
from backend.app.domain.artifacts import ArtifactRecord
from backend.app.domain.task_errors import (
    LangGraphCheckpointerNotReadyError,
    TaskExecutionError,
    TaskInputConflictError,
)
from backend.app.domain.tasks import TaskCreate
from backend.app.repositories.postgres.migrate import apply_migrations
from backend.app.repositories.postgres.tasks import PostgresTaskRepository
from backend.app.services.tasks import TaskService
from tests.backend.postgres_test_support import (
    require_test_database_url,
    reset_test_tables,
)


@pytest.fixture
def repository():
    database_url = require_test_database_url()
    reset_test_tables(database_url)
    apply_migrations(database_url)
    task_repository = PostgresTaskRepository(database_url)
    yield task_repository
    reset_test_tables(database_url)


@pytest.mark.postgres
def test_service_creates_task_with_generated_id(repository):
    service = TaskService(
        repository,
        run_inspection=_successful_run,
        require_ready_artifact=_ready_artifact,
    )

    task = service.create_task(
        TaskCreate(
            title="桥梁巡检",
            task_type="bridge_inspection",
            objective="检查影像",
            artifact_ids=["art_001"],
        ),
        idempotency_key="create-1",
    )

    assert task.task_id.startswith("task_")
    assert repository.get_task(task.task_id) == task


@pytest.mark.postgres
def test_service_requires_one_ready_artifact_before_create(repository):
    calls = []
    service = TaskService(
        repository,
        run_inspection=_successful_run,
        require_ready_artifact=lambda artifact_id: calls.append(artifact_id)
        or _artifact_record(),
    )

    task = service.create_task(_task_command())

    assert calls == ["art_001"]
    assert task.artifact_ids == ["art_001"]


@pytest.mark.postgres
@pytest.mark.parametrize("artifact_ids", [[], ["art_001", "art_002"]])
def test_service_rejects_zero_or_multiple_artifacts_before_create(
    repository,
    artifact_ids,
):
    calls = []
    service = TaskService(
        repository,
        run_inspection=_successful_run,
        require_ready_artifact=lambda artifact_id: calls.append(artifact_id)
        or _artifact_record(),
    )
    command = TaskCreate(
        title="桥梁巡检",
        task_type="bridge_inspection",
        objective="检查影像",
        artifact_ids=artifact_ids,
    )

    with pytest.raises(ArtifactNotReadyError, match="Exactly one ready Artifact"):
        service.create_task(command)

    assert calls == []
    assert repository.list_tasks() == []


@pytest.mark.postgres
def test_service_does_not_create_task_for_missing_artifact(repository):
    def missing(_artifact_id):
        raise ArtifactNotFoundError("missing")

    service = TaskService(
        repository,
        _successful_run,
        require_ready_artifact=missing,
    )

    with pytest.raises(ArtifactNotFoundError):
        service.create_task(_task_command())

    assert repository.list_tasks() == []


@pytest.mark.postgres
def test_new_legacy_task_requires_ready_artifact_before_creation(repository):
    calls = []
    service = TaskService(
        repository,
        run_inspection=_successful_run,
        require_ready_artifact=lambda artifact_id: calls.append(artifact_id)
        or _artifact_record(),
    )

    run = service.execute_legacy_task("task_legacy", _task_command())

    assert calls == ["art_001"]
    assert run.status == "completed"


@pytest.mark.postgres
def test_persisted_legacy_task_bypasses_artifact_validation_and_persists_run_failure(
    repository,
):
    repository.create_task("task_legacy", _task_command(), None)

    def unavailable_artifact(_artifact_id):
        raise ArtifactNotReadyError("not ready")

    service = TaskService(
        repository,
        run_inspection=_failed_graph_run,
        require_ready_artifact=unavailable_artifact,
    )

    run = service.execute_legacy_task("task_legacy", _task_command())

    assert run.status == "failed"
    assert repository.list_runs("task_legacy") == [run]


@pytest.mark.postgres
def test_service_executes_saved_task_and_completes_run(repository):
    task = repository.create_task(
        "task_001",
        _task_command(),
        None,
    )
    calls = []

    def run_inspection(run_id, payload):
        calls.append((run_id, payload))
        return _successful_run(run_id, payload)

    service = TaskService(
        repository,
        run_inspection=run_inspection,
        require_ready_artifact=_ready_artifact,
    )

    run = service.execute_task(task.task_id)

    assert run.status == "completed"
    assert run.run_number == 1
    assert run.agent_model["model_id"] == "DeepSeek-V4-Flash-4bit"
    assert calls[0][0] == run.run_id
    assert calls[0][1] == {
            "task_id": "task_001",
            "task_type": "bridge_inspection",
            "objective": "检查影像",
            "artifact_ids": ["art_001"],
        }
    assert run.workflow_runtime == "langgraph"
    assert run.checkpoint_thread_id == run.run_id
    assert repository.list_runs(task.task_id) == [run]
    assert repository.get_task(task.task_id).status == "completed"


@pytest.mark.postgres
def test_service_persists_failed_run_before_raising(repository):
    repository.create_task("task_001", _task_command(), None)

    def fail(_run_id, _payload):
        raise RuntimeError("gateway timeout")

    service = TaskService(
        repository,
        run_inspection=fail,
        require_ready_artifact=_ready_artifact,
    )

    with pytest.raises(TaskExecutionError, match="gateway timeout") as error:
        service.execute_task("task_001")

    runs = repository.list_runs("task_001")
    assert [item.run_id for item in runs] == [error.value.run_id]
    assert runs[0].status == "failed"
    assert runs[0].error_message == "gateway timeout"
    assert repository.get_task("task_001").status == "failed"


@pytest.mark.postgres
def test_service_redacts_postgres_credentials_from_persisted_unexpected_error(repository):
    repository.create_task("task_001", _task_command(), None)

    def fail(_run_id, _payload):
        raise RuntimeError(
            "connection refused for "
            "postgres://uri-user:uri-sensitive@db.example/bridgeai and "
            "postgresql://pgsql-user:pgsql-sensitive@replica.example/bridgeai; "
            "fallback host=db.example user=bridgeai password='dsn sensitive' "
            "dbname=bridgeai; timeout after 5s",
        )

    service = TaskService(
        repository,
        run_inspection=fail,
        require_ready_artifact=_ready_artifact,
    )

    with pytest.raises(TaskExecutionError) as error:
        service.execute_task("task_001")

    saved = repository.list_runs("task_001")[0]
    for exposed_message in (str(error.value), saved.error_message or ""):
        for sensitive_value in (
            "uri-user",
            "uri-sensitive",
            "pgsql-user",
            "pgsql-sensitive",
            "dsn sensitive",
        ):
            assert sensitive_value not in exposed_message
        assert "db.example" in exposed_message
        assert "replica.example" in exposed_message
        assert "user=bridgeai" in exposed_message
        assert "dbname=bridgeai" in exposed_message
        assert "timeout after 5s" in exposed_message


@pytest.mark.postgres
def test_service_persists_model_configuration_failure_and_preserves_error_type(
    repository,
):
    repository.create_task("task_001", _task_command(), None)

    def fail(_run_id, _payload):
        raise ModelGatewayConfigurationError("API key is required")

    service = TaskService(
        repository,
        run_inspection=fail,
        require_ready_artifact=_ready_artifact,
    )

    with pytest.raises(ModelGatewayConfigurationError, match="API key is required"):
        service.execute_task("task_001")

    runs = repository.list_runs("task_001")
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].error_message == "API key is required"


@pytest.mark.postgres
def test_legacy_execution_reuses_matching_task_and_rejects_input_conflict(repository):
    service = TaskService(
        repository,
        run_inspection=_successful_run,
        require_ready_artifact=_ready_artifact,
    )
    command = _task_command()

    first_run = service.execute_legacy_task("task_legacy", command)
    second_run = service.execute_legacy_task("task_legacy", command)

    assert (first_run.run_number, second_run.run_number) == (1, 2)
    with pytest.raises(TaskInputConflictError):
        service.execute_legacy_task(
            "task_legacy",
            TaskCreate(
                title="检查不同资料",
                task_type="bridge_inspection",
                objective="检查不同资料",
                artifact_ids=["art_002"],
            ),
        )


@pytest.mark.postgres
def test_service_persists_graph_terminal_tool_failure_without_raising(repository):
    repository.create_task("task_001", _task_command(), None)

    def graph_failure(run_id, payload):
        return _failed_graph_run(run_id, payload)

    run = TaskService(
        repository,
        run_inspection=graph_failure,
        require_ready_artifact=_ready_artifact,
    ).execute_task("task_001")

    assert run.status == "failed"
    assert run.error_message == "inspection failed"
    assert run.agent_model["model_id"] == "DeepSeek-V4-Flash-4bit"
    assert run.workflow["current_step"] == "failed"
    assert run.tool_results[0]["error_message"] == "inspection failed"
    assert repository.get_task("task_001").status == "failed"


@pytest.mark.postgres
def test_service_persists_checkpointer_failure_and_preserves_error_type(repository):
    repository.create_task("task_001", _task_command(), None)

    def unavailable(run_id, _payload):
        raise LangGraphCheckpointerNotReadyError(run_id, "checkpoint tables missing")

    service = TaskService(
        repository,
        run_inspection=unavailable,
        require_ready_artifact=_ready_artifact,
    )

    with pytest.raises(LangGraphCheckpointerNotReadyError) as error:
        service.execute_task("task_001")

    saved = repository.list_runs("task_001")[0]
    assert saved.run_id == error.value.run_id
    assert saved.status == "failed"
    assert saved.checkpoint_thread_id == saved.run_id


def _task_command() -> TaskCreate:
    return TaskCreate(
        title="检查影像",
        task_type="bridge_inspection",
        objective="检查影像",
        artifact_ids=["art_001"],
    )


def _artifact_record() -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id="art_001",
        original_filename="bridge.jpg",
        storage_key="art_001.jpg",
        sha256="0" * 64,
        size_bytes=1,
        mime_type="image/jpeg",
        width_px=1,
        height_px=1,
        status="ready",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


def _ready_artifact(_artifact_id: str) -> ArtifactRecord:
    return _artifact_record()


def _successful_run(_run_id, payload):
    return {
        "task_id": payload["task_id"],
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
            "task_id": payload["task_id"],
            "status": "completed",
            "current_step": "completed",
            "history": [],
            "error_step": None,
            "error_message": None,
        },
        "tool_results": [
            {
                "tool_id": "image_quality_check",
                "version": "0.1.0",
                "ok": True,
                "output": {
                    "quality_status": "pass",
                    "artifact_id": payload["artifact_ids"][0],
                },
                "error_code": None,
                "error_message": None,
            },
        ],
    }


def _failed_graph_run(run_id, payload):
    result = _successful_run(run_id, payload)
    result["status"] = "failed"
    result["workflow"] = {
        "task_id": payload["task_id"],
        "status": "failed",
        "current_step": "failed",
        "history": [
            {"step_name": "image_quality_check", "output": {"tool_id": "image_quality_check"}},
            {"step_name": "failed", "output": {"tool_id": "image_quality_check"}},
        ],
        "error_step": "image_quality_check",
        "error_message": "inspection failed",
    }
    result["tool_results"] = [
        {
            "tool_id": "image_quality_check",
            "version": "0.1.0",
            "ok": False,
            "output": None,
            "error_code": "TOOL_EXECUTION_FAILED",
            "error_message": "inspection failed",
        },
    ]
    return result
