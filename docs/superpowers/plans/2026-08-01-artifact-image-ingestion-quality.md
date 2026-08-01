# Artifact Image Ingestion and Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace string-only Artifact IDs and the constant image-quality result with a persisted single-image upload, real integrity verification, explainable technical quality metrics, and a usable Vue preview/result flow.

**Architecture:** PostgreSQL owns immutable Artifact metadata while an `ArtifactStore` interface owns bytes; the first adapter stores files under a configured local root. FastAPI coordinates multipart upload through an Artifact application service, and LangGraph receives only safe Artifact summaries while a versioned Tool analyzes the real image through injected interfaces.

**Tech Stack:** Python 3.12, FastAPI, Pillow, python-multipart, PostgreSQL/psycopg 3, LangGraph with PostgreSQL Checkpointer, Vue 3, TypeScript, Vitest, pytest.

## Global Constraints

- Use `/Users/zhouxiantong/BridgeAI-Agent/.venv/bin/python`; do not use the system Python.
- New tasks contain exactly one Artifact ID produced by `POST /api/v1/artifacts`.
- Accept decoded JPEG and PNG only; reject uploads larger than 20 MiB.
- Store local bytes under `BRIDGEAI_ARTIFACT_STORAGE_ROOT`, defaulting to `var/artifacts/`, and never derive a path from the original filename.
- Persist only relative storage keys; never return or checkpoint an absolute path, file handle, storage client, credential, or binary image.
- Resolution fails below a 720 px short side or below 1,000,000 total pixels.
- Exposure mean fails below 20 or above 235 and warns below 40 or above 215.
- Dark pixels are grayscale values at or below 10; bright pixels are values at or above 245. Either clip ratio fails at 0.80 and warns at 0.50.
- Sharpness is the RMS difference between grayscale content and a radius-1 Gaussian-blurred copy; it fails below 2 and warns below 5.
- Overall quality precedence is `fail`, then `warn`, then `pass`.
- `ToolResult.ok=false` means execution failure. `ToolResult.ok=true` with `quality_status=fail` is a completed negative finding.
- Existing legacy task/history rows remain readable; a new compatibility request must reference one real ready Artifact.
- PostgreSQL tests may mutate only a database whose name is exactly `bridgeai_agent_test`.
- Automated tests use fake/stub model gateways; a real oMLX run is a separate live acceptance check gated by `components.model_gateway=configured`.
- Do not add MinIO, batch images, video, delete/replace, thumbnails, disease detection, image enhancement, async workers, authentication, or an Artifact library in this plan.

---

## File Map

### New backend files

- `backend/app/domain/artifact_errors.py`: stable Artifact exception hierarchy and codes.
- `backend/app/domain/artifacts.py`: `ArtifactRecord` and `ArtifactRepository` protocol.
- `backend/app/storage/__init__.py`: storage package marker.
- `backend/app/storage/artifacts.py`: `ArtifactStore`, `StagedArtifact`, and `LocalArtifactStore`.
- `backend/app/repositories/postgres/artifacts.py`: PostgreSQL Artifact metadata repository.
- `backend/app/repositories/postgres/migrations/0005_artifacts.sql`: Artifact metadata table and constraints.
- `backend/app/services/artifacts.py`: upload, lookup, integrity verification, controlled streaming, and environment assembly.
- `backend/app/services/image_quality.py`: deterministic analyzer, thresholds, result schema, and Chinese reasons.
- `backend/app/api/v1/artifacts.py`: multipart upload, metadata, and controlled content routes.

### New backend tests

- `tests/backend/artifact_test_support.py`: generated JPEG/PNG byte fixtures and Artifact record factory.
- `tests/backend/test_local_artifact_store.py`: filesystem safety and atomic storage behavior.
- `tests/backend/test_artifact_service.py`: upload validation, compensation, lookup, and integrity checks.
- `tests/backend/test_postgres_artifact_repository.py`: guarded PostgreSQL create/read behavior.
- `tests/backend/test_artifacts_api.py`: multipart, metadata/content, headers, and stable errors.
- `tests/backend/test_image_quality.py`: metric boundaries and overall status.

### New frontend files

- `frontend/src/components/ArtifactUploadField.vue`: single-file selection, busy/error state, and ready preview.
- `frontend/src/components/ArtifactUploadField.test.ts`: upload interaction and accessible state tests.

### Existing files modified by the plan

- `pyproject.toml`: Pillow and python-multipart backend dependencies.
- `.gitignore`: local Artifact bytes.
- `.env.example`: local Artifact storage root.
- `tools/sdk.py`, `tests/tools/test_tool_sdk.py`: safe handler-failure conversion to `ToolResult`.
- `agent/langgraph_state.py`, `agent/langgraph_workflow.py`, `agent/runner.py`, `agent/workflow.py`: real data-check routing and persisted error code.
- `backend/app/repositories/postgres/connection.py`: Artifact table readiness probe.
- `backend/app/services/task_runs.py`: real Artifact verifier and quality Tool registration.
- `backend/app/services/tasks.py`: one-ready-Artifact task validation and shared service assembly.
- `backend/app/api/v1/tasks.py`: single-Artifact request validation and Artifact error mapping.
- `backend/app/main.py`: Artifact router registration and optional-import test isolation.
- `tests/backend/postgres_test_support.py`: guarded cleanup includes the Artifact table.
- Existing backend/Agent tests: inject Artifact lookup/verifier dependencies and assert new Workflow semantics.
- `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/api.test.ts`: Artifact and quality types plus API helpers.
- `frontend/src/components/TaskCreateForm.vue` and test: remove manual IDs and require a ready upload.
- `frontend/src/components/TaskRunDetail.vue` and test: preview, quality card, and legacy fallback.
- `frontend/src/App.vue` and test: coordinate immediate upload, selected Artifact loading, and retry state.
- `README.md`, `docs/development/v0.2-local-runbook.md`, `examples/v0_2_sample_task.json`: truthful setup and end-to-end usage.

---

### Task 1: Artifact Errors and Safe Local Storage

