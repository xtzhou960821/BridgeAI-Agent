"""Health payload helpers for backend readiness checks."""

from __future__ import annotations

import os
from collections.abc import Mapping

from agent.model_profile import default_model_profile


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
) -> dict[str, object]:
    """Build the local API health payload from runtime configuration."""

    source = os.environ if environ is None else environ
    return build_health_payload(
        service_name="bridgeai-api",
        version=source.get("BRIDGEAI_API_VERSION", "0.2.0"),
        environment=source.get("BRIDGEAI_ENV", "local_dev"),
        components={
            "database": _configured(source, "BRIDGEAI_DATABASE_URL"),
            "model_gateway": _model_gateway_status(source),
            "tool_registry": "ready",
            "workflow": "ready",
        },
    )


def _configured(source: Mapping[str, str], *names: str) -> str:
    if all(source.get(name, "").strip() for name in names):
        return "configured"
    return "not_configured"


def _model_gateway_status(source: Mapping[str, str]) -> str:
    profile = default_model_profile(source)
    has_profile = bool(profile.model_id.strip() and profile.api_base_url.strip())
    has_api_key = bool(source.get("BRIDGEAI_AGENT_API_KEY", "").strip())
    if has_profile and (profile.is_stub or has_api_key):
        return "configured"
    return "not_configured"
