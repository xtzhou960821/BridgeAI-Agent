"""Verified JPEG and PNG Artifact ingestion and retrieval."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
import hashlib
from io import BytesIO
import os
from pathlib import Path
from typing import BinaryIO
import uuid

from PIL import Image, UnidentifiedImageError

from backend.app.domain.artifact_errors import (
    ArtifactIntegrityMismatchError,
    ArtifactNotReadyError,
    InvalidImageArtifactError,
    UnsupportedArtifactTypeError,
)
from backend.app.domain.artifacts import ArtifactRecord, ArtifactRepository
from backend.app.domain.task_errors import DatabaseUnavailableError
from backend.app.repositories.postgres.artifacts import PostgresArtifactRepository
from backend.app.repositories.postgres.connection import get_database_url
from backend.app.storage.artifacts import ArtifactStore, LocalArtifactStore, StagedArtifact


_MAX_ARTIFACT_BYTES = 20 * 1024 * 1024
_FORMAT_DETAILS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
}


class ArtifactService:
    def __init__(self, repository: ArtifactRepository, store: ArtifactStore) -> None:
        self._repository = repository
        self._store = store

    def upload(
        self,
        source: BinaryIO,
        *,
        original_filename: str,
        claimed_content_type: str | None,
    ) -> ArtifactRecord:
        """Stage and decode an image before persisting immutable metadata."""

        # The client declaration is retained by the caller's audit boundary only.
        # Decoded bytes are the sole authority for type selection here.
        del claimed_content_type
        staged = self._store.stage(source, max_bytes=_MAX_ARTIFACT_BYTES)
        try:
            with self._store.open_staged(staged) as stream:
                image_format, width_px, height_px = _decode_image(stream.read())
        except _InvalidImageData as error:
            self._discard_stage(staged)
            raise InvalidImageArtifactError("Artifact content is not a valid image") from error

        details = _FORMAT_DETAILS.get(image_format)
        if details is None:
            self._discard_stage(staged)
            raise UnsupportedArtifactTypeError(
                "Only decoded JPEG and PNG Artifact content is supported"
            )

        mime_type, extension = details
        artifact_id = f"art_{uuid.uuid4().hex}"
        storage_key = self._store.finalize(staged, artifact_id, extension)
        record = ArtifactRecord(
            artifact_id=artifact_id,
            original_filename=Path(original_filename).name.strip()[:255],
            storage_key=storage_key,
            sha256=staged.sha256,
            size_bytes=staged.size_bytes,
            mime_type=mime_type,
            width_px=width_px,
            height_px=height_px,
            status="ready",
            created_at=datetime.now(UTC),
        )
        try:
            return self._repository.create_artifact(record)
        except Exception:
            # Metadata is authoritative: do not retain orphaned finalized bytes.
            with suppress(Exception):
                self._store.delete(storage_key)
            raise

    def get(self, artifact_id: str) -> ArtifactRecord:
        return self._repository.get_artifact(artifact_id)

    def require_ready(self, artifact_id: str) -> ArtifactRecord:
        record = self.get(artifact_id)
        if record.status != "ready":
            raise ArtifactNotReadyError(f"Artifact {artifact_id} is not ready")
        return record

    def verify(self, artifact_id: str) -> ArtifactRecord:
        record = self.require_ready(artifact_id)
        with self._store.open(record.storage_key) as stream:
            content = stream.read()

        try:
            image_format, width_px, height_px = _decode_image(content)
        except _InvalidImageData as error:
            raise ArtifactIntegrityMismatchError(
                "Artifact content no longer matches its verified metadata"
            ) from error

        details = _FORMAT_DETAILS.get(image_format)
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if (
            details is None
            or len(content) != record.size_bytes
            or actual_sha256 != record.sha256
            or details[0] != record.mime_type
            or width_px != record.width_px
            or height_px != record.height_px
        ):
            raise ArtifactIntegrityMismatchError(
                "Artifact content no longer matches its verified metadata"
            )
        return record

    @contextmanager
    def open_verified(self, artifact_id: str) -> Iterator[tuple[ArtifactRecord, BinaryIO]]:
        record = self.verify(artifact_id)
        with self._store.open(record.storage_key) as stream:
            yield record, stream

    def iter_content(self, artifact_id: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        with self.open_verified(artifact_id) as (_record, stream):
            while chunk := stream.read(chunk_size):
                yield chunk

    def _discard_stage(self, staged: StagedArtifact) -> None:
        with suppress(Exception):
            self._store.delete(f".staging/{staged.staging_key}")


def build_artifact_service_from_environment(
    environ: Mapping[str, str] | None = None,
) -> ArtifactService:
    source = os.environ if environ is None else environ
    database_url = get_database_url(source)
    if not database_url:
        raise DatabaseUnavailableError("PostgreSQL artifact store is unavailable")
    root = Path(source.get("BRIDGEAI_ARTIFACT_STORAGE_ROOT", "var/artifacts"))
    return ArtifactService(PostgresArtifactRepository(database_url), LocalArtifactStore(root))


class _InvalidImageData(Exception):
    """Internal marker that keeps malformed decoded content out of the service API."""


def _decode_image(content: bytes) -> tuple[str, int, int]:
    """Verify and fully load image content before returning its decoded shape."""

    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image.load()
            if image.format is None:
                raise _InvalidImageData("Image has no decoded format")
            return image.format, image.width, image.height
    except _InvalidImageData:
        raise
    except (Image.DecompressionBombError, OSError, SyntaxError, UnidentifiedImageError, ValueError) as error:
        raise _InvalidImageData("Image decoding failed") from error
