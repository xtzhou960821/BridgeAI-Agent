"""Minimal Agent runner for the V0.2 task loop."""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.checkpoint.base import BaseCheckpointSaver

from agent.langgraph_state import initial_bridge_inspection_state
from agent.langgraph_workflow import build_bridge_inspection_graph
from agent.model_gateway import (
    ModelGateway,
    build_model_gateway_from_environment,
)
from agent.model_profile import AgentModelProfile, default_model_profile
from agent.workflow import WorkflowState, WorkflowStatus, WorkflowStep
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
        *,
        checkpointer: BaseCheckpointSaver,
        model_profile: AgentModelProfile | None = None,
        model_gateway: ModelGateway | None = None,
    ) -> None:
        self._tool_executor = ToolExecutor(registry)
        self._checkpointer = checkpointer
        self._model_profile = model_profile or default_model_profile()
        self._model_gateway = model_gateway or build_model_gateway_from_environment(
            profile=self._model_profile,
        )

    def run(self, context: AgentTaskContext, *, thread_id: str) -> AgentRunResult:
        initial = initial_bridge_inspection_state(
            task_id=context.task_id,
            run_id=thread_id,
            task_type=context.task_type,
            objective=context.objective,
            artifact_ids=context.artifact_ids,
            agent_model=self._model_profile.as_payload(),
        )
        graph = build_bridge_inspection_graph(
            model_gateway=self._model_gateway,
            tool_executor=self._tool_executor,
            checkpointer=self._checkpointer,
        )
        terminal = graph.invoke(
            initial,
            config={"configurable": {"thread_id": thread_id}},
        )
        workflow = WorkflowState(
            task_id=str(terminal["task_id"]),
            status=WorkflowStatus(str(terminal["status"])),
            current_step=_string_or_none(terminal["current_step"]),
            history=tuple(
                WorkflowStep(
                    step_name=str(item["step_name"]),
                    output=dict(item["output"]),
                )
                for item in terminal["workflow_history"]
            ),
            error_step=_string_or_none(terminal["error_step"]),
            error_message=_string_or_none(terminal["error_message"]),
        )
        return AgentRunResult(
            task_id=context.task_id,
            status=str(terminal["status"]),
            model_profile=self._model_profile,
            workflow=workflow,
            tool_results=[
                ToolResult(
                    tool_id=str(item["tool_id"]),
                    version=str(item["version"]),
                    ok=bool(item["ok"]),
                    output=dict(item["output"]),
                    error_code=_string_or_none(item["error_code"]),
                    error_message=_string_or_none(item["error_message"]),
                )
                for item in terminal["tool_results"]
            ],
        )


def _string_or_none(value: object) -> str | None:
    return str(value) if value is not None else None
