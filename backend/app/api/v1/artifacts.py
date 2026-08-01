"""FastAPI routes for verified image Artifact ingestion and retrieval."""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn, TypeVar

from backend.app.domain.artifact_errors import (
    ArtifactContentMissingError,
    ArtifactIntegrityMismatchError,
    ArtifactNotFoundError,
    ArtifactStorageUnavailableError,
    ArtifactTooLargeError,
    InvalidImageArtifactError,
    UnsupportedArtifactTypeError,
)
from backend.app.domain.artifacts import ArtifactRecord
from backend.app.domain.task_errors import DatabaseUnavailableError
from backend.app.services.artifacts import (
    ArtifactService,
    build_artifact_service_from_environment,
)

try:
    from fastapi import APIRouter, HTTPException, UploadFile, status
    from fastapi.responses import StreamingResponse
except ModuleNotFoundError:  # pragma: no cover - depends on optional runtime dependency.
    APIRouter = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    UploadFile = None  # type: ignore[assignment]
    StreamingResponse = None  # type: ignore[assignment]
    status = None  # type: ignore[assignment]


_Result = TypeVar("_Result")

ERROR_RESPONSES = {
    UnsupportedArtifactTypeError: (415, "UNSUPPORTED_ARTIFACT_TYPE", "仅支持 JPEG、PNG。"),
    ArtifactTooLargeError: (413, "ARTIFACT_TOO_LARGE", "图片不得超过 20 MiB。"),
    InvalidImageArtifactError: (422, "INVALID_IMAGE_ARTIFACT", "文件不是有效图片或已损坏。"),
    ArtifactNotFoundError: (404, "ARTIFACT_NOT_FOUND", "未找到指定 Artifact。"),
    ArtifactContentMissingError: (
        410,
        "ARTIFACT_CONTENT_MISSING",
        "Artifact 内容已缺失，请重新上传图片。",
    ),
    ArtifactIntegrityMismatchError: (
        409,
        "ARTIFACT_INTEGRITY_MISMATCH",
        "Artifact 内容完整性校验失败，请重新上传图片。",
    ),
    ArtifactStorageUnavailableError: (
        503,
        "ARTIFACT_STORAGE_UNAVAILABLE",
        "Artifact 存储当前不可用，请检查存储目录。",
    ),
    DatabaseUnavailableError: (
        503,
        "DATABASE_UNAVAILABLE",
        "PostgreSQL Artifact 元数据存储当前不可用。",
    ),
}


if APIRouter is not None:
    router = APIRouter(prefix="/artifacts", tags=["artifacts"])

    @router.post("", status_code=status.HTTP_201_CREATED)
    def upload_artifact(file: UploadFile) -> dict[str, object]:
        record = _service_call(
            lambda service: service.upload(
                file.file,
                original_filename=file.filename or "upload",
                claimed_content_type=file.content_type,
            ),
        )
        return _safe_payload(record)

    @router.get("/{artifact_id}")
    def get_artifact(artifact_id: str) -> dict[str, object]:
        return _safe_payload(_service_call(lambda service: service.get(artifact_id)))

    @router.get("/{artifact_id}/content")
    def get_artifact_content(artifact_id: str) -> StreamingResponse:
        try:
            service = build_artifact_service_from_environment()
            record = service.verify(artifact_id)
            content = service.iter_content(artifact_id)
        except tuple(ERROR_RESPONSES) as exc:
            _raise_http_error(exc)

        return StreamingResponse(
            content,
            media_type=record.mime_type,
            headers={
                "ETag": f'"sha256:{record.sha256}"',
                "Cache-Control": "private, max-age=3600",
                "Content-Disposition": "inline",
                "X-Content-Type-Options": "nosniff",
            },
        )
else:
    router = None


def _safe_payload(record: ArtifactRecord) -> dict[str, object]:
    payload = record.as_payload()
    payload["content_url"] = f"/api/v1/artifacts/{record.artifact_id}/content"
    return payload


def _service_call(operation: Callable[[ArtifactService], _Result]) -> _Result:
    try:
        return operation(build_artifact_service_from_environment())
    except tuple(ERROR_RESPONSES) as exc:
        _raise_http_error(exc)


def _raise_http_error(exc: Exception) -> NoReturn:
    if HTTPException is None:  # pragma: no cover - FastAPI-only path.
        raise RuntimeError("FastAPI is not installed") from exc
    status_code, code, message = ERROR_RESPONSES[type(exc)]
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    ) from exc
