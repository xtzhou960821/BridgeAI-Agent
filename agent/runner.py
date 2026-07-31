"""Minimal Agent runner for the V0.2 task loop."""

from __future__ import annotations

from dataclasses import dataclass

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
    workflow: WorkflowState
    tool_results: list[ToolResult]


class AgentRunner:
    """Runs the first single-Agent, single-tool inspection skeleton."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._tool_executor = ToolExecutor(registry)

    def run(self, context: AgentTaskContext) -> AgentRunResult:
        workflow = WorkflowState.create(context.task_id).advance(
            "task_understanding",
            {
                "task_type": context.task_type,
                "objective": context.objective,
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
                workflow=failed,
                tool_results=[tool_result],
            )

        completed = workflow.advance("completed", {"tool_id": tool_result.tool_id})
        return AgentRunResult(
            task_id=context.task_id,
            status="completed",
            workflow=completed,
            tool_results=[tool_result],
        )
