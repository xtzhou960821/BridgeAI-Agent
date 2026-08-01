"""Typed LangGraph workflow for Bridge inspection runs."""

from __future__ import annotations

from collections.abc import Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from agent.langgraph_state import (
    BridgeInspectionState,
    WorkflowHistoryItem,
    artifact_verifier_payload,
    external_text_payload,
    image_quality_output_payload,
    model_result_payload,
    normalize_checkpoint_value,
    safe_error_code_payload,
    tool_id_payload,
    version_payload,
)
from agent.model_gateway import ModelGateway, TaskUnderstandingRequest
from tools.sdk import ToolExecutor, ToolResult


ArtifactVerifier = Callable[[str], dict[str, object]]


def build_bridge_inspection_graph(
    *,
    model_gateway: ModelGateway,
    artifact_verifier: ArtifactVerifier,
    tool_executor: ToolExecutor,
    checkpointer: BaseCheckpointSaver,
):
    """Build the persisted, named-node Bridge inspection graph."""

    def task_understanding(state: BridgeInspectionState) -> dict[str, object]:
        model_result = model_gateway.understand_task(
            TaskUnderstandingRequest(
                task_id=state["task_id"],
                task_type=state["task_type"],
                objective=state["objective"],
                artifact_ids=state["artifact_ids"],
            ),
        ).as_payload()
        model_result = model_result_payload(model_result)
        return {
            "current_step": "task_understanding",
            "model_result": model_result,
            "workflow_history": [
                _history_item(
                    "task_understanding",
                    {
                        "task_type": state["task_type"],
                        "objective": state["objective"],
                        "model_result": model_result,
                    },
                ),
            ],
        }

    def data_check(state: BridgeInspectionState) -> dict[str, object]:
        artifact_id = state["artifact_ids"][0]
        normalized = artifact_verifier_payload(artifact_verifier(artifact_id))
        update: dict[str, object] = {
            "current_step": "data_check",
            "data_check_result": normalized,
            "workflow_history": [_history_item("data_check", normalized)],
        }
        if normalized.get("ok") is not True:
            update.update(
                {
                    "error_step": "data_check",
                    "error_code": _error_value(
                        normalized.get("error_code"),
                        "ARTIFACT_VERIFICATION_FAILED",
                    ),
                    "error_message": _error_value(
                        normalized.get("error_message"),
                        "Artifact verification failed",
                    ),
                }
            )
        return update

    def route_after_data_check(state: BridgeInspectionState) -> str:
        if state["data_check_result"].get("ok") is True:
            return "image_quality_check"
        return "failed"

    def image_quality_check(state: BridgeInspectionState) -> dict[str, object]:
        tool_result = tool_executor.execute(
            "image_quality_check",
            {"artifact_id": state["artifact_ids"][0]},
        )
        serialized_result = _serialize_tool_result(tool_result)
        update: dict[str, object] = {
            "current_step": "image_quality_check",
            "tool_results": [serialized_result],
            "workflow_history": [
                _history_item("image_quality_check", {"tool_result": serialized_result}),
            ],
        }
        if serialized_result["ok"] is not True:
            update.update(
                {
                    "error_step": "image_quality_check",
                    "error_code": _error_value(
                        serialized_result.get("error_code"),
                        "TOOL_EXECUTION_FAILED",
                    ),
                    "error_message": _error_value(
                        serialized_result.get("error_message"),
                        "tool failed",
                    ),
                }
            )
        return update

    def route_after_tool(state: BridgeInspectionState) -> str:
        if state["tool_results"] and state["tool_results"][-1]["ok"] is True:
            return "completed"
        return "failed"

    def completed(state: BridgeInspectionState) -> dict[str, object]:
        tool_id = str(state["tool_results"][-1]["tool_id"])
        return {
            "status": "completed",
            "current_step": "completed",
            "workflow_history": [_history_item("completed", {"tool_id": tool_id})],
        }

    def failed(state: BridgeInspectionState) -> dict[str, object]:
        return {
            "status": "failed",
            "current_step": "failed",
            "workflow_history": [
                _history_item(
                    "failed",
                    {
                        "error_step": state["error_step"],
                        "error_code": state["error_code"],
                        "error_message": state["error_message"],
                    },
                )
            ],
        }

    builder = StateGraph(BridgeInspectionState)
    builder.add_node("task_understanding", task_understanding)
    builder.add_node("data_check", data_check)
    builder.add_node("image_quality_check", image_quality_check)
    builder.add_node("completed", completed)
    builder.add_node("failed", failed)
    builder.add_edge(START, "task_understanding")
    builder.add_edge("task_understanding", "data_check")
    builder.add_conditional_edges(
        "data_check",
        route_after_data_check,
        {"image_quality_check": "image_quality_check", "failed": "failed"},
    )
    builder.add_conditional_edges(
        "image_quality_check",
        route_after_tool,
        {"completed": "completed", "failed": "failed"},
    )
    builder.add_edge("completed", END)
    builder.add_edge("failed", END)
    return builder.compile(checkpointer=checkpointer)


def _history_item(step_name: str, output: dict[str, object]) -> WorkflowHistoryItem:
    return {"step_name": step_name, "output": output}


def _error_value(value: object, default: str) -> str:
    return str(value) if value is not None else default


def _serialize_tool_result(tool_result: ToolResult) -> dict[str, object]:
    output = image_quality_output_payload(tool_result.output)
    tool_id = tool_id_payload(tool_result.tool_id, path="tool_result.tool_id")
    version = version_payload(tool_result.version, path="tool_result.version")
    if not isinstance(tool_result.ok, bool):
        raise TypeError("Tool result ok must be a boolean")
    error_code = (
        safe_error_code_payload(
            tool_result.error_code,
            path="tool_result.error_code",
            default="TOOL_EXECUTION_FAILED",
        )
        if tool_result.error_code is not None
        else None
    )
    error_message = (
        external_text_payload(
            tool_result.error_message,
            path="tool_result.error_message",
        )
        if tool_result.error_message is not None
        else None
    )
    serialized_result = normalize_checkpoint_value(
        {
        "tool_id": tool_id,
        "version": version,
        "ok": tool_result.ok,
        "output": output,
        "error_code": error_code,
        "error_message": error_message,
        },
        path="tool_result",
    )
    if not isinstance(serialized_result, dict):
        raise TypeError("Tool result serialization must produce a dictionary")
    return serialized_result
