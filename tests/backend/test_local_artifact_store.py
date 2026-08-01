from __future__ import annotations

import hashlib
from io import BytesIO

import pytest

from backend.app.domain.artifact_errors import (
    ArtifactStorageUnavailableError,
    ArtifactTooLargeError,
)
from backend.app.storage.artifacts import LocalArtifactStore


def test_local_store_stages_hashes_finalizes_and_reopens(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")
    staged = store.stage(BytesIO(b"bridge-image"), max_bytes=20 * 1024 * 1024)

    assert staged.size_bytes == 12
    assert staged.sha256 == hashlib.sha256(b"bridge-image").hexdigest()

    key = store.finalize(staged, "art_ab12cd34", ".jpg")
    assert key == "ab/art_ab12cd34.jpg"
    with store.open(key) as stream:
        assert stream.read() == b"bridge-image"


def test_local_store_rejects_oversized_stream_and_removes_stage(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ArtifactTooLargeError) as error:
        store.stage(BytesIO(b"x" * 11), max_bytes=10)

    assert error.value.code == "ARTIFACT_TOO_LARGE"
    assert list((tmp_path / "artifacts" / ".staging").glob("*")) == []


def test_local_store_rejects_path_traversal_without_touching_outside_file(tmp_path):
    root = tmp_path / "artifacts"
    outside = tmp_path / "escape"
    outside.write_bytes(b"do not delete")
    store = LocalArtifactStore(root)

    with pytest.raises(ArtifactStorageUnavailableError):
        store.open("../escape")
    with pytest.raises(ArtifactStorageUnavailableError):
        store.delete("../escape")

    assert outside.read_bytes() == b"do not delete"


def test_local_store_refuses_a_symlinked_storage_path(tmp_path):
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "artifact.jpg").write_bytes(b"do not open")
    root.mkdir()
    (root / "ab").symlink_to(outside, target_is_directory=True)
    store = LocalArtifactStore(root)

    with pytest.raises(ArtifactStorageUnavailableError):
        store.open("ab/artifact.jpg")


def test_local_store_deletes_only_a_root_contained_key(tmp_path):
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    staged = store.stage(BytesIO(b"bridge-image"), max_bytes=20 * 1024 * 1024)
    key = store.finalize(staged, "art_ab12cd34", ".png")

    store.delete(key)

    assert not (root / key).exists()
