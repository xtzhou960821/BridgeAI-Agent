"""Health payload helpers for backend readiness checks."""

from __future__ import annotations


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