**Files:**
- Create: `backend/app/domain/artifact_errors.py`
- Create: `backend/app/storage/__init__.py`
- Create: `backend/app/storage/artifacts.py`
- Create: `tests/backend/test_local_artifact_store.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Modify: `.env.example`
- Modify: `tests/project/test_packaging_config.py`

**Interfaces:**
- Consumes: binary upload streams implementing `read(size: int) -> bytes`.
- Produces: `StagedArtifact`, `ArtifactStore`, `LocalArtifactStore.stage`, `open_staged`, `finalize`, `open`, and `delete`.

- [ ] **Step 1: Write failing local-storage and dependency tests**

Add tests that stage a stream, assert the SHA-256 and byte count, finalize it to a generated relative key, reopen identical bytes, reject a 20 MiB + 1 byte stream, reject `../escape`, refuse symlinks, and delete only a key under the root.

```python
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
```

Extend `tests/project/test_packaging_config.py` to assert `pillow` and `python-multipart` are declared in the backend extra.

- [ ] **Step 2: Run the focused tests and verify the missing-module failure**

Run:

```bash
./.venv/bin/python -m pytest tests/backend/test_local_artifact_store.py tests/project/test_packaging_config.py -q
```

Expected: FAIL because `backend.app.storage.artifacts` and the new dependencies do not exist.

- [ ] **Step 3: Add the errors, dependencies, configuration, and minimal store**

Use this stable error base and codes:

```python
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


class UnsupportedArtifactTypeError(ArtifactError):
    code = "UNSUPPORTED_ARTIFACT_TYPE"


class InvalidImageArtifactError(ArtifactError):
    code = "INVALID_IMAGE_ARTIFACT"
```

Define the storage contract exactly once:

```python
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
```

`LocalArtifactStore.stage` must read 1 MiB chunks, update `hashlib.sha256`, stop as soon as the limit is exceeded, close the file, and unlink the stage on every handled failure. `finalize` must accept only `.jpg` and `.png`, derive the two-character prefix from the part after `art_`, create the parent, and use `os.replace`. `_resolve` must reject absolute keys, escaped parents, and symlinks before opening.

Add these backend dependencies:

```toml
"pillow>=11",
"python-multipart>=0.0.9",
```

Add `var/artifacts/` to `.gitignore` and this line to `.env.example`:

```text
BRIDGEAI_ARTIFACT_STORAGE_ROOT=var/artifacts
```

- [ ] **Step 4: Run the focused tests and dependency check**

Run:

```bash
./.venv/bin/python -m pip install -e ".[backend,dev]"
./.venv/bin/python -m pytest tests/backend/test_local_artifact_store.py tests/project/test_packaging_config.py -q
./.venv/bin/python -m pip check
```

Expected: all focused tests pass and `pip check` reports no broken requirements.

- [ ] **Step 5: Commit the storage primitive**

```bash
git add pyproject.toml .gitignore .env.example backend/app/domain/artifact_errors.py backend/app/storage tests/backend/test_local_artifact_store.py tests/project/test_packaging_config.py
git commit -m "feat: add safe local artifact storage"
```

---

### Task 2: Artifact Metadata Migration and Repository

**Files:**
- Create: `backend/app/domain/artifacts.py`
- Create: `backend/app/repositories/postgres/artifacts.py`
- Create: `backend/app/repositories/postgres/migrations/0005_artifacts.sql`
- Create: `tests/backend/test_postgres_artifact_repository.py`
- Modify: `tests/backend/test_postgres_migrations.py`
- Modify: `tests/backend/postgres_test_support.py`
- Modify: `backend/app/repositories/postgres/connection.py`

**Interfaces:**
- Consumes: `ArtifactRecord` values produced by the upload service.
- Produces: `ArtifactRepository.create_artifact(record)` and `get_artifact(artifact_id)` plus safe payload methods.

- [ ] **Step 1: Write failing migration and repository tests**

Update the ordered migration expectation to include `0005_artifacts.sql`, assert all approved columns and constraints, and add guarded repository coverage:

```python
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
```

Extend guarded cleanup to drop `inspection_artifacts` and extend `probe_database` tests so readiness requires the new business table after the migration lands.

- [ ] **Step 2: Run the PostgreSQL tests and verify the expected failure**

Run:

```bash
BRIDGEAI_TEST_DATABASE_URL="$BRIDGEAI_TEST_DATABASE_URL" ./.venv/bin/python -m pytest tests/backend/test_postgres_migrations.py tests/backend/test_postgres_artifact_repository.py tests/backend/test_health.py -q
```

Expected: FAIL because migration 0005 and `PostgresArtifactRepository` are absent.

- [ ] **Step 3: Implement the domain record, SQL migration, and repository**

Use these domain interfaces:

```python
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
```

Add `ArtifactNotFoundError` with code `ARTIFACT_NOT_FOUND` and `ArtifactNotReadyError` with code `ARTIFACT_NOT_READY` to the error hierarchy.

Migration 0005 must create `inspection_artifacts` with the exact columns and checks from the approved spec, including a unique `storage_key`, lowercase 64-character SHA-256 check, 20 MiB limit, JPEG/PNG MIME check, positive dimensions, `status='ready'`, and a descending `created_at, artifact_id` index. Use `CREATE TABLE IF NOT EXISTS` and named constraints so repeated migration execution stays safe.

`PostgresArtifactRepository` must catch `psycopg.Error` and raise the existing `DatabaseUnavailableError("PostgreSQL artifact store is unavailable")`; missing rows raise `ArtifactNotFoundError` without being translated to database failure.

- [ ] **Step 4: Run the migration, repository, and health tests**

Run:

```bash
BRIDGEAI_TEST_DATABASE_URL="$BRIDGEAI_TEST_DATABASE_URL" ./.venv/bin/python -m pytest tests/backend/test_postgres_migrations.py tests/backend/test_postgres_artifact_repository.py tests/backend/test_health.py -q
```

Expected: all tests pass, second migration application returns an empty list, and database health is ready only when `inspection_tasks`, `inspection_task_runs`, and `inspection_artifacts` exist.

- [ ] **Step 5: Commit metadata persistence**

```bash
git add backend/app/domain/artifact_errors.py backend/app/domain/artifacts.py backend/app/repositories/postgres/artifacts.py backend/app/repositories/postgres/migrations/0005_artifacts.sql backend/app/repositories/postgres/connection.py tests/backend/test_postgres_artifact_repository.py tests/backend/test_postgres_migrations.py tests/backend/test_health.py tests/backend/postgres_test_support.py
git commit -m "feat: persist artifact metadata"
```

---

### Task 3: Artifact Upload and Integrity Service

**Files:**
- Create: `backend/app/services/artifacts.py`
- Create: `tests/backend/artifact_test_support.py`
- Create: `tests/backend/test_artifact_service.py`

**Interfaces:**
- Consumes: `ArtifactRepository`, `ArtifactStore`, upload `BinaryIO`, original filename, and client content-type hint.
- Produces: `ArtifactService.upload`, `get`, `require_ready`, `verify`, `open_verified`, and `iter_content`; `build_artifact_service_from_environment`.

- [ ] **Step 1: Write failing service tests with real generated images**

Create deterministic fixture helpers:

```python
def image_bytes(
    image_format: str = "JPEG",
    *,
    size: tuple[int, int] = (1280, 800),
    color: int = 128,
) -> bytes:
    stream = BytesIO()
    Image.new("L", size, color=color).save(stream, format=image_format)
    return stream.getvalue()
