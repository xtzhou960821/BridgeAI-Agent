from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import pytest

try:
    from fastapi.testclient import TestClient
except (ModuleNotFoundError, RuntimeError) as exc:
    pytest.skip(f"FastAPI test client is not available: {exc}", allow_module_level=True)

from backend.app.domain.artifact_errors import (
    ArtifactNotFoundError,
    ArtifactStorageUnavailableError,
    ArtifactTooLargeError,
    InvalidImageArtifactError,
    UnsupportedArtifactTypeError,
)
from backend.app.domain.artifacts import ArtifactRecord
from backend.app.domain.task_errors import DatabaseUnavailableError
from backend.app.main import create_app
from tests.backend.artifact_test_support import (
    artifact_path,
    image_bytes,
    service_with_local_store,
    upload_jpeg,
)


def test_upload_metadata_and_content_routes(monkeypatch):
    from backend.app.api.v1 import artifacts

    service = _FakeArtifactService(_artifact_record())
    monkeypatch.setattr(
        artifacts,
        "build_artifact_service_from_environment",
        lambda: service,
    )
    client = TestClient(create_app())

    uploaded = client.post(
        "/api/v1/artifacts",
        files={"file": ("bridge.jpg", image_bytes("JPEG"), "image/jpeg")},
    )
    metadata = client.get("/api/v1/artifacts/art_ab12cd34")
    content = client.get("/api/v1/artifacts/art_ab12cd34/content")

    assert uploaded.status_code == 201
    assert uploaded.json()["content_url"] == "/api/v1/artifacts/art_ab12cd34/content"
    assert "storage_key" not in uploaded.json()
    assert metadata.status_code == 200
    assert "storage_key" not in metadata.json()
    assert content.status_code == 200
    assert content.content == b"verified-image-content"
    assert content.headers["content-type"] == "image/jpeg"
    assert content.headers["etag"] == f'"sha256:{service.record.sha256}"'
    assert content.headers["cache-control"].startswith("private")
    assert content.headers["content-disposition"] == "inline"
    assert content.headers["x-content-type-options"] == "nosniff"
    assert service.verified_ids == ["art_ab12cd34"]
    assert service.content_ids == ["art_ab12cd34"]


