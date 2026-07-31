from backend.app.services.health import build_health_payload


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
