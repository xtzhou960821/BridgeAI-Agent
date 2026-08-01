"""Safe local byte storage for persisted Artifacts."""

from __future__ import annotations

from contextlib import contextmanager, suppress
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import BinaryIO, ContextManager, Iterator, Protocol
from uuid import uuid4

from backend.app.domain.artifact_errors import (
    ArtifactContentMissingError,
    ArtifactStorageUnavailableError,
    ArtifactTooLargeError,
)


_CHUNK_SIZE = 1024 * 1024
_ALLOWED_EXTENSIONS = {".jpg", ".png"}


@dataclass(frozen=True)
class StagedArtifact:
    staging_key: str
    size_bytes: int
    sha256: str


class ArtifactStore(Protocol):
    def stage(self, source: BinaryIO, *, max_bytes: int) -> StagedArtifact: ...

    def open_staged(self, staged: StagedArtifact) -> ContextManager[BinaryIO]: ...

    def finalize(self, staged: StagedArtifact, artifact_id: str, extension: str) -> str: ...

    def open(self, storage_key: str) -> ContextManager[BinaryIO]: ...

    def delete(self, storage_key: str) -> None: ...


class LocalArtifactStore:
    """Store staged and finalized bytes under one non-symlinked directory."""

    def __init__(self, root: Path) -> None:
        self._root = root.absolute()

    def stage(self, source: BinaryIO, *, max_bytes: int) -> StagedArtifact:
        staging_key = uuid4().hex
        stage_path = self._staging_path(staging_key)
        digest = hashlib.sha256()
        size_bytes = 0

        try:
            stage_path.parent.mkdir(parents=True, exist_ok=True)
            self._assert_no_symlinks(stage_path)
            with stage_path.open("xb") as destination:
                while chunk := source.read(_CHUNK_SIZE):
                    size_bytes += len(chunk)
                    if size_bytes > max_bytes:
                        raise ArtifactTooLargeError("Artifact exceeds the configured size limit")
                    digest.update(chunk)
                    destination.write(chunk)
        except ArtifactTooLargeError:
            self._unlink_stage(stage_path)
            raise
        except OSError as error:
            self._unlink_stage(stage_path)
            raise ArtifactStorageUnavailableError("Artifact storage is unavailable") from error

        return StagedArtifact(
            staging_key=staging_key,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )

    def open_staged(self, staged: StagedArtifact) -> ContextManager[BinaryIO]:
        return self._open_path(self._staging_path(staged.staging_key))

    def finalize(self, staged: StagedArtifact, artifact_id: str, extension: str) -> str:
        if extension not in _ALLOWED_EXTENSIONS:
            raise ValueError("Artifact extension must be .jpg or .png")
        if not artifact_id.startswith("art_") or len(artifact_id.removeprefix("art_")) < 2:
            raise ValueError("Artifact ID must begin with art_ and contain two characters")

        prefix = artifact_id.removeprefix("art_")[:2]
        storage_key = f"{prefix}/{artifact_id}{extension}"
        stage_path = self._staging_path(staged.staging_key)
        target_path = self._resolve(storage_key)

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            self._assert_no_symlinks(target_path)
            os.replace(stage_path, target_path)
        except FileNotFoundError as error:
            raise ArtifactContentMissingError("Staged Artifact content is missing") from error
        except OSError as error:
            raise ArtifactStorageUnavailableError("Artifact storage is unavailable") from error

        return storage_key

    def open(self, storage_key: str) -> ContextManager[BinaryIO]:
        return self._open_path(self._resolve(storage_key))

    def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            raise ArtifactStorageUnavailableError("Artifact storage is unavailable") from error

    def _staging_path(self, staging_key: str) -> Path:
        if Path(staging_key).name != staging_key or not staging_key:
            raise ArtifactStorageUnavailableError("Invalid Artifact staging key")
        return self._resolve(f".staging/{staging_key}")

    def _resolve(self, storage_key: str) -> Path:
        key_path = Path(storage_key)
        if (
            key_path.is_absolute()
            or not key_path.parts
            or any(part == ".." for part in key_path.parts)
        ):
            raise ArtifactStorageUnavailableError("Artifact storage key is outside the root")

        self._ensure_root()
        candidate = self._root.joinpath(*key_path.parts)
        self._assert_no_symlinks(candidate)
        return candidate

    def _ensure_root(self) -> None:
        self._assert_root_has_no_symlink_ancestors()
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ArtifactStorageUnavailableError("Artifact storage is unavailable") from error
        if not self._root.is_dir() or self._root.is_symlink():
            raise ArtifactStorageUnavailableError("Artifact storage root is invalid")

    def _assert_root_has_no_symlink_ancestors(self) -> None:
        current = Path(self._root.anchor)
        for part in self._root.parts[1:]:
            current = current / part
            if current.is_symlink():
                raise ArtifactStorageUnavailableError(
                    "Artifact storage root must not contain symlinks"
                )

    def _assert_no_symlinks(self, path: Path) -> None:
        current = self._root
        if current.is_symlink():
            raise ArtifactStorageUnavailableError("Artifact storage root must not be a symlink")
        try:
            relative_parts = path.relative_to(self._root).parts
        except ValueError as error:
            raise ArtifactStorageUnavailableError("Artifact storage path is outside the root") from error
        for part in relative_parts:
            current = current / part
            if current.is_symlink():
                raise ArtifactStorageUnavailableError("Artifact storage path must not contain symlinks")

    @contextmanager
    def _open_path(self, path: Path) -> Iterator[BinaryIO]:
        try:
            stream = path.open("rb")
        except FileNotFoundError as error:
            raise ArtifactContentMissingError("Artifact content is missing") from error
        except OSError as error:
            raise ArtifactStorageUnavailableError("Artifact storage is unavailable") from error
        try:
            yield stream
        finally:
            stream.close()

    @staticmethod
    def _unlink_stage(stage_path: Path) -> None:
        with suppress(OSError):
            stage_path.unlink(missing_ok=True)
