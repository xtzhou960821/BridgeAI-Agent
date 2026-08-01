"""Immutable metadata records for verified image Artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    original_filename: str
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str
    width_px: int
    height_px: int
    status: str
    created_at: datetime

    def as_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "original_filename": self.original_filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    def as_checkpoint_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "status": self.status,
        }


class ArtifactRepository(Protocol):
    def create_artifact(self, record: ArtifactRecord) -> ArtifactRecord: ...

    def get_artifact(self, artifact_id: str) -> ArtifactRecord: ...
