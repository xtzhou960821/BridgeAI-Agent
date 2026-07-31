from agent.runner import AgentRunner, AgentTaskContext
from tools.sdk import ToolManifest, ToolRegistry


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

    result = AgentRunner(registry).run(context)

    assert result.status == "completed"
    assert result.task_id == "task_001"
    assert result.tool_results[0].tool_id == "image_quality_check"
    assert result.tool_results[0].ok is True
    assert result.workflow.current_step == "completed"