```

Cover a valid JPEG mislabeled by the client, a PNG, corrupt bytes, unsupported GIF, oversized input, database failure cleanup, safe metadata lookup, post-upload byte tampering, missing content, and `ready` enforcement.

```python
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


def test_verify_rejects_modified_content(tmp_path):
    service, _repository = service_with_local_store(tmp_path)
    record = upload_jpeg(service)
    artifact_path(tmp_path, record.storage_key).write_bytes(b"changed")

    with pytest.raises(ArtifactIntegrityMismatchError) as error:
        service.verify(record.artifact_id)
    assert error.value.code == "ARTIFACT_INTEGRITY_MISMATCH"
```

- [ ] **Step 2: Run the service tests and verify they fail because the service is absent**

Run:

```bash
./.venv/bin/python -m pytest tests/backend/test_artifact_service.py -q
```

Expected: FAIL importing `backend.app.services.artifacts`.

- [ ] **Step 3: Implement upload, compensation, and integrity verification**

Use these exact public signatures:

```python
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
    ) -> ArtifactRecord: ...

    def get(self, artifact_id: str) -> ArtifactRecord: ...
    def require_ready(self, artifact_id: str) -> ArtifactRecord: ...
    def verify(self, artifact_id: str) -> ArtifactRecord: ...

    @contextmanager
    def open_verified(self, artifact_id: str) -> Iterator[tuple[ArtifactRecord, BinaryIO]]: ...

    def iter_content(self, artifact_id: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]: ...
```

In `upload`, stage first, verify with `Image.verify()`, reopen and call `load()`, map only `JPEG -> (image/jpeg, .jpg)` and `PNG -> (image/png, .png)`, generate `art_{uuid.uuid4().hex}`, finalize, build the immutable record, and insert it. Normalize the display filename with `Path(original_filename).name.strip()` and limit it to 255 characters. Treat the client content type as an audit hint only; never use it to decide the decoded format.

Set `created_at=datetime.now(UTC)` once when building the record and pass that
same timestamp through repository insertion and the response.

If image validation fails, discard the stage and raise `InvalidImageArtifactError` or `UnsupportedArtifactTypeError`. If repository insertion fails after finalization, call `delete(storage_key)` and re-raise the database error. `verify` must re-read size, SHA-256, and decoded format/dimensions and compare them with the record.

Build from environment with:

```python
def build_artifact_service_from_environment(
    environ: Mapping[str, str] | None = None,
) -> ArtifactService:
    source = os.environ if environ is None else environ
    database_url = get_database_url(source)
    if not database_url:
        raise DatabaseUnavailableError("PostgreSQL artifact store is unavailable")
    root = Path(source.get("BRIDGEAI_ARTIFACT_STORAGE_ROOT", "var/artifacts"))
    return ArtifactService(PostgresArtifactRepository(database_url), LocalArtifactStore(root))
```

- [ ] **Step 4: Run service and local-store tests**

Run:

```bash
./.venv/bin/python -m pytest tests/backend/test_local_artifact_store.py tests/backend/test_artifact_service.py -q
```

Expected: all tests pass; generated fixtures remain inside pytest temporary directories.

- [ ] **Step 5: Commit the Artifact service**

```bash
git add backend/app/domain/artifact_errors.py backend/app/services/artifacts.py tests/backend/artifact_test_support.py tests/backend/test_artifact_service.py
git commit -m "feat: ingest and verify image artifacts"
```

---

### Task 4: Artifact FastAPI Routes

**Files:**
- Create: `backend/app/api/v1/artifacts.py`
- Create: `tests/backend/test_artifacts_api.py`
- Modify: `backend/app/main.py`
- Modify: `tests/backend/test_main_app.py`

**Interfaces:**
- Consumes: `build_artifact_service_from_environment` and `ArtifactService` public methods.
- Produces: `POST /api/v1/artifacts`, `GET /api/v1/artifacts/{artifact_id}`, and `GET /api/v1/artifacts/{artifact_id}/content`.

- [ ] **Step 1: Write failing route and header tests**

Use a fake service for routing behavior and the real service for one multipart integration test.

```python
def test_upload_metadata_and_content_routes(monkeypatch):
    service = FakeArtifactService(artifact_record())
    monkeypatch.setattr(artifacts, "build_artifact_service_from_environment", lambda: service)
    client = TestClient(create_app())

    uploaded = client.post(
        "/api/v1/artifacts",
        files={"file": ("bridge.jpg", image_bytes("JPEG"), "image/jpeg")},
    )
    metadata = client.get("/api/v1/artifacts/art_ab12cd34")
    content = client.get("/api/v1/artifacts/art_ab12cd34/content")

    assert uploaded.status_code == 201
    assert uploaded.json()["content_url"] == "/api/v1/artifacts/art_ab12cd34/content"
    assert "storage_key" not in uploaded.json()
    assert metadata.status_code == 200
    assert content.headers["etag"] == f'"sha256:{service.record.sha256}"'
    assert content.headers["cache-control"].startswith("private")
