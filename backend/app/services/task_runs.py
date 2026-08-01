"""Task execution service for the V0.2 backend API."""

from __future__ import annotations

import os
from functools import partial
from typing import Any

import psycopg
from langgraph.checkpoint.base import BaseCheckpointSaver

from agent.model_gateway import ModelGateway, build_model_gateway_from_environment
from agent.runner import AgentRunResult, AgentRunner, AgentTaskContext
from agent.workflow import WorkflowState
from backend.app.domain.artifact_errors import ArtifactError
from backend.app.domain.task_errors import LangGraphCheckpointerNotReadyError
from backend.app.repositories.postgres.checkpoints import (
    open_postgres_checkpointer,
    probe_langgraph_checkpointer,
)
from backend.app.services.artifacts import (
    ArtifactService,
    build_artifact_service_from_environment,
)
from backend.app.services.image_quality import ImageQualityAnalyzer
from tools.sdk import ToolHandlerError, ToolManifest, ToolRegistry, ToolResult


def run_inspection_task(
    run_id: str,
    payload: dict[str, Any],
    *,
    database_url: str | None = None,
    model_gateway: ModelGateway | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    artifact_service: ArtifactService | None = None,
) -> dict[str, object]:
    """Execute the V0.2 sample inspection task and return an API payload."""

    context = AgentTaskContext(
        task_id=payload["task_id"],
        task_type=payload["task_type"],
        objective=payload["objective"],
        artifact_ids=list(payload["artifact_ids"]),
    )
    gateway = model_gateway or build_model_gateway_from_environment()
    if checkpointer is not None:
        result = _run_with_checkpointer(
            run_id,
            context,
            gateway,
            checkpointer,
            artifact_service,
        )
    else:
        url = database_url or os.environ.get("BRIDGEAI_DATABASE_URL", "").strip()
        if probe_langgraph_checkpointer(url) != "ready":
            raise LangGraphCheckpointerNotReadyError(
                run_id,
                "LangGraph checkpointer is not ready",
            )
        try:
            with open_postgres_checkpointer(url) as saver:
                result = _run_with_checkpointer(
                    run_id,
                    context,
                    gateway,
                    saver,
                    artifact_service,
                )
        except psycopg.Error as exc:
            raise LangGraphCheckpointerNotReadyError(
                run_id,
                "LangGraph checkpointer is not ready",
            ) from exc
    return _serialize_run_result(result)


def _run_with_checkpointer(
    run_id: str,
    context: AgentTaskContext,
    model_gateway: ModelGateway,
    checkpointer: BaseCheckpointSaver,
    artifact_service: ArtifactService | None,
) -> AgentRunResult:
    service = artifact_service or build_artifact_service_from_environment()
    return AgentRunner(
        _build_registry(service),
        artifact_verifier=partial(_verify_artifact, service),
        model_gateway=model_gateway,
        checkpointer=checkpointer,
    ).run(context, thread_id=run_id)


def _build_registry(service: ArtifactService) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        partial(_image_quality_handler, service, ImageQualityAnalyzer()),
    )
    return registry


def _verify_artifact(
    service: ArtifactService,
    artifact_id: str,
) -> dict[str, object]:
    try:
        record = service.verify(artifact_id)
    except ArtifactError as exc:
        return {"ok": False, "error_code": exc.code, "error_message": str(exc)}
    return {"ok": True, "artifact": record.as_checkpoint_payload()}


def _image_quality_handler(
    service: ArtifactService,
    analyzer: ImageQualityAnalyzer,
    payload: dict[str, object],
) -> dict[str, object]:
    artifact_id = str(payload["artifact_id"])
    try:
        with service.open_verified(artifact_id) as (_record, stream):
            return analyzer.analyze(stream, artifact_id=artifact_id).as_payload()
    except ArtifactError as exc:
        raise ToolHandlerError(exc.code, str(exc)) from exc


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
        "error_code": workflow.error_code,
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
