"""Typed LangGraph workflow for Bridge inspection runs."""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from agent.langgraph_state import BridgeInspectionState, WorkflowHistoryItem
from agent.model_gateway import ModelGateway, TaskUnderstandingRequest
from tools.sdk import ToolExecutor, ToolResult


def build_bridge_inspection_graph(
    *,
    model_gateway: ModelGateway,
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
        return {
            "current_step": "data_check",
            "workflow_history": [_history_item("data_check", {"artifact_id": artifact_id})],
        }

    def image_quality_check(state: BridgeInspectionState) -> dict[str, object]:
        tool_result = tool_executor.execute(
            "image_quality_check",
            {"artifact_id": state["artifact_ids"][0]},
        )
        serialized_result = _serialize_tool_result(tool_result)
        return {
            "current_step": "image_quality_check",
            "tool_results": [serialized_result],
            "workflow_history": [
                _history_item("image_quality_check", {"tool_result": serialized_result}),
            ],
        }

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
        tool_result = state["tool_results"][-1]
        tool_id = str(tool_result["tool_id"])
        error_message = str(tool_result["error_message"] or "tool failed")
        return {
            "status": "failed",
            "current_step": "failed",
            "error_step": "image_quality_check",
            "error_message": error_message,
            "workflow_history": [_history_item("failed", {"tool_id": tool_id})],
        }

    builder = StateGraph(BridgeInspectionState)
    builder.add_node("task_understanding", task_understanding)
    builder.add_node("data_check", data_check)
    builder.add_node("image_quality_check", image_quality_check)
    builder.add_node("completed", completed)
    builder.add_node("failed", failed)
    builder.add_edge(START, "task_understanding")
    builder.add_edge("task_understanding", "data_check")
    builder.add_edge("data_check", "image_quality_check")
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


def _serialize_tool_result(tool_result: ToolResult) -> dict[str, object]:
    return {
        "tool_id": tool_result.tool_id,
        "version": tool_result.version,
        "ok": tool_result.ok,
        "output": dict(tool_result.output),
        "error_code": tool_result.error_code,
        "error_message": tool_result.error_message,
    }
