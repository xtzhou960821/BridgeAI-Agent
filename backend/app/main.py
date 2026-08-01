"""FastAPI application factory for BridgeAI-Agent V0.2."""

from __future__ import annotations

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError:  # pragma: no cover - depends on optional runtime dependency.
    FastAPI = None  # type: ignore[assignment]
    CORSMiddleware = None  # type: ignore[assignment]

from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.tasks import router as tasks_router


def create_app():
    """Create the FastAPI application when FastAPI is installed."""

    if FastAPI is None:
        raise RuntimeError(
            "FastAPI is not installed. Install development dependencies before starting the API.",
        )

    app = FastAPI(title="BridgeAI-Agent API", version="0.2.0")
    if CORSMiddleware is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            ],
            allow_origin_regex=r"https?://(127\.0\.0\.1|localhost):517[0-9]",
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if health_router is not None:
        app.include_router(health_router, prefix="/api/v1")
    if tasks_router is not None:
        app.include_router(tasks_router, prefix="/api/v1")
    return app


app = create_app()
