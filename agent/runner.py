"""Minimal Agent runner for the V0.2 task loop."""

from __future__ import annotations

from dataclasses import dataclass

from agent.model_gateway import (
    ModelGateway,
    TaskUnderstandingRequest,
    build_model_gateway_from_environment,
)
from agent.model_profile import AgentModelProfile, default_model_profile
from agent.workflow import WorkflowState
from tools.sdk import ToolExecutor, ToolRegistry, ToolResult


@dataclass(frozen=True)
class AgentTaskContext:
    """Input context for one Agent task execution."""

    task_id: str
    task_type: str
    objective: str
    artifact_ids: list[str]


@dataclass(frozen=True)
class AgentRunResult:
    """Structured result returned by the Agent runner."""

    task_id: str
    status: str
    model_profile: AgentModelProfile
    workflow: WorkflowState
    tool_results: list[ToolResult]


class AgentRunner:
    """Runs the first single-Agent, single-tool inspection skeleton."""

    def __init__(
        self,
        registry: ToolRegistry,
        model_profile: AgentModelProfile | None = None,
        model_gateway: ModelGateway | None = None,
    ) -> None:
        self._tool_executor = ToolExecutor(registry)
        self._model_profile = model_profile or default_model_profile()
        self._model_gateway = model_gateway or build_model_gateway_from_environment(
            profile=self._model_profile,
        )

    def run(self, context: AgentTaskContext) -> AgentRunResult:
        model_result = self._model_gateway.understand_task(
            TaskUnderstandingRequest(
                task_id=context.task_id,
                task_type=context.task_type,
                objective=context.objective,
                artifact_ids=context.artifact_ids,
            ),
        )
        workflow = WorkflowState.create(context.task_id).advance(
            "task_understanding",
            {
                "task_type": context.task_type,
                "objective": context.objective,
                "model_result": model_result.as_payload(),
            },
        )

        artifact_id = context.artifact_ids[0]
        workflow = workflow.advance("data_check", {"artifact_id": artifact_id})
        tool_result = self._tool_executor.execute(
            "image_quality_check",
            {"artifact_id": artifact_id},
        )

        if not tool_result.ok:
            failed = workflow.fail("image_quality_check", tool_result.error_message or "tool failed")
            return AgentRunResult(
                task_id=context.task_id,
                status="failed",
                model_profile=self._model_profile,
                workflow=failed,
                tool_results=[tool_result],
            )

        completed = workflow.advance("completed", {"tool_id": tool_result.tool_id})
        return AgentRunResult(
            task_id=context.task_id,
            status="completed",
            model_profile=self._model_profile,
            workflow=completed,
            tool_results=[tool_result],
        )