def test_upload_route_uses_real_service_for_multipart_image(monkeypatch, tmp_path):
    from backend.app.api.v1 import artifacts

    service, _repository = service_with_local_store(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "build_artifact_service_from_environment",
        lambda: service,
    )

    response = TestClient(create_app()).post(
        "/api/v1/artifacts",
        files={"file": ("bridge.jpg", image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["artifact_id"].startswith("art_")
    assert payload["original_filename"] == "bridge.jpg"
    assert payload["mime_type"] == "image/jpeg"
    assert payload["content_url"] == f"/api/v1/artifacts/{payload['artifact_id']}/content"
    assert "storage_key" not in payload
    assert str(tmp_path) not in response.text


def test_content_route_returns_gone_when_real_stored_content_is_missing(
    monkeypatch,
    tmp_path,
):
    from backend.app.api.v1 import artifacts

    service, _repository = service_with_local_store(tmp_path)
    record = upload_jpeg(service)
    artifact_path(tmp_path, record.storage_key).unlink()
    monkeypatch.setattr(
        artifacts,
        "build_artifact_service_from_environment",
        lambda: service,
    )

    response = TestClient(create_app(), raise_server_exceptions=False).get(
        f"/api/v1/artifacts/{record.artifact_id}/content"
    )

    assert response.status_code == 410
    assert response.json()["detail"] == {
        "code": "ARTIFACT_CONTENT_MISSING",
        "message": "Artifact 内容已缺失，请重新上传图片。",
    }


def test_content_route_returns_conflict_when_real_stored_content_is_tampered(
    monkeypatch,
    tmp_path,
):
    from backend.app.api.v1 import artifacts

    service, _repository = service_with_local_store(tmp_path)
    record = upload_jpeg(service)
    artifact_path(tmp_path, record.storage_key).write_bytes(b"tampered")
    monkeypatch.setattr(
        artifacts,
        "build_artifact_service_from_environment",
        lambda: service,
    )

    response = TestClient(create_app(), raise_server_exceptions=False).get(
        f"/api/v1/artifacts/{record.artifact_id}/content"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "ARTIFACT_INTEGRITY_MISMATCH",
        "message": "Artifact 内容完整性校验失败，请重新上传图片。",
    }


@pytest.mark.parametrize(
    ("method", "path", "service_error", "expected_status", "expected_detail"),
    [
        (
            "post",
            "/api/v1/artifacts",
            UnsupportedArtifactTypeError("unsupported"),
            415,
            {"code": "UNSUPPORTED_ARTIFACT_TYPE", "message": "仅支持 JPEG、PNG。"},
        ),
        (
            "post",
            "/api/v1/artifacts",
            ArtifactTooLargeError("too large"),
            413,
            {"code": "ARTIFACT_TOO_LARGE", "message": "图片不得超过 20 MiB。"},
        ),
        (
            "post",
            "/api/v1/artifacts",
            InvalidImageArtifactError("invalid"),
            422,
            {"code": "INVALID_IMAGE_ARTIFACT", "message": "文件不是有效图片或已损坏。"},
        ),
        (
            "get",
            "/api/v1/artifacts/art_missing",
            ArtifactNotFoundError("missing"),
            404,
            {"code": "ARTIFACT_NOT_FOUND", "message": "未找到指定 Artifact。"},
        ),
        (
            "get",
            "/api/v1/artifacts/art_missing/content",
            ArtifactStorageUnavailableError("storage unavailable"),
            503,
            {
                "code": "ARTIFACT_STORAGE_UNAVAILABLE",
                "message": "Artifact 存储当前不可用，请检查存储目录。",
            },
        ),
        (
            "get",
            "/api/v1/artifacts/art_missing",
            DatabaseUnavailableError("database unavailable"),
            503,
            {
                "code": "DATABASE_UNAVAILABLE",
                "message": "PostgreSQL Artifact 元数据存储当前不可用。",
            },
        ),
    ],
)
def test_artifact_routes_translate_known_errors(
    monkeypatch,
    method,
    path,
    service_error,
    expected_status,
    expected_detail,
):
    from backend.app.api.v1 import artifacts

    monkeypatch.setattr(
        artifacts,
        "build_artifact_service_from_environment",
        lambda: _ErrorArtifactService(service_error),
    )
    files = None
    if method == "post":
        files = {"file": ("bridge.jpg", image_bytes("JPEG"), "image/jpeg")}

    response = TestClient(create_app()).request(method, path, files=files)

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


class _FakeArtifactService:
    def __init__(self, record: ArtifactRecord):
        self.record = record
        self.verified_ids: list[str] = []
        self.content_ids: list[str] = []

    def upload(self, source, *, original_filename, claimed_content_type):
        assert source.read(1)
        assert original_filename == "bridge.jpg"
        assert claimed_content_type == "image/jpeg"
        return self.record

    def get(self, artifact_id):
        assert artifact_id == self.record.artifact_id
        return self.record

    def verify(self, artifact_id):
        assert artifact_id == self.record.artifact_id
        self.verified_ids.append(artifact_id)
        return self.record

    def iter_content(self, artifact_id):
        assert artifact_id == self.record.artifact_id
        self.content_ids.append(artifact_id)
        yield b"verified-image-content"


class _ErrorArtifactService:
    def __init__(self, error):
        self._error = error

    def _raise(self, *args, **kwargs):
        raise self._error

    upload = _raise
    get = _raise
    verify = _raise
    iter_content = _raise


def _artifact_record() -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id="art_ab12cd34",
        original_filename="bridge.jpg",
        storage_key="2026/08/art_ab12cd34.jpg",
        sha256="a" * 64,
        size_bytes=123,
        mime_type="image/jpeg",
        width_px=1280,
        height_px=800,
        status="ready",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
