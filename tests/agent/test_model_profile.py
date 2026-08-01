from agent.model_profile import default_model_profile


def test_default_model_profile_uses_omlx_deepseek_chat_model():
    profile = default_model_profile({})

    assert profile.as_payload() == {
        "model_id": "DeepSeek-V4-Flash-4bit",
        "model_version": "omlx-current",
        "alias": "omlx-deepseek-v4-flash",
        "provider": "omlx",
        "runtime": "openai-compatible",
        "api_base_url": "https://omlx.cpolar.cn/v1",
        "is_stub": False,
    }


def test_model_profile_can_be_loaded_from_environment_mapping():
    profile = default_model_profile(
        {
            "BRIDGEAI_AGENT_MODEL_ID": "qwen3_mlx_local",
            "BRIDGEAI_AGENT_MODEL_VERSION": "2026-07-31",
            "BRIDGEAI_AGENT_MODEL_ALIAS": "local-llm",
            "BRIDGEAI_AGENT_MODEL_PROVIDER": "mlx",
            "BRIDGEAI_AGENT_MODEL_RUNTIME": "mlx",
            "BRIDGEAI_AGENT_API_BASE_URL": "http://127.0.0.1:8001/v1",
            "BRIDGEAI_AGENT_MODEL_IS_STUB": "false",
        },
    )

    assert profile.as_payload() == {
        "model_id": "qwen3_mlx_local",
        "model_version": "2026-07-31",
        "alias": "local-llm",
        "provider": "mlx",
        "runtime": "mlx",
        "api_base_url": "http://127.0.0.1:8001/v1",
        "is_stub": False,
    }


def test_model_profile_payload_does_not_expose_api_key():
    profile = default_model_profile({"BRIDGEAI_AGENT_API_KEY": "secret-token"})

    assert "api_key" not in profile.as_payload()
    assert "secret-token" not in profile.as_payload().values()
