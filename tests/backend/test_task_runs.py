def test_run_inspection_task_returns_completed_workflow_and_tool_result():
    from backend.app.services.task_runs import run_inspection_task

    result = run_inspection_task(
        {
            "task_id": "task_001",
            "task_type": "bridge_inspection",
            "objective": "检查桥梁无人机影像质量",
            "artifact_ids": ["art_001"],
        },
        model_gateway=_FakeModelGateway(),
    )

    assert result == {
        "task_id": "task_001",
        "status": "completed",
        "agent_model": {
            "model_id": "DeepSeek-V4-Flash-4bit",
            "model_version": "omlx-current",
            "alias": "omlx-deepseek-v4-flash",
            "provider": "omlx",
            "runtime": "openai-compatible",
            "api_base_url": "https://omlx.cpolar.cn/v1",
            "is_stub": False,
        },
        "workflow": {
            "task_id": "task_001",
            "status": "completed",
            "current_step": "completed",
            "history": [
                {
                    "step_name": "task_understanding",
                    "output": {
                        "task_type": "bridge_inspection",
                        "objective": "检查桥梁无人机影像质量",
                        "model_result": {
                            "ok": True,
                            "model_id": "DeepSeek-V4-Flash-4bit",
                            "provider": "omlx",
                            "runtime": "openai-compatible",
                            "content": "任务理解完成：检查桥梁无人机影像质量",
                            "usage": {"total_tokens": 12},
                            "error_message": None,
                        },
                    },
                },
                {
                    "step_name": "data_check",
                    "output": {"artifact_id": "art_001"},
                },
                {
                    "step_name": "completed",
                    "output": {"tool_id": "image_quality_check"},
                },
            ],
            "error_step": None,
            "error_message": None,
        },
        "tool_results": [
            {
                "tool_id": "image_quality_check",
                "version": "0.1.0",
                "ok": True,
                "output": {"quality_status": "pass", "artifact_id": "art_001"},
                "error_code": None,
                "error_message": None,
            },
        ],
    }


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
