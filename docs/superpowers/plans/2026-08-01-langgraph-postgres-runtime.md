# LangGraph PostgreSQL Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-written sequential inspection runner with a real LangGraph `StateGraph` whose per-run checkpoints are persisted by the official PostgreSQL Checkpointer, while preserving the existing task API, business history, oMLX Model Gateway, and Vue workbench.

**Architecture:** FastAPI and `TaskService` continue to own business-run lifecycle in `inspection_task_runs`. A runner adapter builds a synchronous bridge-inspection graph from injected Model Gateway and Tool dependencies, invokes it with `thread_id=run_id`, and returns the existing public snapshots. Production opens `PostgresSaver` against the configured PostgreSQL database; focused unit tests inject `InMemorySaver`. Framework tables are created only by an explicit idempotent setup command and are never reproduced by BridgeAI migrations.

**Tech Stack:** Python 3.12, LangGraph 1.2.x, `langgraph-checkpoint-postgres` 3.1.x, psycopg 3, PostgreSQL 17, FastAPI, pytest, Vue 3, TypeScript, Vite, Vitest, Vue Test Utils, Chrome browser verification.

## Global Constraints

- Implement only the confirmed first graph slice: `task_understanding -> data_check -> image_quality_check -> completed/failed`.
- Use the synchronous LangGraph API and synchronous `PostgresSaver`; do not introduce async conversion, queues, workers, streaming, retries, interrupts, or resume endpoints.
- Use the persisted business `run_id` as the exact LangGraph `thread_id`; never reuse the task ID as a thread ID.
- Keep `inspection_task_runs` as the product-facing history authority and LangGraph checkpoints as internal execution-state evidence.
- Do not copy, modify, constrain, or version LangGraph's internal SQL in BridgeAI migrations.
- Never call `PostgresSaver.setup()` during backend startup, health checks, or task requests.
- Production has no in-memory, SQLite, JSON-file, or silent no-checkpoint fallback. `InMemorySaver` is allowed only when a test explicitly injects it.
- Keep graph state serializer-safe: strings, booleans, numbers, `None`, lists, and dictionaries only. Do not store clients, connections, Tool executors, binary Artifacts, exceptions, or secrets.
- Set `LANGGRAPH_STRICT_MSGPACK=true` in local runtime configuration and all checkpoint integration tests.
- Never print, commit, return, or persist the Model Gateway API key or PostgreSQL credentials.
- Run destructive database preparation only when `BRIDGEAI_TEST_DATABASE_URL` resolves to the exact database name `bridgeai_agent_test`.
- Use `.venv/bin/python` for every Python install, test, migration, setup, and server command.
- Use TDD for every behavior: add the focused test, observe the expected failure, implement the minimum production change, then observe the focused test pass.
- Preserve existing task routes and response fields. New runtime metadata must be additive and backward compatible.
- Preserve the existing 503 Model Gateway error and 502 generic execution error; add a distinct 503 only for Checkpointer readiness failures.
- Commit after every completed task using the commit message specified by that task.

---

## File Responsibility Map

### LangGraph runtime

- `agent/langgraph_state.py`: serializer-safe `BridgeInspectionState`, append reducer, initial-state builder, and public snapshot conversion helpers.
- `agent/langgraph_workflow.py`: named nodes, conditional route, and `StateGraph` compilation from injected Model Gateway, Tool executor, and Checkpointer.
- `agent/runner.py`: domain-facing `AgentRunner` adapter; invokes the compiled graph with an explicit thread ID and converts terminal state back into `AgentRunResult`.
- `agent/workflow.py`: existing public `WorkflowState`, `WorkflowStep`, and `WorkflowStatus` records; retained as the API-facing compatibility snapshot.
- `tests/agent/test_langgraph_workflow.py`: graph topology, success/failure routing, ordered public history, and in-memory checkpoint coverage.
- `tests/agent/test_agent_runner.py`: runner facade and `thread_id=run_id` contract.

### Checkpointer infrastructure

- `backend/app/repositories/postgres/checkpoints.py`: explicit setup command, context-managed `PostgresSaver` factory, and read-only readiness probe.
- `tests/backend/postgres_test_support.py`: guarded reset for BridgeAI test tables and official Checkpointer tables in the isolated test database.
- `tests/backend/test_langgraph_checkpointer.py`: setup repeatability, readiness states, real PostgreSQL checkpoints, and thread isolation.
- `.env.example`: documented strict msgpack switch; no credentials beyond the existing redacted sample value.

### Business persistence and execution

- `backend/app/repositories/postgres/migrations/0003_langgraph_runtime.sql`: additive business-run runtime metadata and constraints.
- `backend/app/domain/tasks.py`: runtime metadata on `TaskRunRecord` and expanded repository protocol.
- `backend/app/domain/task_errors.py`: stable Checkpointer-not-ready error carrying the persisted run ID.
- `backend/app/repositories/postgres/tasks.py`: SQL mapping for runtime metadata and optional full failure snapshots.
- `backend/app/services/task_runs.py`: production runtime adapter that opens `PostgresSaver`, invokes `AgentRunner`, and serializes the existing result shape.
- `backend/app/services/tasks.py`: business-run creation, run-ID forwarding, successful/failed terminal persistence, and error preservation.
- `tests/backend/test_postgres_migrations.py`: migration order, defaults, constraints, and repeatability.
- `tests/backend/test_postgres_task_repository.py`: runtime metadata and complete failed-run snapshot persistence.
- `tests/backend/test_task_runs.py`: serialization contract with an explicitly injected test Checkpointer.
- `tests/backend/test_task_service.py`: run-ID forwarding, graph-terminal failure behavior, and Checkpointer exception persistence.

### API, health, and frontend

- `backend/app/api/v1/tasks.py`: HTTP translation for `LANGGRAPH_CHECKPOINTER_NOT_READY`.
- `backend/app/services/health.py`: `langgraph_checkpointer` health component without schema mutation.
- `tests/backend/test_tasks_api.py`: additive run fields and new 503 error payload.
- `tests/backend/test_health.py`: `ready`, `not_initialized`, and `unavailable` Checkpointer states.
- `frontend/src/types.ts`: additive `workflow_runtime` and `checkpoint_thread_id` fields.
- `frontend/src/components/TaskRunHistory.vue`: compact runtime badge in each historical run.
- `frontend/src/components/TaskRunDetail.vue`: runtime and checkpoint thread in the selected snapshot.
- `frontend/src/components/TaskRunHistory.test.ts`: runtime badge rendering and selection behavior.
- `frontend/src/components/TaskRunDetail.test.ts`: thread metadata and snapshot rendering.
- `frontend/src/App.vue`: actionable Checkpointer readiness message and status tone.
- `frontend/src/App.test.ts`: health and selected-run runtime integration.

