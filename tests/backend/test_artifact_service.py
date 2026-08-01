from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pytest
from PIL import Image

from backend.app.domain.artifact_errors import (
    ArtifactContentMissingError,
    ArtifactIntegrityMismatchError,
    ArtifactNotReadyError,
    ArtifactStorageUnavailableError,
    ArtifactTooLargeError,
    InvalidImageArtifactError,
    UnsupportedArtifactTypeError,
)
from backend.app.domain.task_errors import DatabaseUnavailableError
from backend.app.services.artifacts import ArtifactService
from backend.app.storage.artifacts import LocalArtifactStore
from tests.backend.artifact_test_support import (
    InMemoryArtifactRepository,
    artifact_path,
    image_bytes,
    service_with_local_store,
    upload_jpeg,
)


def test_upload_uses_decoded_type_and_persists_safe_metadata(tmp_path):
    service, repository = service_with_local_store(tmp_path)

    record = service.upload(
        BytesIO(image_bytes("JPEG")),
        original_filename="../bridge.jpg",
        claimed_content_type="text/plain",
    )

    assert record.original_filename == "bridge.jpg"
    assert record.mime_type == "image/jpeg"
    assert record.storage_key.endswith(".jpg")
    assert repository.get_artifact(record.artifact_id) == record
    assert "storage_key" not in service.get(record.artifact_id).as_payload()


def test_upload_accepts_png_from_decoded_content(tmp_path):
    service, _repository = service_with_local_store(tmp_path)

    record = service.upload(
        BytesIO(image_bytes("PNG", size=(320, 240))),
        original_filename="bridge.png",
        claimed_content_type=None,
    )

    assert (record.mime_type, record.storage_key[-4:], record.width_px, record.height_px) == (
        "image/png",
        ".png",
        320,
        240,
    )


def test_upload_rejects_corrupt_bytes_and_discards_the_stage(tmp_path):
    service, _repository = service_with_local_store(tmp_path)

    with pytest.raises(InvalidImageArtifactError) as error:
        service.upload(
            BytesIO(b"not an image"),
            original_filename="bridge.jpg",
            claimed_content_type="image/jpeg",
        )

    assert error.value.code == "INVALID_IMAGE_ARTIFACT"
    assert list((tmp_path / "artifacts" / ".staging").glob("*")) == []


def test_upload_rejects_a_decoded_but_unsupported_gif(tmp_path):
    service, _repository = service_with_local_store(tmp_path)

    with pytest.raises(UnsupportedArtifactTypeError) as error:
        service.upload(
            BytesIO(image_bytes("GIF")),
            original_filename="bridge.gif",
            claimed_content_type="image/gif",
        )

    assert error.value.code == "UNSUPPORTED_ARTIFACT_TYPE"
    assert list((tmp_path / "artifacts" / ".staging").glob("*")) == []


def test_upload_rejects_animated_png_and_discards_the_stage(tmp_path):
    service, repository = service_with_local_store(tmp_path)

    with pytest.raises(UnsupportedArtifactTypeError) as error:
        service.upload(
            BytesIO(_animated_png_bytes()),
            original_filename="bridge-animation.png",
            claimed_content_type="image/png",
        )

    assert error.value.code == "UNSUPPORTED_ARTIFACT_TYPE"
    assert repository.records == {}
    assert list((tmp_path / "artifacts" / ".staging").glob("*")) == []


def test_upload_rejects_decompression_bomb_warning_and_discards_the_stage(
    monkeypatch,
    tmp_path,
):
    content = image_bytes("PNG", size=(20, 20))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 300)
    service, repository = service_with_local_store(tmp_path)

    with pytest.raises(InvalidImageArtifactError) as error:
        service.upload(
            BytesIO(content),
            original_filename="oversized-dimensions.png",
            claimed_content_type="image/png",
        )

    assert error.value.code == "INVALID_IMAGE_ARTIFACT"
    assert repository.records == {}
    assert list((tmp_path / "artifacts" / ".staging").glob("*")) == []


