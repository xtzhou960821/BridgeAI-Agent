import psycopg
import pytest

from backend.app.repositories.postgres.connection import probe_database
from backend.app.repositories.postgres.migrate import apply_migrations
from backend.app.services.health import build_health_payload, build_local_health_payload
from tests.backend.postgres_test_support import require_test_database_url, reset_test_tables


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


def test_local_health_marks_database_ready_and_model_gateway_configured():
    payload = build_local_health_payload(
        {
            "BRIDGEAI_ENV": "local_dev",
            "BRIDGEAI_DATABASE_URL": "postgresql://bridgeai:bridgeai@localhost:5432/bridgeai",
            "BRIDGEAI_AGENT_MODEL_ID": "DeepSeek-V4-Flash-4bit",
            "BRIDGEAI_AGENT_API_BASE_URL": "https://omlx.cpolar.cn/v1",
            "BRIDGEAI_AGENT_API_KEY": "secret-token",
        },
        database_probe=lambda _url: True,
        checkpointer_probe=lambda _url: "ready",
    )

    assert payload["components"] == {
        "database": "ready",
        "langgraph_checkpointer": "ready",
        "model_gateway": "configured",
        "tool_registry": "ready",
        "workflow": "ready",
    }


def test_local_health_keeps_database_and_model_gateway_not_configured_when_missing():
    payload = build_local_health_payload({}, database_probe=lambda _url: True)

    assert payload["components"] == {
        "database": "not_configured",
        "langgraph_checkpointer": "unavailable",
        "model_gateway": "not_configured",
        "tool_registry": "ready",
        "workflow": "ready",
    }


def test_local_health_marks_stub_model_gateway_configured_without_api_key():
    payload = build_local_health_payload(
        {"BRIDGEAI_AGENT_MODEL_IS_STUB": "true"},
        database_probe=lambda _url: True,
    )

    assert payload["components"]["model_gateway"] == "configured"


def test_local_health_marks_configured_but_unreachable_database_unavailable():
    payload = build_local_health_payload(
        {"BRIDGEAI_DATABASE_URL": "postgresql://db/bridgeai"},
        database_probe=lambda _url: False,
        checkpointer_probe=lambda _url: "unavailable",
    )

    assert payload["components"]["database"] == "unavailable"


def test_local_health_exposes_not_initialized_checkpointer_without_setup():
    payload = build_local_health_payload(
        environ={"BRIDGEAI_DATABASE_URL": "postgresql://local/bridgeai"},
        database_probe=lambda _url: True,
        checkpointer_probe=lambda _url: "not_initialized",
    )

    assert payload["components"]["langgraph_checkpointer"] == "not_initialized"


def test_local_health_exposes_unavailable_checkpointer_without_setup():
    payload = build_local_health_payload(
        environ={"BRIDGEAI_DATABASE_URL": "postgresql://local/bridgeai"},
        database_probe=lambda _url: True,
        checkpointer_probe=lambda _url: "unavailable",
    )

    assert payload["components"]["langgraph_checkpointer"] == "unavailable"


@pytest.mark.postgres
def test_database_probe_requires_artifact_table():
    database_url = require_test_database_url()
    reset_test_tables(database_url)
    try:
        apply_migrations(database_url)
        assert probe_database(database_url) is True

        with psycopg.connect(database_url) as connection:
            connection.execute("DROP TABLE inspection_artifacts")

        assert probe_database(database_url) is False
    finally:
        reset_test_tables(database_url)
