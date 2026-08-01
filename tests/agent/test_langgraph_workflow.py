import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from agent.langgraph_state import StateSerializationError, initial_bridge_inspection_state
from agent.langgraph_workflow import build_bridge_inspection_graph
from tools.sdk import ToolExecutor, ToolManifest, ToolRegistry


def test_graph_routes_success_through_all_named_nodes():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=saver,
    )
    config = {"configurable": {"thread_id": "run_success"}}

    result = graph.invoke(_initial_state("run_success"), config=config)

    assert result["status"] == "completed"
    assert result["current_step"] == "completed"
    assert [item["step_name"] for item in result["workflow_history"]] == [
        "task_understanding",
        "data_check",
        "image_quality_check",
        "completed",
    ]
    assert result["tool_results"][0]["ok"] is True


def test_graph_routes_unsuccessful_tool_to_failed():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        tool_executor=ToolExecutor(
            _registry(required=["artifact_id", "camera_id"]),
        ),
        checkpointer=saver,
    )

    result = graph.invoke(
        _initial_state("run_failed"),
        config={"configurable": {"thread_id": "run_failed"}},
    )

    assert result["status"] == "failed"
    assert result["current_step"] == "failed"
    assert result["error_step"] == "image_quality_check"
    assert result["error_message"] == "Missing required input: camera_id"
    assert [item["step_name"] for item in result["workflow_history"]][-1] == "failed"


def test_graph_persists_multiple_checkpoints_for_one_thread():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=saver,
    )
    config = {"configurable": {"thread_id": "run_checkpointed"}}

    graph.invoke(_initial_state("run_checkpointed"), config=config)

    checkpoints = list(saver.list(config))
    assert len(checkpoints) >= 5
    assert checkpoints[0].checkpoint["channel_values"]["run_id"] == "run_checkpointed"


def test_initial_state_contains_only_serializer_safe_values():
    state = _initial_state("run_serializable")

    assert state["run_id"] == "run_serializable"
    assert state["workflow_history"] == []
    assert state["tool_results"] == []
    assert state["error_step"] is None
    assert state["error_message"] is None


def test_graph_redacts_sensitive_values_and_serializes_with_strict_msgpack():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(
            additional_payload={"api_key": "model-secret"},
        ),
        tool_executor=ToolExecutor(
            _registry_with_output(
                {
                    "quality_status": "pass",
                    "nested": {"access_token": "tool-secret", "score": 0.98},
                },
            ),
        ),
        checkpointer=saver,
    )

    result = graph.invoke(
        initial_bridge_inspection_state(
            task_id="task_001",
            run_id="run_safe_msgpack",
            task_type="bridge_inspection",
            objective="检查桥梁无人机影像质量",
            artifact_ids=["art_001"],
            agent_model={
                "model_id": "DeepSeek-V4-Flash-4bit",
                "api_key": "profile-secret",
                "metadata": {"binary": b"untrusted"},
            },
        ),
        config={"configurable": {"thread_id": "run_safe_msgpack"}},
    )

    assert result["agent_model"] == {"model_id": "DeepSeek-V4-Flash-4bit"}
    assert "api_key" not in result["model_result"]
    assert result["tool_results"][0]["output"]["nested"] == {
        "access_token": "[redacted]",
        "score": 0.98,
    }
    value_type, _ = JsonPlusSerializer(pickle_fallback=False).dumps_typed(result)
    assert value_type == "msgpack"


def test_graph_rejects_binary_tool_output_before_checkpointing():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        tool_executor=ToolExecutor(
            _registry_with_output(
                {"quality_status": "pass", "binary_artifact": b"untrusted"},
            ),
        ),
        checkpointer=saver,
    )

    with pytest.raises(
        StateSerializationError,
        match="tool_result.output.binary_artifact",
    ):
        graph.invoke(
            _initial_state("run_rejected_binary"),
            config={"configurable": {"thread_id": "run_rejected_binary"}},
        )


def _initial_state(run_id: str):
    return initial_bridge_inspection_state(
        task_id="task_001",
        run_id=run_id,
        task_type="bridge_inspection",
        objective="检查桥梁无人机影像质量",
        artifact_ids=["art_001"],
        agent_model={"model_id": "DeepSeek-V4-Flash-4bit"},
    )


def _registry(required: list[str]) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": required},
            output_schema={"required": ["quality_status"]},
        ),
        lambda payload: {
            "quality_status": "pass",
            "artifact_id": payload["artifact_id"],
        },
    )
    return registry


def _registry_with_output(output: dict[str, object]) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        lambda payload: output,
    )
    return registry


class _FakeModelGateway:
    def __init__(self, additional_payload: dict[str, object] | None = None):
        self._additional_payload = additional_payload or {}

    def understand_task(self, request):
        payload = {
            "ok": True,
            "model_id": "DeepSeek-V4-Flash-4bit",
            "provider": "omlx",
            "runtime": "openai-compatible",
            "content": f"任务理解完成：{request.objective}",
            "usage": {"total_tokens": 12},
            "error_message": None,
        }
        payload.update(self._additional_payload)
        return _FakeModelResult(
            payload,
        )


class _FakeModelResult:
    def __init__(self, payload):
        self._payload = payload

    def as_payload(self):
        return self._payload