def test_upload_enforces_a_fixed_twenty_mebibyte_limit(tmp_path):
    service, _repository = service_with_local_store(tmp_path)

    with pytest.raises(ArtifactTooLargeError) as error:
        service.upload(
            BytesIO(b"x" * (20 * 1024 * 1024 + 1)),
            original_filename="oversized.jpg",
            claimed_content_type="image/jpeg",
        )

    assert error.value.code == "ARTIFACT_TOO_LARGE"


def test_upload_deletes_finalized_content_when_metadata_insert_fails(tmp_path):
    service, repository = service_with_local_store(tmp_path)
    repository.create_error = DatabaseUnavailableError("database unavailable")

    with pytest.raises(DatabaseUnavailableError, match="database unavailable"):
        service.upload(
            BytesIO(image_bytes("JPEG")),
            original_filename="bridge.jpg",
            claimed_content_type="image/jpeg",
        )

    assert list((tmp_path / "artifacts").rglob("art_*.jpg")) == []


def test_verify_rejects_modified_content(tmp_path):
    service, _repository = service_with_local_store(tmp_path)
    record = upload_jpeg(service)
    artifact_path(tmp_path, record.storage_key).write_bytes(b"changed")

    with pytest.raises(ArtifactIntegrityMismatchError) as error:
        service.verify(record.artifact_id)
    assert error.value.code == "ARTIFACT_INTEGRITY_MISMATCH"


def test_open_verified_reports_missing_content(tmp_path):
    service, _repository = service_with_local_store(tmp_path)
    record = upload_jpeg(service)
    artifact_path(tmp_path, record.storage_key).unlink()

    with pytest.raises(ArtifactContentMissingError) as error:
        with service.open_verified(record.artifact_id):
            pass

    assert error.value.code == "ARTIFACT_CONTENT_MISSING"


def test_ready_enforcement_blocks_non_ready_artifacts(tmp_path):
    service, repository = service_with_local_store(tmp_path)
    record = upload_jpeg(service)
    repository.records[record.artifact_id] = replace(record, status="pending")

    with pytest.raises(ArtifactNotReadyError) as error:
        service.require_ready(record.artifact_id)

    assert error.value.code == "ARTIFACT_NOT_READY"


def test_iter_content_yields_verified_bytes_in_requested_chunks(tmp_path):
    service, _repository = service_with_local_store(tmp_path)
    record = upload_jpeg(service)

    assert b"".join(service.iter_content(record.artifact_id, chunk_size=17)) == artifact_path(
        tmp_path, record.storage_key
    ).read_bytes()


def test_upload_discards_stage_when_staged_content_cannot_be_read(tmp_path):
    class ReadFailingStore(LocalArtifactStore):
        def open_staged(self, staged):
            raise ArtifactStorageUnavailableError("staged read failed")

    service = ArtifactService(InMemoryArtifactRepository(), ReadFailingStore(tmp_path / "artifacts"))

    with pytest.raises(ArtifactStorageUnavailableError, match="staged read failed"):
        service.upload(
            BytesIO(image_bytes("JPEG")),
            original_filename="bridge.jpg",
            claimed_content_type="image/jpeg",
        )

    assert list((tmp_path / "artifacts" / ".staging").glob("*")) == []


def test_upload_discards_stage_when_finalization_fails_before_move(tmp_path):
    class FinalizeFailingStore(LocalArtifactStore):
        def finalize(self, staged, artifact_id, extension):
            raise ArtifactStorageUnavailableError("finalization failed")

    service = ArtifactService(
        InMemoryArtifactRepository(), FinalizeFailingStore(tmp_path / "artifacts")
    )

    with pytest.raises(ArtifactStorageUnavailableError, match="finalization failed"):
        service.upload(
            BytesIO(image_bytes("JPEG")),
            original_filename="bridge.jpg",
            claimed_content_type="image/jpeg",
        )

    assert list((tmp_path / "artifacts" / ".staging").glob("*")) == []


def _animated_png_bytes() -> bytes:
    stream = BytesIO()
    first = Image.new("RGB", (16, 16), color="red")
    second = Image.new("RGB", (16, 16), color="blue")
    first.save(
        stream,
        format="PNG",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )
    return stream.getvalue()