```

Parameterize exact mappings for HTTP 415, 413, 422, 503, and 404. Update the optional-FastAPI isolation test to remove and restore `backend.app.api.v1.artifacts` alongside the existing API modules.

- [ ] **Step 2: Run API tests and verify the missing-router failure**

Run:

```bash
./.venv/bin/python -m pytest tests/backend/test_artifacts_api.py tests/backend/test_main_app.py -q
```

Expected: FAIL because the Artifact router is absent.

- [ ] **Step 3: Implement the router and stable error translation**

The successful upload route must call the service with `UploadFile.file`, add `content_url` to the safe payload, and return 201. The content route must call `verify` before returning a `StreamingResponse` over `iter_content` with these headers:

```python
headers = {
    "ETag": f'"sha256:{record.sha256}"',
    "Cache-Control": "private, max-age=3600",
    "Content-Disposition": "inline",
    "X-Content-Type-Options": "nosniff",
}
```

Map errors exactly:

```python
ERROR_RESPONSES = {
    UnsupportedArtifactTypeError: (415, "UNSUPPORTED_ARTIFACT_TYPE", "仅支持 JPEG、PNG。"),
    ArtifactTooLargeError: (413, "ARTIFACT_TOO_LARGE", "图片不得超过 20 MiB。"),
    InvalidImageArtifactError: (422, "INVALID_IMAGE_ARTIFACT", "文件不是有效图片或已损坏。"),
    ArtifactNotFoundError: (404, "ARTIFACT_NOT_FOUND", "未找到指定 Artifact。"),
    ArtifactStorageUnavailableError: (503, "ARTIFACT_STORAGE_UNAVAILABLE", "Artifact 存储当前不可用，请检查存储目录。"),
    DatabaseUnavailableError: (503, "DATABASE_UNAVAILABLE", "PostgreSQL Artifact 元数据存储当前不可用。"),
}
```

Register `artifacts_router` under `/api/v1` in `create_app` without changing existing CORS behavior.

- [ ] **Step 4: Run Artifact API, app-isolation, and CORS tests**

Run:

```bash
./.venv/bin/python -m pytest tests/backend/test_artifacts_api.py tests/backend/test_main_app.py tests/backend/test_tasks_api.py::test_api_allows_vite_frontend_origin_preflight -q
```

Expected: all tests pass and no response contains `storage_key` or an absolute path.

- [ ] **Step 5: Commit the Artifact API**

```bash
git add backend/app/api/v1/artifacts.py backend/app/main.py tests/backend/test_artifacts_api.py tests/backend/test_main_app.py
git commit -m "feat: expose artifact upload API"
```

---

### Task 5: Require One Ready Artifact for New Tasks

**Files:**
- Modify: `backend/app/services/tasks.py`
- Modify: `backend/app/api/v1/tasks.py`
- Modify: `tests/backend/test_task_service.py`
- Modify: `tests/backend/test_tasks_api.py`

**Interfaces:**
- Consumes: `ArtifactService.require_ready(artifact_id) -> ArtifactRecord`.
- Produces: `TaskService(..., require_ready_artifact=callable)` and single-Artifact task/compatibility behavior.

- [ ] **Step 1: Write failing service and request-validation tests**

Add service tests proving new task creation calls the lookup once, zero/multiple IDs are rejected, a missing Artifact is not persisted, a new compatibility task is validated, and an already persisted legacy task bypasses create-time validation so its run can produce a persisted Workflow failure.

```python
def test_service_requires_one_ready_artifact_before_create(repository):
    calls = []
    service = TaskService(
        repository,
        run_inspection=_successful_run,
        require_ready_artifact=lambda artifact_id: calls.append(artifact_id) or artifact_record(),
    )

    task = service.create_task(_task_command())

    assert calls == ["art_001"]
    assert task.artifact_ids == ["art_001"]


def test_service_does_not_create_task_for_missing_artifact(repository):
    def missing(_artifact_id):
        raise ArtifactNotFoundError("missing")

    service = TaskService(repository, _successful_run, require_ready_artifact=missing)
    with pytest.raises(ArtifactNotFoundError):
        service.create_task(_task_command())
    assert repository.list_tasks() == []
```

Add API tests that both `TaskCreateRequest` and `LegacyTaskRunRequest` reject arrays of length 0 or 2 with HTTP 422 and translate `ArtifactNotFoundError`/`ArtifactNotReadyError` to HTTP 422 `ARTIFACT_NOT_READY`.

- [ ] **Step 2: Run focused task tests and verify the constructor/validation failures**

Run:

```bash
BRIDGEAI_TEST_DATABASE_URL="$BRIDGEAI_TEST_DATABASE_URL" ./.venv/bin/python -m pytest tests/backend/test_task_service.py tests/backend/test_tasks_api.py -q
```

Expected: FAIL until `TaskService` accepts the Artifact lookup and request models enforce exactly one ID.

- [ ] **Step 3: Implement the validation and shared environment assembly**

Change the service constructor to:

```python
RequireReadyArtifact = Callable[[str], ArtifactRecord]


def __init__(
    self,
    repository: TaskRepository,
    run_inspection: RunInspection,
    require_ready_artifact: RequireReadyArtifact,
) -> None:
    self._repository = repository
    self._run_inspection = run_inspection
    self._require_ready_artifact = require_ready_artifact
```

Use one private method for both create paths:

```python
def _validate_new_task_artifact(self, command: TaskCreate) -> None:
    if len(command.artifact_ids) != 1:
        raise ArtifactNotReadyError("Exactly one ready Artifact is required")
    self._require_ready_artifact(command.artifact_ids[0])