### Documentation and verification

- `README.md`: current LangGraph runtime status and required setup order.
- `docs/development/v0.2-local-runbook.md`: install, business migration, Checkpointer setup, health, smoke, and troubleshooting commands.
- `pyproject.toml`: bounded LangGraph dependencies.

---

### Task 1: Add the Typed StateGraph and Unit-Test Its Routes

**Files:**
- Modify: `pyproject.toml`
- Create: `agent/langgraph_state.py`
- Create: `agent/langgraph_workflow.py`
- Create: `tests/agent/test_langgraph_workflow.py`

**Interfaces:**
- Consumes: `ModelGateway.understand_task(TaskUnderstandingRequest)`, `ToolExecutor.execute(tool_id, payload)`, `AgentModelProfile.as_payload()`, and a `BaseCheckpointSaver` supplied by the caller.
- Produces: `BridgeInspectionState`, `initial_bridge_inspection_state(*, task_id, run_id, task_type, objective, artifact_ids, agent_model) -> BridgeInspectionState`, and `build_bridge_inspection_graph(*, model_gateway, tool_executor, checkpointer)` returning an invokable compiled graph.

- [ ] **Step 1: Declare and install the bounded dependencies**

Set the base and backend dependencies in `pyproject.toml`:

```toml
[project]
dependencies = [
  "langgraph>=1.2.9,<1.3",
]

[project.optional-dependencies]
backend = [
  "fastapi>=0.115",
  "langgraph-checkpoint-postgres>=3.1,<3.2",
  "psycopg[binary]>=3.2",
  "uvicorn[standard]>=0.30",
]
```

Install and check dependency consistency:

```bash
./.venv/bin/python -m pip install -e ".[backend,dev]"
./.venv/bin/python -m pip check
```

Expected: installation succeeds, and `pip check` reports no broken requirements.

- [ ] **Step 2: Write the failing graph tests**

Create `tests/agent/test_langgraph_workflow.py` with four focused tests:

```python
from langgraph.checkpoint.memory import InMemorySaver

from agent.langgraph_state import initial_bridge_inspection_state
from agent.langgraph_workflow import build_bridge_inspection_graph
from tools.sdk import ToolExecutor, ToolManifest, ToolRegistry


def test_graph_routes_success_through_all_named_nodes():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=saver,
    )
    config = {"configurable": {"thread_id": "run_success"}}

    result = graph.invoke(_initial_state("run_success"), config=config)

    assert result["status"] == "completed"
    assert result["current_step"] == "completed"
    assert [item["step_name"] for item in result["workflow_history"]] == [
        "task_understanding",
        "data_check",
        "image_quality_check",
        "completed",
    ]
    assert result["tool_results"][0]["ok"] is True


def test_graph_routes_unsuccessful_tool_to_failed():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        tool_executor=ToolExecutor(
            _registry(required=["artifact_id", "camera_id"]),
        ),
        checkpointer=saver,
    )

    result = graph.invoke(
        _initial_state("run_failed"),
        config={"configurable": {"thread_id": "run_failed"}},
    )

    assert result["status"] == "failed"
    assert result["current_step"] == "failed"
    assert result["error_step"] == "image_quality_check"
    assert result["error_message"] == "Missing required input: camera_id"
    assert [item["step_name"] for item in result["workflow_history"]][-1] == "failed"


def test_graph_persists_multiple_checkpoints_for_one_thread():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=saver,
    )
    config = {"configurable": {"thread_id": "run_checkpointed"}}

    graph.invoke(_initial_state("run_checkpointed"), config=config)

    checkpoints = list(saver.list(config))
    assert len(checkpoints) >= 5
    assert checkpoints[0].checkpoint["channel_values"]["run_id"] == "run_checkpointed"


def test_initial_state_contains_only_serializer_safe_values():
    state = _initial_state("run_serializable")

    assert state["run_id"] == "run_serializable"
    assert state["workflow_history"] == []
    assert state["tool_results"] == []
    assert state["error_step"] is None
    assert state["error_message"] is None
```

The same file must define deterministic helpers with no network access:

```python
def _initial_state(run_id: str):
    return initial_bridge_inspection_state(
        task_id="task_001",
        run_id=run_id,
        task_type="bridge_inspection",
        objective="检查桥梁无人机影像质量",
        artifact_ids=["art_001"],
        agent_model={"model_id": "DeepSeek-V4-Flash-4bit"},
    )


def _registry(required: list[str]) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": required},
            output_schema={"required": ["quality_status"]},
        ),
        lambda payload: {
            "quality_status": "pass",
            "artifact_id": payload["artifact_id"],
        },
    )
    return registry
```

Reuse a local `_FakeModelGateway` and `_FakeModelResult` that return the same payload currently asserted in `tests/backend/test_task_runs.py`.

- [ ] **Step 3: Run the new tests and observe RED**

```bash
./.venv/bin/python -m pytest tests/agent/test_langgraph_workflow.py -q
```

Expected: collection fails because `agent.langgraph_state` and `agent.langgraph_workflow` do not exist.

- [ ] **Step 4: Implement the serializer-safe state**

Create `agent/langgraph_state.py` with this public shape:

```python
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class WorkflowHistoryItem(TypedDict):
    step_name: str
    output: dict[str, object]


class BridgeInspectionState(TypedDict):
    task_id: str
    run_id: str
    task_type: str
    objective: str
    artifact_ids: list[str]
    status: str
    current_step: str | None
    agent_model: dict[str, object]
    model_result: dict[str, object]
    workflow_history: Annotated[list[WorkflowHistoryItem], operator.add]
    tool_results: list[dict[str, object]]
    error_step: str | None
    error_message: str | None


def initial_bridge_inspection_state(
    *,
    task_id: str,
    run_id: str,
    task_type: str,
    objective: str,
    artifact_ids: list[str],
    agent_model: dict[str, object],
) -> BridgeInspectionState:
    return {
        "task_id": task_id,
        "run_id": run_id,
        "task_type": task_type,
        "objective": objective,
        "artifact_ids": list(artifact_ids),
        "status": "running",
        "current_step": None,
        "agent_model": dict(agent_model),
        "model_result": {},
        "workflow_history": [],
        "tool_results": [],
        "error_step": None,
        "error_message": None,
    }
```

- [ ] **Step 5: Implement the named graph and conditional edge**

Create `agent/langgraph_workflow.py` with node closures that return state updates rather than mutating input. Compile this exact topology:

