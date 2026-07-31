"""FastAPI application factory for BridgeAI-Agent V0.2."""

from __future__ import annotations

try:
    from fastapi import FastAPI
except ModuleNotFoundError:  # pragma: no cover - depends on optional runtime dependency.
    FastAPI = None  # type: ignore[assignment]

from backend.app.api.v1.health import router as health_router


def create_app():
    """Create the FastAPI application when FastAPI is installed."""

    if FastAPI is None:
        raise RuntimeError(
            "FastAPI is not installed. Install development dependencies before starting the API.",
        )

    app = FastAPI(title="BridgeAI-Agent API", version="0.2.0")
    if health_router is not None:
        app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