```

Call it before `create_task` persistence. In `execute_legacy_task`, call it only when `get_task` raises `TaskNotFoundError`, then create the compatibility task with its supplied ID. Existing persisted tasks still proceed directly to `execute_task`.

Build one `ArtifactService` in `build_task_service_from_environment`, pass `artifact_service.require_ready`, and bind the same service into `run_inspection_task` with `functools.partial`.

Set both Pydantic request fields to `Field(min_length=1, max_length=1)` and map missing/not-ready Artifact errors to:

```json
{
  "code": "ARTIFACT_NOT_READY",
  "message": "请先上传一张有效且已就绪的图片。"
}
```

- [ ] **Step 4: Run task service and task API tests**

Run:

```bash
BRIDGEAI_TEST_DATABASE_URL="$BRIDGEAI_TEST_DATABASE_URL" ./.venv/bin/python -m pytest tests/backend/test_task_service.py tests/backend/test_tasks_api.py -q
```

Expected: all tests pass, including the compatibility distinction between new and persisted legacy tasks.

- [ ] **Step 5: Commit task binding validation**

```bash
git add backend/app/services/tasks.py backend/app/api/v1/tasks.py tests/backend/test_task_service.py tests/backend/test_tasks_api.py
git commit -m "feat: bind tasks to one ready artifact"
```

---

### Task 6: Deterministic Quality Analyzer and Tool Failure Contract

**Files:**
- Create: `backend/app/services/image_quality.py`
- Create: `tests/backend/test_image_quality.py`
- Modify: `tools/sdk.py`
- Modify: `tests/tools/test_tool_sdk.py`

**Interfaces:**
- Consumes: a verified image binary stream and Artifact ID.
- Produces: `QualityThresholds`, `ImageQualityResult`, `ImageQualityAnalyzer.analyze`, and `ToolHandlerError` conversion.

- [ ] **Step 1: Write failing metric, boundary, and Tool handler tests**

Generate sharp checkerboard, Gaussian-blurred, low-resolution, dark, bright, and neutral images. Assert per-check states, exact threshold inclusion, overall precedence, finite numbers, analyzer version, and Chinese reasons.

```python
def test_analyzer_returns_explainable_metrics_and_thresholds():
    result = ImageQualityAnalyzer().analyze(
        BytesIO(checkerboard_jpeg(size=(1280, 800))),
        artifact_id="art_quality",
    )
    payload = result.as_payload()

    assert payload["artifact_id"] == "art_quality"
    assert payload["analyzer_version"] == "0.1.0"
    assert payload["checks"]["resolution"] == "pass"
    assert payload["thresholds"]["resolution"]["min_short_side_px"] == 720
    assert payload["quality_status"] in {"pass", "warn"}
    assert all(math.isfinite(value) for value in payload["metrics"].values())


def test_tool_executor_converts_declared_handler_error():
    registry = ToolRegistry()
    registry.register(manifest(), lambda _payload: _raise_tool_handler_error())

    result = ToolExecutor(registry).execute("image_quality_check", {"artifact_id": "art_1"})

    assert result.ok is False
    assert result.error_code == "ARTIFACT_CONTENT_MISSING"
    assert result.error_message == "图片文件缺失"
```

- [ ] **Step 2: Run quality and Tool SDK tests and verify missing APIs**

Run:

```bash
./.venv/bin/python -m pytest tests/backend/test_image_quality.py tests/tools/test_tool_sdk.py -q
```

Expected: FAIL because the analyzer and `ToolHandlerError` do not exist.

- [ ] **Step 3: Implement exact metrics and declared Tool failures**

Define immutable defaults:

```python
@dataclass(frozen=True)
class QualityThresholds:
    min_short_side_px: int = 720
    min_total_pixels: int = 1_000_000
    exposure_fail_low: float = 20.0
    exposure_warn_low: float = 40.0
    exposure_warn_high: float = 215.0
    exposure_fail_high: float = 235.0
    dark_pixel_max: int = 10
    bright_pixel_min: int = 245
    clip_warn_ratio: float = 0.50
    clip_fail_ratio: float = 0.80
    sharpness_fail_below: float = 2.0
    sharpness_warn_below: float = 5.0
```

Return one immutable result shape:

```python
@dataclass(frozen=True)
class ImageQualityResult:
    artifact_id: str
    quality_status: str
    analyzer_version: str
    metrics: dict[str, float]
    thresholds: dict[str, dict[str, float | int]]
    checks: dict[str, str]
    reasons: tuple[str, ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "quality_status": self.quality_status,
            "analyzer_version": self.analyzer_version,
            "metrics": self.metrics,
            "thresholds": self.thresholds,
            "checks": self.checks,
            "reasons": list(self.reasons),
        }
```

Calculate metrics with Pillow only:

```python
gray = image.convert("L")
histogram = gray.histogram()
pixel_count = gray.width * gray.height
mean_luminance = float(ImageStat.Stat(gray).mean[0])
dark_clip_ratio = sum(histogram[: thresholds.dark_pixel_max + 1]) / pixel_count
bright_clip_ratio = sum(histogram[thresholds.bright_pixel_min :]) / pixel_count
blurred = gray.filter(ImageFilter.GaussianBlur(radius=1))
sharpness_rms = float(ImageStat.Stat(ImageChops.difference(gray, blurred)).rms[0])
```

Use strict comparisons from Global Constraints, preserve exact boundary values, and serialize a `thresholds` object, per-check states, metrics, overall state, and ordered Chinese reasons. Do not round values before classification; round only serialized display metrics to four decimal places.

Add:

```python
class ToolHandlerError(RuntimeError):
    def __init__(self, error_code: str, error_message: str) -> None:
        super().__init__(error_message)
        self.error_code = error_code
        self.error_message = error_message
```

Catch only `ToolHandlerError` inside `ToolExecutor.execute` and return `ToolResult(ok=False, output={}, error_code=..., error_message=...)`. Unexpected exceptions still propagate to the task service.

- [ ] **Step 4: Run quality and Tool SDK tests**

Run:

```bash
./.venv/bin/python -m pytest tests/backend/test_image_quality.py tests/tools/test_tool_sdk.py -q
```

Expected: all metric, boundary, and handler-failure tests pass.

- [ ] **Step 5: Commit the analyzer and Tool contract**

```bash
git add backend/app/services/image_quality.py tests/backend/test_image_quality.py tools/sdk.py tests/tools/test_tool_sdk.py
git commit -m "feat: analyze technical image quality"
```

---

### Task 7: Real Artifact Verification in LangGraph

**Files:**
- Modify: `agent/langgraph_state.py`
- Modify: `agent/langgraph_workflow.py`
- Modify: `agent/runner.py`
- Modify: `agent/workflow.py`
- Modify: `backend/app/services/task_runs.py`
- Modify: `tests/agent/test_langgraph_workflow.py`
- Modify: `tests/agent/test_agent_runner.py`
- Modify: `tests/agent/test_workflow_state.py`
- Modify: `tests/backend/test_task_runs.py`
- Modify: `tests/backend/test_langgraph_checkpointer.py`

**Interfaces:**
- Consumes: `ArtifactService.verify`, `open_verified`, `ImageQualityAnalyzer`, and Tool SDK.
- Produces: `ArtifactVerifier = Callable[[str], dict[str, object]]`, real `data_check`, persisted `error_code`, and a real `image_quality_check` Tool result.

- [ ] **Step 1: Write failing graph routing and real-result tests**

Update every graph/runner construction to inject a verifier. Add coverage for successful safe metadata, missing/tampered data routing before Tool execution, Tool infrastructure failure, and a completed `quality_status=fail` result.

```python
def test_graph_routes_failed_artifact_verification_without_running_tool():
    calls = []
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=lambda _artifact_id: {
            "ok": False,
            "error_code": "ARTIFACT_NOT_FOUND",
            "error_message": "Artifact does not exist",
        },
        tool_executor=ToolExecutor(_registry_with_handler(lambda payload: calls.append(payload))),
        checkpointer=InMemorySaver(),
    )

    result = graph.invoke(_initial_state("run_missing"), config=_config("run_missing"))

    assert result["status"] == "failed"
    assert result["error_step"] == "data_check"
    assert result["error_code"] == "ARTIFACT_NOT_FOUND"
    assert calls == []


