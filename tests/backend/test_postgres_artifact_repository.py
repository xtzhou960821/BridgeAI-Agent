from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.domain.artifact_errors import ArtifactNotFoundError
from backend.app.domain.artifacts import ArtifactRecord
from backend.app.repositories.postgres.artifacts import PostgresArtifactRepository
from backend.app.repositories.postgres.migrate import apply_migrations
from tests.backend.postgres_test_support import (
    require_test_database_url,
    reset_test_tables,
)


def artifact_record(
    *,
    artifact_id: str = "art_001",
    storage_key: str = "00/art_001.jpg",
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        original_filename="bridge-span.jpg",
        storage_key=storage_key,
        sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        size_bytes=483_120,
        mime_type="image/jpeg",
        width_px=1920,
        height_px=1080,
        status="ready",
        created_at=datetime(2026, 8, 1, 4, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def repository():
    database_url = require_test_database_url()
    reset_test_tables(database_url)
    apply_migrations(database_url)
    artifact_repository = PostgresArtifactRepository(database_url)
    yield artifact_repository
    reset_test_tables(database_url)


@pytest.mark.postgres
def test_repository_creates_and_loads_artifact(repository):
    record = artifact_record(
        artifact_id="art_ab12cd34",
        storage_key="ab/art_ab12cd34.jpg",
    )

    created = repository.create_artifact(record)

    assert created == record
    assert repository.get_artifact(record.artifact_id) == record


@pytest.mark.postgres
def test_repository_reports_missing_artifact(repository):
    with pytest.raises(ArtifactNotFoundError) as error:
        repository.get_artifact("art_missing")

    assert error.value.code == "ARTIFACT_NOT_FOUND"


def test_artifact_payloads_exclude_storage_key():
    record = artifact_record()

    assert record.as_payload() == {
        "artifact_id": "art_001",
        "original_filename": "bridge-span.jpg",
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "size_bytes": 483_120,
        "mime_type": "image/jpeg",
        "width_px": 1920,
        "height_px": 1080,
        "status": "ready",
        "created_at": "2026-08-01T04:00:00+00:00",
    }
    assert record.as_checkpoint_payload() == {
        "artifact_id": "art_001",
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "size_bytes": 483_120,
        "mime_type": "image/jpeg",
        "width_px": 1920,
        "height_px": 1080,
        "status": "ready",
    }
