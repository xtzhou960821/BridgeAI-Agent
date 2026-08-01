"""Task domain records and persistence protocol."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class TaskCreate:
    """Validated input used to create a V0.2 inspection task."""

    title: str
    task_type: str
    objective: str
    artifact_ids: list[str]


@dataclass(frozen=True)
class TaskRecord:
    """Persisted inspection task."""

    task_id: str
    title: str
    task_type: str
    objective: str
    artifact_ids: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    def as_payload(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "task_type": self.task_type,
            "objective": self.objective,
            "artifact_ids": self.artifact_ids,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class TaskRunRecord:
    """Persisted snapshot of one Agent execution."""

    run_id: str
    task_id: str
    run_number: int
    status: str
    workflow_runtime: str
    checkpoint_thread_id: str | None
    agent_model: dict[str, object]
    workflow: dict[str, object]
    tool_results: list[dict[str, object]]
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None

    def as_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "run_number": self.run_number,
            "status": self.status,
            "workflow_runtime": self.workflow_runtime,
            "checkpoint_thread_id": self.checkpoint_thread_id,
            "agent_model": self.agent_model,
            "workflow": self.workflow,
            "tool_results": self.tool_results,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


class TaskRepository(Protocol):
    """Persistence contract consumed by the task application service."""

    def create_task(
        self,
        task_id: str,
        command: TaskCreate,
        idempotency_key: str | None,
    ) -> TaskRecord: ...

    def list_tasks(self, limit: int = 50) -> list[TaskRecord]: ...

    def get_task(self, task_id: str) -> TaskRecord: ...

    def start_run(
        self,
        task_id: str,
        run_id: str,
        *,
        workflow_runtime: str = "legacy",
        checkpoint_thread_id: str | None = None,
    ) -> TaskRunRecord: ...

    def complete_run(
        self,
        run_id: str,
        agent_model: dict[str, object],
        workflow: dict[str, object],
        tool_results: list[dict[str, object]],
    ) -> TaskRunRecord: ...

    def fail_run(
        self,
        run_id: str,
        error_message: str,
        *,
        agent_model: dict[str, object] | None = None,
        workflow: dict[str, object] | None = None,
        tool_results: list[dict[str, object]] | None = None,
    ) -> TaskRunRecord: ...

    def list_runs(self, task_id: str) -> list[TaskRunRecord]: ...