def test_graph_completes_when_analysis_finds_low_quality():
    graph = graph_with_quality_output({"quality_status": "fail", "artifact_id": "art_001"})
    result = graph.invoke(_initial_state("run_low_quality"), config=_config("run_low_quality"))

    assert result["status"] == "completed"
    assert result["tool_results"][0]["ok"] is True
    assert result["tool_results"][0]["output"]["quality_status"] == "fail"
```

Add a task-run service test using `ArtifactService` with a temporary local store and a generated image; assert the serialized Tool output contains actual metrics and thresholds instead of the old constant payload.

- [ ] **Step 2: Run Agent and task-run tests and verify the missing verifier/error fields**

Run:

```bash
./.venv/bin/python -m pytest tests/agent/test_langgraph_workflow.py tests/agent/test_agent_runner.py tests/agent/test_workflow_state.py tests/backend/test_task_runs.py tests/backend/test_langgraph_checkpointer.py -q
```

Expected: FAIL until graph state, runner construction, and task-run registration accept the real Artifact dependencies.

- [ ] **Step 3: Add serializer-safe data-check state and routing**

Add these fields to `BridgeInspectionState` and initialize them safely:

```python
data_check_result: dict[str, object]
error_code: str | None
```

Change the graph signature to:

```python
ArtifactVerifier = Callable[[str], dict[str, object]]


def build_bridge_inspection_graph(
    *,
    model_gateway: ModelGateway,
    artifact_verifier: ArtifactVerifier,
    tool_executor: ToolExecutor,
    checkpointer: BaseCheckpointSaver,
):
```

`data_check` must normalize the verifier result before checkpointing, append it to history, and set `error_step`, `error_code`, and `error_message` when `ok` is not true. Add a conditional edge from `data_check` to `image_quality_check` or `failed`. When the Tool result is not okay, set the same three error fields for `image_quality_check`. The `failed` node must use those fields and must not index `tool_results[-1]` for a data-check failure.

Add `error_code` to `WorkflowState`, `AgentRunner` terminal mapping, and `_serialize_workflow`.

- [ ] **Step 4: Register the real verifier and quality Tool**

Replace `_build_demo_registry` and the constant handler with injected functions:

```python
def _verify_artifact(service: ArtifactService, artifact_id: str) -> dict[str, object]:
    try:
        record = service.verify(artifact_id)
    except ArtifactError as exc:
        return {"ok": False, "error_code": exc.code, "error_message": str(exc)}
    return {"ok": True, "artifact": record.as_checkpoint_payload()}


def _image_quality_handler(
    service: ArtifactService,
    analyzer: ImageQualityAnalyzer,
    payload: dict[str, object],
) -> dict[str, object]:
    artifact_id = str(payload["artifact_id"])
    try:
        with service.open_verified(artifact_id) as (_record, stream):
            return analyzer.analyze(stream, artifact_id=artifact_id).as_payload()
    except ArtifactError as exc:
        raise ToolHandlerError(exc.code, str(exc)) from exc
```

`run_inspection_task` accepts an optional injected `artifact_service`; the environment path constructs one only when absent. `_run_with_checkpointer` passes `partial(_verify_artifact, service)` to `AgentRunner` and registers `partial(_image_quality_handler, service, ImageQualityAnalyzer())` as Tool version `0.1.0`.

- [ ] **Step 5: Run the complete Agent and task-run slice**

Run:

```bash
./.venv/bin/python -m pytest tests/agent tests/tools tests/backend/test_task_runs.py tests/backend/test_langgraph_checkpointer.py -q
```

Expected: all tests pass; strict msgpack tests still prove that no binary data, paths, or secrets enter checkpoints.

- [ ] **Step 6: Commit the real Workflow integration**

```bash
git add agent/langgraph_state.py agent/langgraph_workflow.py agent/runner.py agent/workflow.py backend/app/services/task_runs.py tests/agent tests/backend/test_task_runs.py tests/backend/test_langgraph_checkpointer.py
git commit -m "feat: verify real artifacts in langgraph"
```

---

### Task 8: Frontend Upload API and Task Form

**Files:**
- Create: `frontend/src/components/ArtifactUploadField.vue`
- Create: `frontend/src/components/ArtifactUploadField.test.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/api.test.ts`
- Modify: `frontend/src/components/TaskCreateForm.vue`
- Modify: `frontend/src/components/TaskCreateForm.test.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.test.ts`

**Interfaces:**
- Consumes: Artifact API response and one user-selected `File`.
- Produces: `ArtifactRecord`, `uploadArtifact(file)`, `getArtifact(id)`, `artifactContentUrl(id)`, and form `upload`/`create` events.

- [ ] **Step 1: Write failing API and upload-component tests**

Add exact frontend types:

```typescript
export type ArtifactRecord = {
  artifact_id: string
  original_filename: string
  sha256: string
  size_bytes: number
  mime_type: 'image/jpeg' | 'image/png'
  width_px: number
  height_px: number
  status: 'ready'
  content_url: string
  created_at: string
}
```

Test FormData without manually setting `Content-Type`, encoded metadata/content URLs, and structured upload errors.

```typescript
it('uploads one file as multipart form data', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(artifact, 201))
  const file = new File(['jpeg-bytes'], 'bridge.jpg', { type: 'image/jpeg' })

  await uploadArtifact(file)

  const [, init] = fetchMock.mock.calls[0]
  expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/artifacts')
  expect(init?.method).toBe('POST')
  expect(init?.body).toBeInstanceOf(FormData)
  expect(init?.headers).toBeUndefined()
})
```

Component tests must cover click input, drag/drop, busy copy, upload error with `role=alert`, ready preview/metadata, no file input after ready, and submit disabled until an Artifact is ready.

- [ ] **Step 2: Run frontend tests and verify missing types/component behavior**

Run:

```bash
npm test --prefix frontend -- frontend/src/api.test.ts frontend/src/components/ArtifactUploadField.test.ts frontend/src/components/TaskCreateForm.test.ts frontend/src/App.test.ts
```

Expected: FAIL because Artifact helpers and `ArtifactUploadField` do not exist and the form still exposes a manual ID textarea.

- [ ] **Step 3: Implement API helpers and the upload field**

Add:

```typescript
export function uploadArtifact(file: File): Promise<ArtifactRecord> {
  const body = new FormData()
  body.append('file', file)
  return request('/artifacts', { method: 'POST', body })
}

