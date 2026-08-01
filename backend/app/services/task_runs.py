"""Task execution service for the V0.2 backend API."""

from __future__ import annotations

from typing import Any

from agent.model_gateway import ModelGateway, build_model_gateway_from_environment
from agent.runner import AgentRunResult, AgentRunner, AgentTaskContext
from agent.workflow import WorkflowState
from tools.sdk import ToolManifest, ToolRegistry, ToolResult


def run_inspection_task(
    payload: dict[str, Any],
    model_gateway: ModelGateway | None = None,
) -> dict[str, object]:
    """Execute the V0.2 sample inspection task and return an API payload."""

    context = AgentTaskContext(
        task_id=payload["task_id"],
        task_type=payload["task_type"],
        objective=payload["objective"],
        artifact_ids=list(payload["artifact_ids"]),
    )
    result = AgentRunner(
        _build_demo_registry(),
        model_gateway=model_gateway or build_model_gateway_from_environment(),
    ).run(context)
    return _serialize_run_result(result)


def _build_demo_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        _image_quality_check,
    )
    return registry


def _image_quality_check(payload: dict[str, Any]) -> dict[str, Any]:
    return {"quality_status": "pass", "artifact_id": payload["artifact_id"]}


def _serialize_run_result(result: AgentRunResult) -> dict[str, object]:
    return {
        "task_id": result.task_id,
        "status": result.status,
        "agent_model": result.model_profile.as_payload(),
        "workflow": _serialize_workflow(result.workflow),
        "tool_results": [_serialize_tool_result(item) for item in result.tool_results],
    }


def _serialize_workflow(workflow: WorkflowState) -> dict[str, object]:
    return {
        "task_id": workflow.task_id,
        "status": workflow.status.value,
        "current_step": workflow.current_step,
        "history": [
            {"step_name": item.step_name, "output": item.output}
            for item in workflow.history
        ],
        "error_step": workflow.error_step,
        "error_message": workflow.error_message,
    }


def _serialize_tool_result(result: ToolResult) -> dict[str, object]:
    return {
        "tool_id": result.tool_id,
        "version": result.version,
        "ok": result.ok,
        "output": result.output,
        "error_code": result.error_code,
        "error_message": result.error_message,
    }
