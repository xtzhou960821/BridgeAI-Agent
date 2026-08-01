"""Synchronous PostgreSQL repository for immutable Artifact metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg.rows import dict_row

from backend.app.domain.artifact_errors import ArtifactNotFoundError
from backend.app.domain.artifacts import ArtifactRecord
from backend.app.domain.task_errors import DatabaseUnavailableError
from backend.app.repositories.postgres.connection import connect


_ARTIFACT_COLUMNS = (
    "artifact_id, original_filename, storage_key, sha256, size_bytes, mime_type, "
    "width_px, height_px, status, created_at"
)


class PostgresArtifactRepository:
    """Store and load immutable metadata for verified image Artifacts."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def create_artifact(self, record: ArtifactRecord) -> ArtifactRecord:
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "INSERT INTO inspection_artifacts ("
                        "artifact_id, original_filename, storage_key, sha256, size_bytes, "
                        "mime_type, width_px, height_px, status, created_at"
                        ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        f"RETURNING {_ARTIFACT_COLUMNS}",
                        (
                            record.artifact_id,
                            record.original_filename,
                            record.storage_key,
                            record.sha256,
                            record.size_bytes,
                            record.mime_type,
                            record.width_px,
                            record.height_px,
                            record.status,
                            record.created_at,
                        ),
                    )
                    return _artifact_from_row(cursor.fetchone())
        except psycopg.Error as exc:
            raise _database_unavailable() from exc

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        try:
            with connect(self._database_url) as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"SELECT {_ARTIFACT_COLUMNS} FROM inspection_artifacts "
                        "WHERE artifact_id = %s",
                        (artifact_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ArtifactNotFoundError(
                            f"Artifact {artifact_id} was not found",
                        )
                    return _artifact_from_row(row)
        except psycopg.Error as exc:
            raise _database_unavailable() from exc


def _artifact_from_row(row: Mapping[str, Any]) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=str(row["artifact_id"]),
        original_filename=str(row["original_filename"]),
        storage_key=str(row["storage_key"]),
        sha256=str(row["sha256"]),
        size_bytes=int(row["size_bytes"]),
        mime_type=str(row["mime_type"]),
        width_px=int(row["width_px"]),
        height_px=int(row["height_px"]),
        status=str(row["status"]),
        created_at=row["created_at"],
    )


def _database_unavailable() -> DatabaseUnavailableError:
    return DatabaseUnavailableError("PostgreSQL artifact store is unavailable")