export function getArtifact(artifactId: string): Promise<ArtifactRecord> {
  return request(`/artifacts/${encodeURIComponent(artifactId)}`)
}

export function artifactContentUrl(artifactId: string): string {
  return `${apiBaseUrl}/artifacts/${encodeURIComponent(artifactId)}/content`
}
```

`ArtifactUploadField` props and event are:

```typescript
defineProps<{
  artifact: ArtifactRecord | null
  busy: boolean
  error: string
}>()

const emit = defineEmits<{ select: [file: File] }>()
```

Accept `.jpg,.jpeg,.png,image/jpeg,image/png`, emit only the first selected/dropped file, show `正在校验并保存图片...` while busy, and render preview with `artifactContentUrl`, filename, MiB size, dimensions, MIME, checksum prefix, status, and read-only ID after success. Do not render replace/delete controls after success.

- [ ] **Step 4: Integrate immediate upload into TaskCreateForm and App**

Change the form contract to:

```typescript
const props = defineProps<{
  busy: boolean
  uploading: boolean
  artifact: ArtifactRecord | null
  uploadError: string
}>()

const emit = defineEmits<{
  upload: [file: File]
  create: [input: TaskCreateInput]
}>()
```

Remove the manual Artifact textarea. Validate title, task type, objective, and `props.artifact`; emit `artifact_ids: [props.artifact.artifact_id]`. Disable submit while uploading, creating, or no Artifact is ready.

In `App.vue`, add `pendingArtifact`, `isUploadingArtifact`, and `artifactUploadError`; `handleArtifactUpload(file)` calls `uploadArtifact` immediately. Preserve `pendingArtifact` when task creation fails, and clear it only after task creation succeeds. Mock `uploadArtifact` in `App.test.ts` and assert `createTask` receives the uploaded ID.

- [ ] **Step 5: Run the focused frontend suite and build**

Run:

```bash
npm test --prefix frontend -- frontend/src/api.test.ts frontend/src/components/ArtifactUploadField.test.ts frontend/src/components/TaskCreateForm.test.ts frontend/src/App.test.ts
npm run build --prefix frontend
```

Expected: focused tests and Vue typecheck/Vite production build pass.

- [ ] **Step 6: Commit the upload form**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/api.test.ts frontend/src/components/ArtifactUploadField.vue frontend/src/components/ArtifactUploadField.test.ts frontend/src/components/TaskCreateForm.vue frontend/src/components/TaskCreateForm.test.ts frontend/src/App.vue frontend/src/App.test.ts
git commit -m "feat: upload task artifact from workbench"
```

---

### Task 9: Persisted Artifact Preview and Quality Result UI

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.test.ts`
- Modify: `frontend/src/components/TaskRunDetail.vue`
- Modify: `frontend/src/components/TaskRunDetail.test.ts`

**Interfaces:**
- Consumes: selected task Artifact ID, `getArtifact`, and `image_quality_check` Tool output.
- Produces: selected Artifact loading state, safe legacy fallback, an `ImageQualityOutput` type guard and quality card, and expandable raw Tool audit data.

- [ ] **Step 1: Write failing selected-Artifact and quality-card tests**

Add typed quality structures:

```typescript
export type QualityStatus = 'pass' | 'warn' | 'fail'

