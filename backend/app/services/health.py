"""Health payload helpers for backend readiness checks."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from agent.model_profile import default_model_profile
from backend.app.repositories.postgres.connection import (
    get_database_url,
    probe_database,
)


def build_health_payload(
    service_name: str,
    version: str,
    environment: str,
    components: dict[str, str],
) -> dict[str, object]:
    """Build the stable health payload returned by backend health endpoints."""

    return {
        "service": service_name,
        "version": version,
        "environment": environment,
        "status": "ready",
        "components": components,
    }


def build_local_health_payload(
    environ: Mapping[str, str] | None = None,
    database_probe: Callable[[str], bool] = probe_database,
) -> dict[str, object]:
    """Build the local API health payload from runtime configuration."""

    source = os.environ if environ is None else environ
    return build_health_payload(
        service_name="bridgeai-api",
        version=source.get("BRIDGEAI_API_VERSION", "0.2.0"),
        environment=source.get("BRIDGEAI_ENV", "local_dev"),
        components={
            "database": _database_status(source, database_probe),
            "model_gateway": _model_gateway_status(source),
            "tool_registry": "ready",
            "workflow": "ready",
        },
    )


def _database_status(
    source: Mapping[str, str],
    database_probe: Callable[[str], bool],
) -> str:
    database_url = get_database_url(source)
    if not database_url:
        return "not_configured"
    if database_probe(database_url):
        return "ready"
    return "unavailable"


def _model_gateway_status(source: Mapping[str, str]) -> str:
    profile = default_model_profile(source)
    has_profile = bool(profile.model_id.strip() and profile.api_base_url.strip())
    has_api_key = bool(source.get("BRIDGEAI_AGENT_API_KEY", "").strip())
    if has_profile and (profile.is_stub or has_api_key):
        return "configured"
    return "not_configured"
