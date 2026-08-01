-- Persist immutable metadata for verified JPEG and PNG Artifacts.

CREATE TABLE IF NOT EXISTS inspection_artifacts (
    artifact_id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    width_px INTEGER NOT NULL,
    height_px INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_inspection_artifacts_storage_key UNIQUE (storage_key),
    CONSTRAINT ck_inspection_artifacts_original_filename_nonblank CHECK (
        btrim(original_filename) <> ''
    ),
    CONSTRAINT ck_inspection_artifacts_storage_key_nonblank CHECK (
        btrim(storage_key) <> ''
    ),
    CONSTRAINT ck_inspection_artifacts_sha256 CHECK (
        sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_inspection_artifacts_size_bytes CHECK (
        size_bytes > 0 AND size_bytes <= 20971520
    ),
    CONSTRAINT ck_inspection_artifacts_mime_type CHECK (
        mime_type IN ('image/jpeg', 'image/png')
    ),
    CONSTRAINT ck_inspection_artifacts_width_px CHECK (width_px > 0),
    CONSTRAINT ck_inspection_artifacts_height_px CHECK (height_px > 0),
    CONSTRAINT ck_inspection_artifacts_status CHECK (status = 'ready')
);

CREATE INDEX IF NOT EXISTS ix_inspection_artifacts_created_at
    ON inspection_artifacts (created_at DESC, artifact_id DESC);