export type ImageQualityOutput = {
  artifact_id: string
  quality_status: QualityStatus
  analyzer_version: string
  metrics: Record<string, number>
  thresholds: Record<string, Record<string, number>>
  checks: Record<string, QualityStatus>
  reasons: string[]
}
```

Test pass/warn/fail Chinese badges, metric/threshold/reason display, image preview, raw JSON details, an Artifact metadata 404, and an old run without a quality output.

```typescript
it('renders a failed quality finding without calling the run a system failure', () => {
  const wrapper = mount(TaskRunDetail, {
    props: {
      run: qualityRun('fail'),
      artifact,
      artifactLoading: false,
      artifactError: '',
    },
  })

  expect(wrapper.text()).toContain('质量不合格')
  expect(wrapper.text()).toContain('图像整体偏暗')
  expect(wrapper.text()).toContain('分析器 0.1.0')
  expect(wrapper.text()).not.toContain('任务执行失败')
})
```

- [ ] **Step 2: Run detail/App tests and verify missing props and rendering**

Run:

```bash
npm test --prefix frontend -- frontend/src/components/TaskRunDetail.test.ts frontend/src/App.test.ts
```

Expected: FAIL because App does not load selected Artifact metadata and the detail component only prints raw JSON.

- [ ] **Step 3: Load the selected task Artifact without stale updates**

Add `selectedArtifact`, `isLoadingArtifact`, and `selectedArtifactError` to `App.vue`. On task selection, clear old Artifact state and run `refreshRuns(taskId)` and `refreshArtifact(taskId, artifactId)` in parallel. Before assigning either response, confirm `selectedTaskId.value === taskId`.

Treat a missing legacy Artifact as display state, not a global task-list failure:

```typescript
selectedArtifact.value = null
selectedArtifactError.value = messageOf(error, '历史任务未关联真实图片')
```

Pass all four props to `TaskRunDetail`.

- [ ] **Step 4: Render preview, typed quality checks, and audit details**

Change the detail props to:

```typescript
defineProps<{
  run: TaskRunRecord | null
  artifact: ArtifactRecord | null
  artifactLoading: boolean
  artifactError: string
}>()
```

Use a type guard that requires `artifact_id`, one of the three quality statuses, object metrics/thresholds/checks, and a string reasons array. Find only the `image_quality_check` Tool whose `ok === true`. Render:

- controlled Artifact preview and safe metadata;
- `质量通过`, `需要注意`, or `质量不合格`;
- resolution, exposure, dark clipping, bright clipping, and sharpness rows;
- actual metric values and the serialized thresholds used;
- analyzer version and reasons;
- `<details><summary>审计详情</summary>` containing raw Tool JSON.

If metadata is absent or failed to load, display `历史任务未关联真实图片`. If the run has no typed quality result, keep the existing generic Tool snapshot so legacy history remains readable.

- [ ] **Step 5: Run frontend tests and production build**

Run:

```bash
npm test --prefix frontend
npm run build --prefix frontend
```

Expected: all frontend tests pass and the production build completes without TypeScript errors.

- [ ] **Step 6: Commit the result experience**

```bash
git add frontend/src/types.ts frontend/src/App.vue frontend/src/App.test.ts frontend/src/components/TaskRunDetail.vue frontend/src/components/TaskRunDetail.test.ts
git commit -m "feat: show artifact quality evidence"
```

---

### Task 10: Documentation, Full Regression, and Live Acceptance

**Files:**
- Create: `tests/project/test_artifact_docs.py`
- Modify: `README.md`
- Modify: `docs/development/v0.2-local-runbook.md`
- Modify: `examples/v0_2_sample_task.json`

**Interfaces:**
- Consumes: all routes, environment variables, migrations, and UI behavior from Tasks 1-9.
- Produces: a reproducible local runbook and fresh completion evidence.

- [ ] **Step 1: Update documentation tests/markers before prose**

Create `tests/project/test_artifact_docs.py` with a small documentation assertion that requires all of these literal markers:

```python
required = {
    "README.md": ["POST /api/v1/artifacts", "BRIDGEAI_ARTIFACT_STORAGE_ROOT"],
    "docs/development/v0.2-local-runbook.md": [
        "0005_artifacts.sql",
        "ARTIFACT_INTEGRITY_MISMATCH",
        "quality_status",
    ],
}
```

Run the test and confirm it fails before editing the documentation.

- [ ] **Step 2: Document setup and the real upload/create/run flow**

Update README development status to say that the first V0.3 Artifact slice is present without claiming all V0.3 Tools are complete. Update the runbook migration list through 0005 and document:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/artifacts \
  -F "file=@/absolute/path/to/bridge-image.jpg"
```

Then show task creation using the returned ID, execution, metadata/content retrieval, quality semantics, the 20 MiB/JPEG/PNG limits, local storage root, and stable repair guidance. State that legacy string-only records remain readable but cannot acquire fabricated image content. Update `examples/v0_2_sample_task.json` so its Artifact ID is explicitly documented as a value obtained from upload rather than a working built-in object.

- [ ] **Step 3: Run the complete automated verification suite**

Run fresh commands:

```bash
set -a
source .env
set +a
export BRIDGEAI_TEST_DATABASE_URL="${BRIDGEAI_DATABASE_URL%/*}/bridgeai_agent_test"
export LANGGRAPH_STRICT_MSGPACK=true
./.venv/bin/python -m backend.app.repositories.postgres.migrate
./.venv/bin/python -m pytest -q
npm test --prefix frontend
npm run build --prefix frontend
./.venv/bin/python -m pip check
git diff --check
```

Expected: migrations apply cleanly, every Python and frontend test passes, the frontend build exits zero, dependency check is clean, and Git reports no whitespace errors.

- [ ] **Step 4: Perform local browser acceptance with a controlled fixture**

Start the backend with `.env` and strict msgpack, then start Vite on port 5173. In the workbench:

1. Upload one known-good JPEG and confirm preview, size, dimensions, MIME, checksum prefix, and ready state.
2. Create a task and confirm the Artifact ID is automatic.
3. Run the task and confirm real metrics, thresholds, analyzer version, and a non-constant Tool payload.
4. Refresh the browser and restart only the backend; confirm task, run, preview, and result persist.
5. Upload a generated low-quality fixture; confirm the run is `completed` while the quality badge is warn/fail.
6. Confirm the browser console has no JavaScript errors and repeat the core view at 390 x 844.

Do not modify or corrupt files under the user's development storage root for acceptance. The tamper case is already covered inside pytest temporary storage.

- [ ] **Step 5: Gate one real oMLX run on current health**

Read `GET /api/v1/health`. Only when `components.model_gateway=configured` and `components.langgraph_checkpointer=ready`, run the uploaded task once with the configured oMLX profile. Verify the result exposes model ID, provider, runtime, `is_stub=false`, usage, Workflow runtime, checkpoint thread, and real quality Tool metrics. If either component is not ready, report the exact health state and documented restart/setup command instead of claiming live-model acceptance.

- [ ] **Step 6: Commit documentation and verified acceptance updates**

```bash
git add README.md docs/development/v0.2-local-runbook.md examples/v0_2_sample_task.json tests/project/test_artifact_docs.py
git commit -m "docs: document artifact quality workflow"
```

---

## Final Review Checklist

- [ ] Every production behavior was preceded by a focused failing test.
- [ ] New tasks accept exactly one uploaded ready Artifact.
- [ ] Legacy rows remain readable and missing legacy bytes fail explicitly on rerun.
- [ ] Uploads accept decoded JPEG/PNG only and enforce 20 MiB while streaming.
- [ ] PostgreSQL contains metadata only; local storage contains bytes only.
- [ ] Original filenames cannot affect storage paths.
- [ ] Normal handled failures clean temporary/final files created by that operation.
- [ ] Data check re-verifies file existence, size, SHA-256, format, and dimensions.
- [ ] Quality outputs contain metrics, thresholds, checks, reasons, and analyzer version.
- [ ] A quality fail is a completed negative result; a Tool failure is a failed Workflow.
- [ ] Checkpoints and API responses contain no bytes, absolute paths, secrets, or connection strings.
- [ ] Vue supports immediate upload, retry-safe task creation, persisted preview, quality cards, and legacy fallback.
- [ ] Python tests, PostgreSQL tests, frontend tests, frontend build, `pip check`, and `git diff --check` all have fresh zero-failure evidence.
- [ ] Live oMLX acceptance is reported only when current health proves the model gateway and Checkpointer are ready.
