"""Optional FastAPI health route for local development."""

from __future__ import annotations

from backend.app.services.health import build_health_payload

try:
    from fastapi import APIRouter
except ModuleNotFoundError:  # pragma: no cover - exercised when FastAPI is installed.
    APIRouter = None  # type: ignore[assignment]


def health_payload() -> dict[str, object]:
    return build_health_payload(
        service_name="bridgeai-api",
        version="0.2.0",
        environment="local_dev",
        components={
            "database": "not_configured",
            "tool_registry": "ready",
            "workflow": "ready",
        },
    )


if APIRouter is not None:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def read_health() -> dict[str, object]:
        return health_payload()
else:
    router = None