```python
builder = StateGraph(BridgeInspectionState)
builder.add_node("task_understanding", task_understanding)
builder.add_node("data_check", data_check)
builder.add_node("image_quality_check", image_quality_check)
builder.add_node("completed", completed)
builder.add_node("failed", failed)
builder.add_edge(START, "task_understanding")
builder.add_edge("task_understanding", "data_check")
builder.add_edge("data_check", "image_quality_check")
builder.add_conditional_edges(
    "image_quality_check",
    route_after_tool,
    {"completed": "completed", "failed": "failed"},
)
builder.add_edge("completed", END)
builder.add_edge("failed", END)
return builder.compile(checkpointer=checkpointer)
```

Implement these exact public inputs:

```python
def build_bridge_inspection_graph(
    *,
    model_gateway: ModelGateway,
    tool_executor: ToolExecutor,
    checkpointer: BaseCheckpointSaver,
):
```

Each node appends one dictionary containing the exact keys `step_name` and `output`. `image_quality_check` stores the serialized `ToolResult`; `route_after_tool` returns `"completed"` only when its last Tool result has `ok is True`; `failed` copies the Tool error into `error_step` and `error_message`.

- [ ] **Step 6: Run the focused tests and observe GREEN**

```bash
./.venv/bin/python -m pytest tests/agent/test_langgraph_workflow.py -q
```

Expected: 4 tests pass without network or PostgreSQL access.

- [ ] **Step 7: Run the existing core regression suite**

```bash
./.venv/bin/python -m pytest tests/agent tests/tools -q
./.venv/bin/python -m pip check
git diff --check
```

Expected: the new tests and all existing Agent/Tool tests pass; dependency and whitespace checks pass.

- [ ] **Step 8: Commit the graph core**

```bash
git add pyproject.toml agent/langgraph_state.py agent/langgraph_workflow.py tests/agent/test_langgraph_workflow.py
git diff --cached --check
git commit -m "feat: add langgraph inspection workflow"
```

---

### Task 2: Add Explicit PostgreSQL Checkpointer Setup and Readiness

**Files:**
- Create: `backend/app/repositories/postgres/checkpoints.py`
- Modify: `tests/backend/postgres_test_support.py`
- Create: `tests/backend/test_langgraph_checkpointer.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `BRIDGEAI_DATABASE_URL`, `LANGGRAPH_STRICT_MSGPACK=true`, and the official `PostgresSaver` API.
- Produces: `CheckpointerStatus`, `probe_langgraph_checkpointer(database_url) -> CheckpointerStatus`, `open_postgres_checkpointer(database_url)`, `setup_langgraph_checkpointer(database_url) -> None`, and `python -m backend.app.repositories.postgres.checkpoints`.

- [ ] **Step 1: Extend the guarded PostgreSQL test reset**

Add a separate helper to `tests/backend/postgres_test_support.py`:

```python
def reset_langgraph_checkpoint_tables(database_url: str) -> None:
    if urlparse(database_url).path.lstrip("/") != EXPECTED_TEST_DATABASE:
        raise RuntimeError("Checkpoint reset is restricted to bridgeai_agent_test")
    with psycopg.connect(database_url) as connection:
        connection.execute(
            "DROP TABLE IF EXISTS checkpoint_writes, checkpoint_blobs, "
            "checkpoints, checkpoint_migrations CASCADE",
        )
```

This helper is test-only. Production BridgeAI code must not drop or alter these tables.

- [ ] **Step 2: Write the failing setup and probe tests**

Create `tests/backend/test_langgraph_checkpointer.py`:

```python
from __future__ import annotations

import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from agent.langgraph_state import initial_bridge_inspection_state
from agent.langgraph_workflow import build_bridge_inspection_graph
from backend.app.repositories.postgres.checkpoints import (
    probe_langgraph_checkpointer,
    setup_langgraph_checkpointer,
)
from tests.backend.postgres_test_support import (
    require_test_database_url,
    reset_langgraph_checkpoint_tables,
)
from tools.sdk import ToolExecutor


