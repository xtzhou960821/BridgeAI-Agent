from __future__ import annotations

import pytest

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

    first = repository.start_run("task_alpha", "run_001")
    completed = repository.complete_run(
        "run_001",
        {"model_id": "DeepSeek-V4-Flash-4bit"},
        {"current_step": "completed", "history": []},
        [{"tool_id": "image_quality_check", "ok": True}],
    )
    second = repository.start_run("task_alpha", "run_002")
    failed = repository.fail_run("run_002", "model timeout")

    assert (first.run_number, second.run_number) == (1, 2)
    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert failed.status == "failed"
    assert failed.error_message == "model timeout"
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
        repository.start_run("task_missing", "run_missing")
