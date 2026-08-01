from __future__ import annotations

import pytest
import psycopg

from backend.app.domain.task_errors import (
    IdempotencyConflictError,
    TaskNotFoundError,
)
from backend.app.domain.tasks import TaskCreate
from backend.app.repositories.postgres.migrate import apply_migrations
from backend.app.repositories.postgres.tasks import PostgresTaskRepository
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
def test_repository_creates_lists_and_loads_task(repository):
    created = repository.create_task(
        "task_alpha",
        TaskCreate(
            title="桥梁巡检",
            task_type="bridge_inspection",
            objective="检查无人机影像",
            artifact_ids=["art_001"],
        ),
        "create-alpha",
    )

    assert created.task_id == "task_alpha"
    assert created.status == "draft"
    assert repository.get_task("task_alpha") == created
    assert repository.list_tasks() == [created]


@pytest.mark.postgres
def test_repository_replays_idempotent_create_and_rejects_conflict(repository):
    command = TaskCreate(
        title="桥梁巡检",
        task_type="bridge_inspection",
        objective="检查影像",
        artifact_ids=["art_001"],
    )

    first = repository.create_task("task_alpha", command, "same-key")
    replay = repository.create_task("task_other", command, "same-key")

    assert replay == first
    with pytest.raises(IdempotencyConflictError):
        repository.create_task(
            "task_conflict",
            TaskCreate(
                title="道路巡检",
                task_type="bridge_inspection",
                objective="不同目标",
                artifact_ids=["art_002"],
            ),
            "same-key",
        )


@pytest.mark.postgres
def test_repository_persists_ordered_terminal_runs(repository):
    repository.create_task(
        "task_alpha",
        TaskCreate(
            title="桥梁巡检",
            task_type="bridge_inspection",
            objective="检查影像",
            artifact_ids=["art_001"],
        ),
        None,
    )

    first = repository.start_run(
        "task_alpha",
        "run_001",
        workflow_runtime="langgraph",
        checkpoint_thread_id="run_001",
    )
    completed = repository.complete_run(
        "run_001",
        {"model_id": "DeepSeek-V4-Flash-4bit"},
        {"current_step": "completed", "history": []},
        [{"tool_id": "image_quality_check", "ok": True}],
    )
    second = repository.start_run(
        "task_alpha",
        "run_002",
        workflow_runtime="langgraph",
        checkpoint_thread_id="run_002",
    )
    failed = repository.fail_run(
        "run_002",
        "image quality failed",
        agent_model={"model_id": "DeepSeek-V4-Flash-4bit"},
        workflow={
            "status": "failed",
            "current_step": "failed",
            "history": [{"step_name": "failed", "output": {}}],
        },
        tool_results=[{"tool_id": "image_quality_check", "ok": False}],
    )

    assert (first.run_number, second.run_number) == (1, 2)
    assert first.workflow_runtime == "langgraph"
    assert first.checkpoint_thread_id == "run_001"
    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert failed.status == "failed"
    assert failed.error_message == "image quality failed"
    assert failed.agent_model["model_id"] == "DeepSeek-V4-Flash-4bit"
    assert failed.workflow["current_step"] == "failed"
    assert failed.tool_results[0]["ok"] is False
    assert repository.get_task("task_alpha").status == "failed"
    assert [item.run_id for item in repository.list_runs("task_alpha")] == [
        "run_002",
        "run_001",
    ]


@pytest.mark.postgres
def test_repository_rejects_missing_task_detail_and_run(repository):
    with pytest.raises(TaskNotFoundError):
        repository.get_task("task_missing")

    with pytest.raises(TaskNotFoundError):
        repository.start_run(
            "task_missing",
            "run_missing",
            workflow_runtime="langgraph",
            checkpoint_thread_id="run_missing",
        )


@pytest.mark.postgres
def test_repository_rejects_reused_checkpoint_thread_id(repository):
    repository.create_task(
        "task_alpha",
        TaskCreate(
            title="桥梁巡检",
            task_type="bridge_inspection",
            objective="检查影像",
            artifact_ids=["art_001"],
        ),
        None,
    )
    repository.start_run(
        "task_alpha",
        "run_001",
        workflow_runtime="langgraph",
        checkpoint_thread_id="thread_001",
    )

    with pytest.raises(psycopg.errors.UniqueViolation):
        # This direct write verifies the partial unique index itself, rather
        # than the repository's translation of a database error.
        database_url = require_test_database_url()
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "INSERT INTO inspection_task_runs "
                "(run_id, task_id, run_number, status, workflow_runtime, checkpoint_thread_id) "
                "VALUES ('run_002', 'task_alpha', 2, 'running', 'langgraph', 'thread_001')",
            )