@pytest.mark.postgres
def test_checkpointer_setup_is_explicit_repeatable_and_probeable(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_STRICT_MSGPACK", "true")
    database_url = require_test_database_url()
    reset_langgraph_checkpoint_tables(database_url)

    assert probe_langgraph_checkpointer(database_url) == "not_initialized"
    setup_langgraph_checkpointer(database_url)
    setup_langgraph_checkpointer(database_url)
    assert probe_langgraph_checkpointer(database_url) == "ready"


@pytest.mark.postgres
def test_postgres_saver_keeps_run_threads_isolated(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_STRICT_MSGPACK", "true")
    database_url = require_test_database_url()
    reset_langgraph_checkpoint_tables(database_url)
    setup_langgraph_checkpointer(database_url)

    with PostgresSaver.from_conn_string(database_url) as saver:
        graph = build_bridge_inspection_graph(
            model_gateway=_FakeModelGateway(),
            tool_executor=ToolExecutor(_successful_registry()),
            checkpointer=saver,
        )
        for run_id in ("run_pg_001", "run_pg_002"):
            graph.invoke(
                _initial_state(run_id),
                config={"configurable": {"thread_id": run_id}},
            )

        first = list(saver.list({"configurable": {"thread_id": "run_pg_001"}}))
        second = list(saver.list({"configurable": {"thread_id": "run_pg_002"}}))

    assert len(first) >= 5
    assert len(second) >= 5
    assert first[0].checkpoint["channel_values"]["run_id"] == "run_pg_001"
    assert second[0].checkpoint["channel_values"]["run_id"] == "run_pg_002"
```

Define `_FakeModelGateway`, `_initial_state`, and `_successful_registry` locally with the same deterministic values as Task 1; do not import private test helpers from another test module.

- [ ] **Step 3: Run the Checkpointer tests and observe RED**

Load the isolated test URL without echoing it:

```bash
set -a
source .env
set +a
export BRIDGEAI_TEST_DATABASE_URL="${BRIDGEAI_DATABASE_URL%/*}/bridgeai_agent_test"
export LANGGRAPH_STRICT_MSGPACK=true
./.venv/bin/python -m pytest tests/backend/test_langgraph_checkpointer.py -q
```

Expected: collection fails because `backend.app.repositories.postgres.checkpoints` does not exist.

- [ ] **Step 4: Implement the explicit lifecycle module**

Create `backend/app/repositories/postgres/checkpoints.py` with these behaviors:

```python
from contextlib import contextmanager
from typing import Iterator, Literal

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

from backend.app.repositories.postgres.connection import connect, get_database_url


CheckpointerStatus = Literal["ready", "not_initialized", "unavailable"]
REQUIRED_CHECKPOINT_TABLES = (
    "checkpoint_migrations",
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
)


@contextmanager
def open_postgres_checkpointer(database_url: str) -> Iterator[PostgresSaver]:
    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        yield checkpointer


def setup_langgraph_checkpointer(database_url: str) -> None:
    with open_postgres_checkpointer(database_url) as checkpointer:
        checkpointer.setup()


def probe_langgraph_checkpointer(database_url: str) -> CheckpointerStatus:
    if not database_url:
        return "unavailable"
    try:
        with connect(database_url) as connection:
            tables = connection.execute(
                "SELECT "
                "to_regclass('public.checkpoint_migrations'), "
                "to_regclass('public.checkpoints'), "
                "to_regclass('public.checkpoint_blobs'), "
                "to_regclass('public.checkpoint_writes')",
            ).fetchone()
    except psycopg.Error:
        return "unavailable"
    return "ready" if tables and all(tables) else "not_initialized"
```

Add `main()` that requires `BRIDGEAI_DATABASE_URL`, calls `setup_langgraph_checkpointer`, and prints only `langgraph checkpointer ready`. It must never print the URL.

- [ ] **Step 5: Document strict deserialization in the environment template**

Add this non-secret line to `.env.example`:

```dotenv
LANGGRAPH_STRICT_MSGPACK=true
```

- [ ] **Step 6: Run the focused PostgreSQL tests and observe GREEN**

```bash
./.venv/bin/python -m pytest tests/backend/test_langgraph_checkpointer.py -q
```

Expected: setup is repeatable, probe transitions from `not_initialized` to `ready`, both runs produce multiple checkpoints, and their thread histories remain isolated.

- [ ] **Step 7: Verify the command is repeatable against the isolated test database**

```bash
export BRIDGEAI_DATABASE_URL="$BRIDGEAI_TEST_DATABASE_URL"
./.venv/bin/python -m backend.app.repositories.postgres.checkpoints
./.venv/bin/python -m backend.app.repositories.postgres.checkpoints
```

Expected: both invocations print `langgraph checkpointer ready`; neither prints credentials.

- [ ] **Step 8: Commit the Checkpointer lifecycle**

```bash
git add .env.example backend/app/repositories/postgres/checkpoints.py tests/backend/postgres_test_support.py tests/backend/test_langgraph_checkpointer.py
git diff --cached --check
git commit -m "feat: add postgres checkpoint lifecycle"
```

---

### Task 3: Persist Runtime Metadata and Full Failure Snapshots

**Files:**
- Create: `backend/app/repositories/postgres/migrations/0003_langgraph_runtime.sql`
- Modify: `backend/app/domain/tasks.py`
- Modify: `backend/app/repositories/postgres/tasks.py`
- Modify: `tests/backend/test_postgres_migrations.py`
- Modify: `tests/backend/test_postgres_task_repository.py`
- Modify: `tests/backend/test_tasks_api.py`

**Interfaces:**
- Consumes: existing task/run relational schema and JSONB snapshots.
- Produces: `TaskRunRecord.workflow_runtime: str`, `TaskRunRecord.checkpoint_thread_id: str | None`, required runtime arguments on `start_run`, and optional snapshot arguments on `fail_run`.

- [ ] **Step 1: Write the failing migration assertions**

Update `tests/backend/test_postgres_migrations.py` to expect:

```python
assert first == [
    "0001_v0_2_skeleton.sql",
    "0002_task_history.sql",
    "0003_langgraph_runtime.sql",
]
assert {row[0] for row in columns} >= {
    "workflow_runtime",
    "checkpoint_thread_id",
}
```

Also insert a run without specifying the new columns and assert it reads back as `workflow_runtime='legacy'` with a null checkpoint thread.

- [ ] **Step 2: Write the failing repository contract tests**

Update `tests/backend/test_postgres_task_repository.py` so the first run is started with explicit graph metadata:

```python
started = repository.start_run(
    "task_alpha",
    "run_001",
    workflow_runtime="langgraph",
    checkpoint_thread_id="run_001",
)

assert started.workflow_runtime == "langgraph"
assert started.checkpoint_thread_id == "run_001"
```

Add a failed terminal snapshot test:

```python
failed = repository.fail_run(
    "run_001",
    "image quality failed",
    agent_model={"model_id": "DeepSeek-V4-Flash-4bit"},
    workflow={
        "status": "failed",
        "current_step": "failed",
        "history": [{"step_name": "failed", "output": {}}],
    },
    tool_results=[{"tool_id": "image_quality_check", "ok": False}],
)

assert failed.status == "failed"
assert failed.agent_model["model_id"] == "DeepSeek-V4-Flash-4bit"
assert failed.workflow["current_step"] == "failed"
assert failed.tool_results[0]["ok"] is False
```

Add a database-level assertion that a second run cannot reuse the same non-null checkpoint thread ID.

- [ ] **Step 3: Run the migration and repository tests and observe RED**

```bash
./.venv/bin/python -m pytest tests/backend/test_postgres_migrations.py tests/backend/test_postgres_task_repository.py -q
```

Expected: failures report the missing migration, missing `TaskRunRecord` fields, and old repository signatures.

- [ ] **Step 4: Create the additive business migration**

Create `0003_langgraph_runtime.sql` with:

```sql
ALTER TABLE inspection_task_runs
    ADD COLUMN IF NOT EXISTS workflow_runtime TEXT NOT NULL DEFAULT 'legacy',
    ADD COLUMN IF NOT EXISTS checkpoint_thread_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_workflow_runtime'
    ) THEN
        ALTER TABLE inspection_task_runs
            ADD CONSTRAINT ck_inspection_task_runs_workflow_runtime
            CHECK (workflow_runtime IN ('legacy', 'langgraph'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_checkpoint_thread_nonblank'
    ) THEN
        ALTER TABLE inspection_task_runs
            ADD CONSTRAINT ck_inspection_task_runs_checkpoint_thread_nonblank
            CHECK (
                checkpoint_thread_id IS NULL
                OR btrim(checkpoint_thread_id) <> ''
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_runtime_thread'
    ) THEN
        ALTER TABLE inspection_task_runs
            ADD CONSTRAINT ck_inspection_task_runs_runtime_thread
            CHECK (
                (workflow_runtime = 'legacy' AND checkpoint_thread_id IS NULL)
                OR
                (workflow_runtime = 'langgraph' AND checkpoint_thread_id IS NOT NULL)
            );
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_task_runs_checkpoint_thread
    ON inspection_task_runs (checkpoint_thread_id)
    WHERE checkpoint_thread_id IS NOT NULL;
```

Do not add any framework checkpoint tables to this file.

- [ ] **Step 5: Extend the domain record and protocol**

Add the fields to `TaskRunRecord` and `as_payload()`:

```python
workflow_runtime: str
checkpoint_thread_id: str | None
```

Change the protocol signatures to:

```python
def start_run(
    self,
    task_id: str,
    run_id: str,
    *,
    workflow_runtime: str = "legacy",
    checkpoint_thread_id: str | None = None,
) -> TaskRunRecord:
    raise NotImplementedError

def fail_run(
    self,
    run_id: str,
    error_message: str,
    *,
    agent_model: dict[str, object] | None = None,
    workflow: dict[str, object] | None = None,
    tool_results: list[dict[str, object]] | None = None,
) -> TaskRunRecord:
    raise NotImplementedError
```

- [ ] **Step 6: Update PostgreSQL mapping and writes**

Add `workflow_runtime, checkpoint_thread_id` to `_RUN_COLUMNS`. Insert both values in `start_run`. In `fail_run`, update snapshots with `COALESCE` so exception paths preserve existing empty snapshots while graph-terminal failures store complete snapshots:

```sql
UPDATE inspection_task_runs SET
    status = 'failed',
    agent_model = COALESCE(%s, agent_model),
    workflow = COALESCE(%s, workflow),
    tool_results = COALESCE(%s, tool_results),
    error_message = %s,
    completed_at = NOW()
WHERE run_id = %s
```

Wrap non-null payloads with `Jsonb`; pass SQL null for omitted snapshots. Map both runtime fields in `_run_from_row`.

- [ ] **Step 7: Update existing test fixtures for the additive fields**

Every direct `TaskRunRecord` constructor call in `tests/backend/test_tasks_api.py` must include:

```python
workflow_runtime="langgraph",
checkpoint_thread_id="run_001",
```

Every direct `repository.start_run` call in backend tests must supply an explicit runtime and thread pair. The protocol defaults keep the intermediate commit backward compatible with the not-yet-refactored service; Task 4 makes all production calls explicit.

- [ ] **Step 8: Run persistence and API serialization tests and observe GREEN**

```bash
./.venv/bin/python -m pytest tests/backend/test_postgres_migrations.py tests/backend/test_postgres_task_repository.py tests/backend/test_tasks_api.py -q
```

Expected: the migration is repeatable, old/default rows are `legacy`, graph runs expose their thread ID, failed snapshots remain complete, and API payloads include both additive fields.

- [ ] **Step 9: Commit business persistence changes**

```bash
git add backend/app/repositories/postgres/migrations/0003_langgraph_runtime.sql backend/app/domain/tasks.py backend/app/repositories/postgres/tasks.py tests/backend/test_postgres_migrations.py tests/backend/test_postgres_task_repository.py tests/backend/test_tasks_api.py
git diff --cached --check
git commit -m "feat: persist langgraph runtime metadata"
```

---

### Task 4: Route Task Execution Through the Checkpointed Graph

**Files:**
- Modify: `agent/runner.py`
- Modify: `backend/app/domain/task_errors.py`
- Modify: `backend/app/services/task_runs.py`
- Modify: `backend/app/services/tasks.py`
- Modify: `tests/agent/test_agent_runner.py`
- Modify: `tests/backend/test_task_runs.py`
- Modify: `tests/backend/test_task_service.py`

**Interfaces:**
- Consumes: `AgentTaskContext`, injected `BaseCheckpointSaver`, `run_id`, business task input, Model Gateway, Tool registry, and configured database URL.
- Produces: `AgentRunner.run(context, *, thread_id) -> AgentRunResult`, `run_inspection_task(run_id, payload, *, database_url=None, model_gateway=None, checkpointer=None) -> dict[str, object]`, and `LangGraphCheckpointerNotReadyError(run_id, message)`.

- [ ] **Step 1: Write the failing runner facade tests**

Update `tests/agent/test_agent_runner.py` so every runner receives `InMemorySaver()` and every call supplies an explicit thread:

```python
saver = InMemorySaver()
runner = AgentRunner(
    registry,
    model_gateway=_FakeModelGateway(),
    checkpointer=saver,
)

result = runner.run(context, thread_id="run_agent_001")

assert result.status == "completed"
assert [step.step_name for step in result.workflow.history] == [
    "task_understanding",
    "data_check",
    "image_quality_check",
    "completed",
]
assert len(list(saver.list({"configurable": {"thread_id": "run_agent_001"}}))) >= 5
```

Retain the existing success and Tool-failure assertions, updating the expected history for the named Tool and terminal nodes.

- [ ] **Step 2: Write the failing task-run adapter test**

Update `tests/backend/test_task_runs.py`:

```python
result = run_inspection_task(
    "run_001",
    {
        "task_id": "task_001",
        "task_type": "bridge_inspection",
        "objective": "检查桥梁无人机影像质量",
        "artifact_ids": ["art_001"],
    },
    model_gateway=_FakeModelGateway(),
    checkpointer=InMemorySaver(),
)

assert result["status"] == "completed"
assert [item["step_name"] for item in result["workflow"]["history"]] == [
    "task_understanding",
    "data_check",
    "image_quality_check",
    "completed",
]
```

Keep the existing exact model profile, model result, usage, Tool output, and error-field assertions.

- [ ] **Step 3: Write the failing service orchestration tests**

Change the test callable contract in `tests/backend/test_task_service.py` to `(run_id, payload)`. Assert that the service forwards the persisted run ID:

```python
calls = []

def run_inspection(run_id, payload):
    calls.append((run_id, payload))
    return _successful_run(payload)

run = TaskService(repository, run_inspection).execute_task("task_001")

assert calls[0][0] == run.run_id
assert run.workflow_runtime == "langgraph"
assert run.checkpoint_thread_id == run.run_id
```

Add a graph-terminal Tool failure test whose callable returns a `status='failed'` result containing model, Workflow, Tool, and error snapshots. Assert `execute_task` returns a failed record with HTTP-worthy normal control flow and does not raise.

Add a Checkpointer failure test:

```python
def unavailable(run_id, payload):
    raise LangGraphCheckpointerNotReadyError(run_id, "checkpoint tables missing")

with pytest.raises(LangGraphCheckpointerNotReadyError) as error:
    service.execute_task("task_001")

saved = repository.list_runs("task_001")[0]
assert saved.run_id == error.value.run_id
assert saved.status == "failed"
assert saved.checkpoint_thread_id == saved.run_id
```

- [ ] **Step 4: Run the focused tests and observe RED**

```bash
./.venv/bin/python -m pytest tests/agent/test_agent_runner.py tests/backend/test_task_runs.py tests/backend/test_task_service.py -q
```

Expected: failures show that the runner has no Checkpointer/thread contract, the task adapter has the old signature, and the service callable does not receive `run_id`.

- [ ] **Step 5: Convert `AgentRunner` into the graph facade**

Change its constructor and run signature:

```python
def __init__(
    self,
    registry: ToolRegistry,
    *,
    checkpointer: BaseCheckpointSaver,
    model_profile: AgentModelProfile | None = None,
    model_gateway: ModelGateway | None = None,
) -> None:

def run(
    self,
    context: AgentTaskContext,
    *,
    thread_id: str,
) -> AgentRunResult:
```

Inside `run`, build the initial state with `run_id=thread_id`, compile with the injected Checkpointer, and invoke with:

```python
config = {"configurable": {"thread_id": thread_id}}
terminal = graph.invoke(initial, config=config)
```

Convert `terminal["workflow_history"]` into immutable `WorkflowStep` records and `terminal["tool_results"]` into `ToolResult` records. Keep `AgentRunResult` and public `WorkflowState` as the return boundary; do not expose LangGraph classes to backend services.

- [ ] **Step 6: Add the stable Checkpointer error**

Add to `backend/app/domain/task_errors.py`:

```python
class LangGraphCheckpointerNotReadyError(RuntimeError):
    """Raised after a business run exists but its Checkpointer is not ready."""

    def __init__(self, run_id: str, message: str) -> None:
        super().__init__(message)
        self.run_id = run_id
```

- [ ] **Step 7: Implement the production task-run adapter**

Use this exact signature in `backend/app/services/task_runs.py`:

```python
def run_inspection_task(
    run_id: str,
    payload: dict[str, Any],
    *,
    database_url: str | None = None,
    model_gateway: ModelGateway | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> dict[str, object]:
```

When `checkpointer` is explicitly supplied, use it directly for focused tests. Otherwise:

1. resolve `database_url` or `BRIDGEAI_DATABASE_URL`;
2. require `probe_langgraph_checkpointer(url) == 'ready'`;
3. open `open_postgres_checkpointer(url)`;
4. construct `AgentRunner` with `checkpointer=saver`, then call `run(context, thread_id=run_id)`;
5. serialize the existing model, Workflow, and Tool result shape.

Map absent tables, an unavailable probe, and psycopg checkpoint failures to `LangGraphCheckpointerNotReadyError(run_id, sanitized generic text)`. Never call `setup()` here.

- [ ] **Step 8: Update `TaskService` business-run semantics**

Change the callable alias to:

```python
RunInspection = Callable[[str, dict[str, object]], dict[str, object]]
```

Start every new run with:

```python
run_id = _new_id("run")
started = self._repository.start_run(
    task_id,
    run_id,
    workflow_runtime="langgraph",
    checkpoint_thread_id=run_id,
)
```

Pass the same `run_id` to `self._run_inspection(run_id, payload)`.

If the returned result has `status == 'failed'`, call `fail_run` with the graph's error message and all three snapshots, then return that failed record without raising. Continue to use `complete_run` for `status == 'completed'`. Reject any other terminal status through `TaskExecutionError`.

Resolve the required nonblank failure text in this order: `workflow.error_message`, the first failed Tool result's `error_message`, then the fixed fallback `workflow failed`. This keeps the database failure constraint valid without inventing a successful result.

Catch `LangGraphCheckpointerNotReadyError` separately, mark the persisted business run failed, and re-raise it unchanged. Preserve the existing Model Gateway and generic exception branches.

In `build_task_service_from_environment`, bind the already-resolved database URL:

```python
run_inspection=partial(run_inspection_task, database_url=database_url)
```

- [ ] **Step 9: Run the focused tests and observe GREEN**

```bash
./.venv/bin/python -m pytest tests/agent/test_agent_runner.py tests/backend/test_task_runs.py tests/backend/test_task_service.py -q
```

Expected: the runner creates checkpoints under the explicit run thread, task serialization remains compatible, completed and Tool-failed terminals persist full snapshots, and Checkpointer readiness errors preserve their run ID.

- [ ] **Step 10: Run graph and persistence regressions**

```bash
./.venv/bin/python -m pytest tests/agent tests/backend/test_langgraph_checkpointer.py tests/backend/test_postgres_task_repository.py -q
git diff --check
```

Expected: all graph, Checkpointer, runner, and repository tests pass.

- [ ] **Step 11: Commit the execution integration**

```bash
git add agent/runner.py backend/app/domain/task_errors.py backend/app/services/task_runs.py backend/app/services/tasks.py tests/agent/test_agent_runner.py tests/backend/test_task_runs.py tests/backend/test_task_service.py
git diff --cached --check
git commit -m "feat: run inspection tasks with langgraph"
```

---

### Task 5: Expose Checkpointer Errors and Health Without Mutating Schema

**Files:**
- Modify: `backend/app/api/v1/tasks.py`
- Modify: `backend/app/services/health.py`
- Modify: `tests/backend/test_tasks_api.py`
- Modify: `tests/backend/test_health.py`

**Interfaces:**
- Consumes: `LangGraphCheckpointerNotReadyError`, `probe_langgraph_checkpointer`, existing task API, and health component payload.
- Produces: HTTP 503 `LANGGRAPH_CHECKPOINTER_NOT_READY` with `run_id`, plus `components.langgraph_checkpointer` in every local health response.

- [ ] **Step 1: Add the failing API error case**

Add this case to the parameterized table in `tests/backend/test_tasks_api.py`:

```python
(
    "post",
    "/api/v1/tasks/task_001/runs",
    LangGraphCheckpointerNotReadyError("run_checkpoint", "tables missing"),
    503,
    {
        "code": "LANGGRAPH_CHECKPOINTER_NOT_READY",
        "message": (
            "LangGraph 检查点存储未就绪，请先执行显式初始化命令并检查 PostgreSQL。"
        ),
        "run_id": "run_checkpoint",
    },
),
```

Also assert the normal run payload exposes `workflow_runtime == 'langgraph'` and `checkpoint_thread_id == 'run_001'`.

- [ ] **Step 2: Add failing health-state tests**

Update `tests/backend/test_health.py` to inject a deterministic Checkpointer probe:

```python
payload = build_local_health_payload(
    environ={"BRIDGEAI_DATABASE_URL": "postgresql://local/bridgeai"},
    database_probe=lambda _: True,
    checkpointer_probe=lambda _: "ready",
)
assert payload["components"]["langgraph_checkpointer"] == "ready"
```

Add separate assertions for `not_initialized` and `unavailable`. Assert the probe callable is not allowed to call setup or mutate the database by keeping it a read-only status function.

Update the exact component-dictionary expectations in the existing health tests to include `langgraph_checkpointer`; use `unavailable` when no database URL exists.

- [ ] **Step 3: Run API and health tests and observe RED**

```bash
./.venv/bin/python -m pytest tests/backend/test_tasks_api.py tests/backend/test_health.py -q
```

Expected: the API treats the new error as generic and health omits `langgraph_checkpointer`.

- [ ] **Step 4: Add Checkpointer HTTP translation**

Import `LangGraphCheckpointerNotReadyError` in `backend/app/api/v1/tasks.py`, include it in `_service_call`, and handle it before the generic execution branch:

```python
elif isinstance(exc, LangGraphCheckpointerNotReadyError):
    status_code = 503
    detail = {
        "code": "LANGGRAPH_CHECKPOINTER_NOT_READY",
        "message": (
            "LangGraph 检查点存储未就绪，请先执行显式初始化命令并检查 PostgreSQL。"
        ),
        "run_id": exc.run_id,
    }
```

- [ ] **Step 5: Add the read-only health component**

Change the health builder signature to:

```python
def build_local_health_payload(
    environ: Mapping[str, str] | None = None,
    database_probe: Callable[[str], bool] = probe_database,
    checkpointer_probe: Callable[[str], CheckpointerStatus] = probe_langgraph_checkpointer,
) -> dict[str, object]:
```

Resolve the database URL once. When no URL exists, report `langgraph_checkpointer='unavailable'`; otherwise report the exact Checkpointer probe result. Never call `setup_langgraph_checkpointer` from the health path.

- [ ] **Step 6: Run the focused tests and observe GREEN**

```bash
./.venv/bin/python -m pytest tests/backend/test_tasks_api.py tests/backend/test_health.py tests/backend/test_main_app.py -q
```

Expected: existing API translations remain unchanged, the new 503 includes the persisted run ID, and all three Checkpointer health states are exposed.

- [ ] **Step 7: Commit API and health visibility**

```bash
git add backend/app/api/v1/tasks.py backend/app/services/health.py tests/backend/test_tasks_api.py tests/backend/test_health.py
git diff --cached --check
git commit -m "feat: expose langgraph runtime readiness"
```

---

### Task 6: Show Runtime and Checkpoint Identity in the Vue Workbench

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/components/TaskRunHistory.vue`
- Modify: `frontend/src/components/TaskRunDetail.vue`
- Create: `frontend/src/components/TaskRunHistory.test.ts`
- Create: `frontend/src/components/TaskRunDetail.test.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.test.ts`

**Interfaces:**
- Consumes: additive task-run fields and `health.components.langgraph_checkpointer`.
- Produces: visible runtime label, visible checkpoint thread, warning for `not_initialized`/`unavailable`, and typed rendering with no unsafe assumptions.

- [ ] **Step 1: Add the failing focused component tests**

Create `TaskRunHistory.test.ts` with a complete `TaskRunRecord` fixture and assertions:

```ts
expect(wrapper.text()).toContain('LangGraph')
expect(wrapper.text()).toContain('run_001')
await wrapper.get('button[data-run-id="run_001"]').trigger('click')
expect(wrapper.emitted('select')).toEqual([['run_001']])
```

Create `TaskRunDetail.test.ts` and assert:

```ts
expect(wrapper.text()).toContain('LangGraph')
expect(wrapper.text()).toContain('run_001')
expect(wrapper.text()).toContain('task_understanding')
expect(wrapper.text()).toContain('image_quality_check')
```

The shared fixture must include:

```ts
workflow_runtime: 'langgraph',
checkpoint_thread_id: 'run_001',
```

- [ ] **Step 2: Add the failing App health assertion**

Set `health.components.langgraph_checkpointer = 'not_initialized'` in one `App.test.ts` case and assert the page contains:

```text
LangGraph 检查点表尚未初始化
```

Update every `TaskRunRecord` fixture in the file with the two additive runtime fields.

- [ ] **Step 3: Run frontend tests and observe RED**

```bash
npm test --prefix frontend -- --run
```

Expected: TypeScript fixtures and rendering assertions fail because the runtime fields and messages do not exist.

- [ ] **Step 4: Extend the TypeScript API contract**

Add to `TaskRunRecord` in `frontend/src/types.ts`:

```ts
workflow_runtime: 'legacy' | 'langgraph'
checkpoint_thread_id: string | null
```

- [ ] **Step 5: Render runtime metadata accessibly**

In `TaskRunHistory.vue`, render `LangGraph` for `workflow_runtime === 'langgraph'`, otherwise `Legacy`, plus the non-null thread ID in a `<small>` element.

In `TaskRunDetail.vue`, add a compact metadata row with labels `Workflow Runtime` and `Checkpoint Thread`. Render `未记录` for a null thread without inventing an ID.

- [ ] **Step 6: Add the actionable readiness message**

In `App.vue`, derive a Checkpointer warning:

```ts
const checkpointerStatus = computed(() => health.value?.components.langgraph_checkpointer)
const checkpointerWarning = computed(() => {
  if (checkpointerStatus.value === 'not_initialized') {
    return 'LangGraph 检查点表尚未初始化，请先执行后端显式初始化命令。'
  }
  if (checkpointerStatus.value === 'unavailable') {
    return 'LangGraph 检查点存储不可用，请检查 PostgreSQL 连接。'
  }
  return ''
})
```

Render it in the backend status panel with the existing warning style. Add `not_initialized` to the warning branch of `statusTone`.

- [ ] **Step 7: Run frontend tests and build and observe GREEN**

```bash
npm test --prefix frontend -- --run
npm run build --prefix frontend
```

Expected: component/App tests pass, Vue type checking passes, and Vite produces a production build.

- [ ] **Step 8: Commit the frontend runtime surface**

```bash
git add frontend/src/types.ts frontend/src/components/TaskRunHistory.vue frontend/src/components/TaskRunDetail.vue frontend/src/components/TaskRunHistory.test.ts frontend/src/components/TaskRunDetail.test.ts frontend/src/App.vue frontend/src/App.test.ts
git diff --cached --check
git commit -m "feat: show langgraph execution metadata"
```

---

### Task 7: Document, Verify, and Close the LangGraph Slice

**Files:**
- Modify: `README.md`
- Modify: `docs/development/v0.2-local-runbook.md`
- Verify: all source, tests, migrations, production build, local PostgreSQL, live API, and browser interaction

**Interfaces:**
- Consumes: completed LangGraph implementation and the user's existing local PostgreSQL/oMLX configuration.
- Produces: reproducible setup order, troubleshooting guidance, automated proof, real PostgreSQL checkpoint proof, and live workbench proof.

- [ ] **Step 1: Update the README runtime status**

Document that:

- the graph has five named nodes and conditional Tool routing;
- each business run uses `checkpoint_thread_id=run_id`;
- task history stays in BridgeAI business tables;
- graph execution state stays in official LangGraph checkpoint tables;
- business migrations and Checkpointer setup are separate explicit commands;
- resume/retry, interrupts, async workers, streaming, Store, Memory, and RAG are outside this slice.

Show this exact setup order:

```bash
set -a
source .env
set +a
export LANGGRAPH_STRICT_MSGPACK=true
./.venv/bin/python -m backend.app.repositories.postgres.migrate
./.venv/bin/python -m backend.app.repositories.postgres.checkpoints
./.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 2: Expand the local runbook**

Add sections for:

- dependency install and `pip check`;
- `0003_langgraph_runtime.sql`;
- explicit, repeatable Checkpointer setup;
- `LANGGRAPH_STRICT_MSGPACK=true`;
- health meanings for `ready`, `not_initialized`, and `unavailable`;
- `LANGGRAPH_CHECKPOINTER_NOT_READY` remediation;
- business history versus framework checkpoint ownership;
- known non-atomic crash behavior and deferred resume/reconciliation;
- two-run acceptance and restart verification.

- [ ] **Step 3: Run the complete automated verification**

Prepare the isolated database URL without printing credentials:

```bash
set -a
source .env
set +a
export BRIDGEAI_TEST_DATABASE_URL="${BRIDGEAI_DATABASE_URL%/*}/bridgeai_agent_test"
export LANGGRAPH_STRICT_MSGPACK=true
./.venv/bin/python -m pytest -q
npm test --prefix frontend -- --run
npm run build --prefix frontend
./.venv/bin/python -m pip check
git diff --check
```

Expected: all Python tests, real PostgreSQL tests, frontend tests, production build, dependency checks, and whitespace checks pass.

- [ ] **Step 4: Initialize the development database explicitly**

```bash
./.venv/bin/python -m backend.app.repositories.postgres.migrate
./.venv/bin/python -m backend.app.repositories.postgres.checkpoints
./.venv/bin/python -m backend.app.repositories.postgres.checkpoints
```

Expected: the business migration applies once, both Checkpointer setup invocations succeed, and no credentials are printed.

- [ ] **Step 5: Start the backend and frontend in two managed sessions**

Backend:

```bash
set -a
source .env
set +a
export LANGGRAPH_STRICT_MSGPACK=true
./.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173
```

Expected: both processes remain running without startup errors.

- [ ] **Step 6: Execute a two-run API smoke and inspect real checkpoints**

Run this exact Python smoke script from the repository root while the backend is live:

```bash
./.venv/bin/python - <<'PY'
import json
import os
import urllib.request
import uuid

from langgraph.checkpoint.postgres import PostgresSaver

base = "http://127.0.0.1:8000/api/v1"
request = urllib.request.Request(
    f"{base}/tasks",
    data=json.dumps(
        {
            "title": "LangGraph 双运行验收",
            "task_type": "bridge_inspection",
            "objective": "检查桥梁无人机影像质量",
            "artifact_ids": ["art_langgraph_acceptance"],
        },
        ensure_ascii=False,
    ).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Idempotency-Key": f"langgraph-acceptance-{uuid.uuid4().hex}",
    },
    method="POST",
)
with urllib.request.urlopen(request) as response:
    task = json.load(response)

runs = []
for _ in range(2):
    run_request = urllib.request.Request(
        f"{base}/tasks/{task['task_id']}/runs",
        data=b"",
        method="POST",
    )
    with urllib.request.urlopen(run_request) as response:
        runs.append(json.load(response))

assert runs[1]["run_number"] == runs[0]["run_number"] + 1
assert all(run["status"] == "completed" for run in runs)
assert all(run["workflow_runtime"] == "langgraph" for run in runs)
assert all(run["checkpoint_thread_id"] == run["run_id"] for run in runs)

database_url = os.environ["BRIDGEAI_DATABASE_URL"]
with PostgresSaver.from_conn_string(database_url) as saver:
    counts = [
        len(list(saver.list({"configurable": {"thread_id": run["run_id"]}})))
        for run in runs
    ]
assert all(count >= 5 for count in counts)
print(
    json.dumps(
        {
            "task_id": task["task_id"],
            "run_ids": [run["run_id"] for run in runs],
            "checkpoint_counts": counts,
        },
        ensure_ascii=False,
    ),
)
PY
```

Expected: two completed business runs have distinct run/thread IDs and at least five checkpoints each. Output contains IDs and counts only, never credentials or model keys.

- [ ] **Step 7: Verify the live workbench interaction**

Use `build-web-apps:frontend-testing-debugging` and browser control at `http://127.0.0.1:5173`.

Verify:

- health shows `database=ready` and `langgraph_checkpointer=ready`;
- the two-run task is selectable;
- history shows two runs in reverse order;
- each run shows `LangGraph` and its own checkpoint thread;
- switching runs updates the selected model, Workflow, Tool, runtime, and thread snapshots;
- Workflow shows `task_understanding`, `data_check`, `image_quality_check`, and `completed` in order;
- refreshing the page preserves both business histories;
- the browser console has no application error.

- [ ] **Step 8: Verify persistence across backend restart**

Stop only the backend session, restart it with the Step 5 backend command, refresh the page, and reselect the two-run task.

Expected: both business-run records remain visible, both runtime/thread values are unchanged, health returns to `langgraph_checkpointer=ready`, and the checkpoint counts from Step 6 remain nonzero.

- [ ] **Step 9: Stop the managed development sessions**

Send `Ctrl-C` to the exact backend and frontend sessions from Step 5 and confirm both processes exit.

- [ ] **Step 10: Commit the runbook closeout**

```bash
git add README.md docs/development/v0.2-local-runbook.md
git diff --cached --check
git commit -m "docs: document langgraph postgres runtime"
```

- [ ] **Step 11: Perform the final clean-tree verification**

```bash
git status --short
git log --oneline --decorate -8
```

Expected: the worktree is clean and the branch contains the seven scoped implementation commits after the confirmed design and plan artifacts.
