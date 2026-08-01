"""Real local-store fixtures for Artifact service tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from backend.app.domain.artifacts import ArtifactRecord
from backend.app.services.artifacts import ArtifactService
from backend.app.storage.artifacts import LocalArtifactStore


class InMemoryArtifactRepository:
    """Small repository double that keeps storage behavior real."""

    def __init__(self) -> None:
        self.records: dict[str, ArtifactRecord] = {}
        self.create_error: Exception | None = None

    def create_artifact(self, record: ArtifactRecord) -> ArtifactRecord:
        if self.create_error is not None:
            raise self.create_error
        self.records[record.artifact_id] = record
        return record

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        return self.records[artifact_id]


def image_bytes(
    image_format: str = "JPEG",
    *,
    size: tuple[int, int] = (1280, 800),
    color: int = 128,
) -> bytes:
    stream = BytesIO()
    Image.new("L", size, color=color).save(stream, format=image_format)
    return stream.getvalue()


def service_with_local_store(tmp_path: Path) -> tuple[ArtifactService, InMemoryArtifactRepository]:
    repository = InMemoryArtifactRepository()
    return ArtifactService(repository, LocalArtifactStore(tmp_path / "artifacts")), repository


def upload_jpeg(service: ArtifactService) -> ArtifactRecord:
    return service.upload(
        BytesIO(image_bytes("JPEG")),
        original_filename="bridge.jpg",
        claimed_content_type="image/jpeg",
    )


def artifact_path(tmp_path: Path, storage_key: str) -> Path:
    return tmp_path / "artifacts" / storage_key
