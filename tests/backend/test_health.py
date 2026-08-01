from backend.app.services.health import build_health_payload, build_local_health_payload


def test_health_payload_reports_service_version_environment_and_components():
    payload = build_health_payload(
        service_name="bridgeai-api",
        version="0.2.0",
        environment="local_dev",
        components={"database": "not_configured", "tool_registry": "ready"},
    )

    assert payload == {
        "service": "bridgeai-api",
        "version": "0.2.0",
        "environment": "local_dev",
        "status": "ready",
        "components": {"database": "not_configured", "tool_registry": "ready"},
    }


def test_local_health_marks_database_and_model_gateway_configured_from_environment():
    payload = build_local_health_payload(
        {
            "BRIDGEAI_ENV": "local_dev",
            "BRIDGEAI_DATABASE_URL": "postgresql://bridgeai:bridgeai@localhost:5432/bridgeai",
            "BRIDGEAI_AGENT_MODEL_ID": "DeepSeek-V4-Flash-4bit",
            "BRIDGEAI_AGENT_API_BASE_URL": "https://omlx.cpolar.cn/v1",
            "BRIDGEAI_AGENT_API_KEY": "secret-token",
        },
    )

    assert payload["components"] == {
        "database": "configured",
        "model_gateway": "configured",
        "tool_registry": "ready",
        "workflow": "ready",
    }


def test_local_health_keeps_database_and_model_gateway_not_configured_when_missing():
    payload = build_local_health_payload({})

    assert payload["components"] == {
        "database": "not_configured",
        "model_gateway": "not_configured",
        "tool_registry": "ready",
        "workflow": "ready",
    }


def test_local_health_marks_stub_model_gateway_configured_without_api_key():
    payload = build_local_health_payload({"BRIDGEAI_AGENT_MODEL_IS_STUB": "true"})

    assert payload["components"]["model_gateway"] == "configured"
