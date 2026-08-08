import pytest

from agent.model_gateway import (
    ModelGatewayConfigurationError,
    OpenAICompatibleModelGateway,
    TaskUnderstandingRequest,
    build_model_gateway_from_environment,
)
from agent.model_profile import default_model_profile


def test_openai_compatible_gateway_posts_task_understanding_request():
    calls = []

    def transport(url, headers, payload, timeout_seconds):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            },
        )
        return {
            "model": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX",
            "choices": [
                {
                    "message": {
                        "content": "任务理解：检查 Artifact 影像质量，并进入数据检查。",
                    },
                },
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 9, "total_tokens": 20},
        }

    gateway = OpenAICompatibleModelGateway(
        profile=default_model_profile({}),
        api_key="secret-token",
        transport=transport,
        timeout_seconds=12.0,
    )

    result = gateway.understand_task(
        TaskUnderstandingRequest(
            task_id="task_001",
            task_type="bridge_inspection",
            objective="检查桥梁无人机影像质量",
            artifact_ids=["art_001"],
        ),
    )

    assert result.as_payload() == {
        "ok": True,
        "model_id": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX",
        "provider": "omlx",
        "runtime": "openai-compatible",
        "content": "任务理解：检查 Artifact 影像质量，并进入数据检查。",
        "usage": {"prompt_tokens": 11, "completion_tokens": 9, "total_tokens": 20},
        "error_message": None,
    }
    assert calls == [
        {
            "url": "http://127.0.0.1:18000/v1/chat/completions",
            "headers": {
                "Authorization": "Bearer secret-token",
                "Content-Type": "application/json",
            },
            "payload": {
                "model": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是 BridgeAI-Agent 的任务理解节点。"
                            "请用简短中文概括任务目标、输入 Artifact 和下一步动作。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "task_id=task_001\n"
                            "task_type=bridge_inspection\n"
                            "objective=检查桥梁无人机影像质量\n"
                            "artifact_ids=art_001"
                        ),
                    },
                ],
                "temperature": 0,
                "max_tokens": 256,
            },
            "timeout_seconds": 12.0,
        },
    ]


def test_model_gateway_requires_api_key_for_non_stub_profile():
    with pytest.raises(ModelGatewayConfigurationError, match="API key is required"):
        build_model_gateway_from_environment(
            environ={},
            profile=default_model_profile({}),
        )
