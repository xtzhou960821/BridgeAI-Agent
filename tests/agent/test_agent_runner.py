from agent.runner import AgentRunner, AgentTaskContext
from tools.sdk import ToolManifest, ToolRegistry


class _FakeModelGateway:
    def understand_task(self, request):
        return _FakeModelResult(
            {
                "ok": True,
                "model_id": "DeepSeek-V4-Flash-4bit",
                "provider": "omlx",
                "runtime": "openai-compatible",
                "content": f"任务理解完成：{request.objective}",
                "usage": {"total_tokens": 12},
                "error_message": None,
            },
        )


class _FakeModelResult:
    def __init__(self, payload):
        self._payload = payload

    def as_payload(self):
        return self._payload


def test_agent_runner_executes_image_quality_tool_for_inspection_task():
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        lambda payload: {"quality_status": "pass", "artifact_id": payload["artifact_id"]},
    )
    context = AgentTaskContext(
        task_id="task_001",
        task_type="bridge_inspection",
        objective="检查桥梁无人机影像质量",
        artifact_ids=["art_001"],
    )

    result = AgentRunner(registry, model_gateway=_FakeModelGateway()).run(context)

    assert result.status == "completed"
    assert result.task_id == "task_001"
    assert result.model_profile.model_id == "DeepSeek-V4-Flash-4bit"
    assert result.model_profile.is_stub is False
    assert result.tool_results[0].tool_id == "image_quality_check"
    assert result.tool_results[0].ok is True
    assert result.workflow.current_step == "completed"
    assert result.workflow.history[0].output["model_result"] == {
        "ok": True,
        "model_id": "DeepSeek-V4-Flash-4bit",
        "provider": "omlx",
        "runtime": "openai-compatible",
        "content": "任务理解完成：检查桥梁无人机影像质量",
        "usage": {"total_tokens": 12},
        "error_message": None,
    }
