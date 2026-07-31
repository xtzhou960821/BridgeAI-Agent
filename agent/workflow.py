"""Minimal workflow state model for BridgeAI-Agent V0.2."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkflowStatus(StrEnum):
    """Supported workflow execution states."""

    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass(frozen=True)
class WorkflowStep:
    """One recorded workflow step output."""

    step_name: str
    output: dict[str, Any]


@dataclass(frozen=True)
class WorkflowState:
    """Immutable-style workflow state used by the Agent runner."""

    task_id: str
    status: WorkflowStatus
    current_step: str | None = None
    history: tuple[WorkflowStep, ...] = field(default_factory=tuple)
    error_step: str | None = None
    error_message: str | None = None

    @classmethod
    def create(cls, task_id: str) -> WorkflowState:
        return cls(task_id=task_id, status=WorkflowStatus.PENDING)

    def advance(self, step_name: str, output: dict[str, Any]) -> WorkflowState:
        status = WorkflowStatus.COMPLETED if step_name == "completed" else WorkflowStatus.RUNNING
        return WorkflowState(
            task_id=self.task_id,
            status=status,
            current_step=step_name,
            history=(*self.history, WorkflowStep(step_name=step_name, output=output)),
        )

    def fail(self, step_name: str, error_message: str) -> WorkflowState:
        return WorkflowState(
            task_id=self.task_id,
            status=WorkflowStatus.FAILED,
            current_step=self.current_step,
            history=self.history,
            error_step=step_name,
            error_message=error_message,
        )

    def recover(self, step_name: str) -> WorkflowState:
        return WorkflowState(
            task_id=self.task_id,
            status=WorkflowStatus.RUNNING,
            current_step=step_name,
            history=self.history,
        )
