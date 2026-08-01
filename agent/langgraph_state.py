"""Serializer-safe state for the Bridge inspection LangGraph workflow."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class WorkflowHistoryItem(TypedDict):
    """One serializable workflow-step record."""

    step_name: str
    output: dict[str, object]


class BridgeInspectionState(TypedDict):
    """State persisted by the Bridge inspection graph."""

    task_id: str
    run_id: str
    task_type: str
    objective: str
    artifact_ids: list[str]
    status: str
    current_step: str | None
    agent_model: dict[str, object]
    model_result: dict[str, object]
    workflow_history: Annotated[list[WorkflowHistoryItem], operator.add]
    tool_results: list[dict[str, object]]
    error_step: str | None
    error_message: str | None


def initial_bridge_inspection_state(
    *,
    task_id: str,
    run_id: str,
    task_type: str,
    objective: str,
    artifact_ids: list[str],
    agent_model: dict[str, object],
) -> BridgeInspectionState:
    """Create a state containing only checkpoint-serializer-safe values."""

    return {
        "task_id": task_id,
        "run_id": run_id,
        "task_type": task_type,
        "objective": objective,
        "artifact_ids": list(artifact_ids),
        "status": "running",
        "current_step": None,
        "agent_model": dict(agent_model),
        "model_result": {},
        "workflow_history": [],
        "tool_results": [],
        "error_step": None,
        "error_message": None,
    }
