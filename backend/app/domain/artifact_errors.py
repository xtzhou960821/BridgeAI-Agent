"""Stable errors for Artifact storage and ingestion use cases."""


class ArtifactError(RuntimeError):
    code = "ARTIFACT_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ArtifactTooLargeError(ArtifactError):
    code = "ARTIFACT_TOO_LARGE"


class ArtifactStorageUnavailableError(ArtifactError):
    code = "ARTIFACT_STORAGE_UNAVAILABLE"


class ArtifactContentMissingError(ArtifactError):
    code = "ARTIFACT_CONTENT_MISSING"


class ArtifactIntegrityMismatchError(ArtifactError):
    code = "ARTIFACT_INTEGRITY_MISMATCH"


class ArtifactNotFoundError(ArtifactError):
    code = "ARTIFACT_NOT_FOUND"


class ArtifactNotReadyError(ArtifactError):
    code = "ARTIFACT_NOT_READY"


class UnsupportedArtifactTypeError(ArtifactError):
    code = "UNSUPPORTED_ARTIFACT_TYPE"


class InvalidImageArtifactError(ArtifactError):
    code = "INVALID_IMAGE_ARTIFACT"
