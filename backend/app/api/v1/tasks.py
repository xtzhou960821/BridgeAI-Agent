"""Optional FastAPI task execution route for local development."""

from __future__ import annotations

from agent.model_gateway import ModelGatewayConfigurationError
from backend.app.services.task_runs import run_inspection_task

try:
    from fastapi import APIRouter, HTTPException
except ModuleNotFoundError:  # pragma: no cover - depends on optional runtime dependency.
    APIRouter = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]


if APIRouter is not None:
    from pydantic import BaseModel, Field

    class TaskRunRequest(BaseModel):
        task_id: str
        task_type: str
        objective: str
        artifact_ids: list[str] = Field(min_length=1)

    router = APIRouter(prefix="/tasks", tags=["tasks"])

    @router.post("/runs")
    def run_task(request: TaskRunRequest) -> dict[str, object]:
        try:
            return run_inspection_task(request.model_dump())
        except ModelGatewayConfigurationError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "MODEL_GATEWAY_NOT_CONFIGURED",
                    "message": (
                        "模型网关未配置：请在后端启动环境中设置 BRIDGEAI_AGENT_API_KEY，"
                        "或将 BRIDGEAI_AGENT_MODEL_IS_STUB=true 用于本地演示。"
                    ),
                },
            ) from exc
else:
    router = None
