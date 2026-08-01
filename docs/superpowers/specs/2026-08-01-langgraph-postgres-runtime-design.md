# BridgeAI-Agent LangGraph PostgreSQL Runtime Design

**Date:** 2026-08-01
**Status:** Approved for implementation
**Target:** First executable LangGraph slice after V0.2 PostgreSQL task history

## 1. Goal

Replace the current hand-written sequential inspection runner with a real
LangGraph `StateGraph` backed by the official PostgreSQL Checkpointer, while
preserving the existing task API, Vue workbench, Model Gateway integration, and
BridgeAI business-history semantics.

The slice is complete only when a normal task execution passes through named
LangGraph nodes, writes multiple checkpoints under a run-scoped thread, and
still produces the existing model, Workflow, and Tool result payloads.

## 2. Current Baseline

The V0.2 runtime currently has these boundaries:

- `TaskService` creates a business run before invoking an inspection callable.
- `AgentRunner` calls the Model Gateway and Tool SDK in a fixed Python sequence.
- `WorkflowState` is an immutable-style dataclass that records step history.
- `inspection_task_runs` is the authoritative task-history table exposed by the
  API and frontend.
- PostgreSQL stores terminal business snapshots, but there are no graph-level
  checkpoints and no LangGraph dependency.

The new design retains the API and business database as the product-facing
authority. LangGraph becomes the Workflow Runtime and checkpoint authority for
the internal execution state of one run.

## 3. Confirmed Decisions

1. Use a real `StateGraph`; do not wrap the existing runner in one opaque node.
2. Use the synchronous Graph API and synchronous `PostgresSaver` for this slice.
3. Use `run_id` as the LangGraph `thread_id` for each execution.
4. Keep repeated runs of one task isolated from each other.
5. Initialize official Checkpointer tables with an explicit command, never at
   application startup or inside a task request.
6. Keep BridgeAI business tables separate from framework-owned Checkpointer
   tables.
7. Preserve existing API routes and response structure, adding only
   backward-compatible runtime metadata.
8. Use `InMemorySaver` only in focused unit tests. Production and PostgreSQL
   integration paths have no in-memory fallback.

## 4. Scope

### 4.1 Included

- LangGraph and PostgreSQL Checkpointer dependencies.
- A typed graph state containing only serializable values.
- Named task-understanding, data-check, Tool, completion, and failure nodes.
- Conditional routing after Tool execution.
- PostgreSQL checkpoints for every graph super-step.
- Explicit, idempotent Checkpointer initialization command.
- Business-run metadata identifying the runtime and checkpoint thread.
- Full failure snapshots in business history.
- Checkpointer readiness in the health payload and frontend status surface.
- Python, PostgreSQL, API, frontend, build, and browser verification.

### 4.2 Excluded

- Human-in-the-loop interrupts and review UI.
- A resume or retry API.
- Async FastAPI, async Model Gateway, or `AsyncPostgresSaver` conversion.
- Queues, workers, cancellation, streaming, WebSockets, or SSE.
- The full production bridge-inspection graph from the architecture white paper.
- LangGraph Store, long-term Memory, RAG, Qdrant, or MinIO integration.
- Copying or modifying LangGraph's internal checkpoint table definitions.

## 5. Architecture

```text
POST /api/v1/tasks/{task_id}/runs
  -> TaskService starts inspection_task_run
  -> run_inspection_task(run_id, task input)
  -> open PostgresSaver for BRIDGEAI_DATABASE_URL
  -> compile StateGraph with the saver
  -> graph.invoke(initial_state, thread_id=run_id)
  -> convert terminal graph state to AgentRunResult payload
  -> TaskService completes or fails the business run
  -> existing API and Vue history read the business snapshot
```

`TaskService` remains responsible for business-run lifecycle and error
translation. `AgentRunner` becomes responsible for constructing and invoking the
graph. Nodes depend on injected Model Gateway and Tool SDK interfaces, not on
FastAPI or the task repository.

The runtime adapter keeps the graph replaceable: callers consume the current
structured result instead of importing LangGraph state or checkpoint types.

## 6. Components

### 6.1 Graph State

`BridgeInspectionState` is a `TypedDict` with these fields:

| Field | Type | Purpose |
|---|---|---|
| `task_id` | `str` | Business task identity |
| `run_id` | `str` | Business run and checkpoint-thread identity |
| `task_type` | `str` | Inspection task type |
| `objective` | `str` | Model task objective |
| `artifact_ids` | `list[str]` | References only; no image bytes |
| `status` | `str` | `running`, `completed`, or `failed` |
| `current_step` | `str` | Last completed graph node |
| `agent_model` | `dict` | Existing Model Profile payload |
| `model_result` | `dict` | Existing model-understanding payload |
| `workflow_history` | `list[dict]` | Append-only public Workflow history |
| `tool_results` | `list[dict]` | Serialized Tool result snapshots |
| `error_step` | `str \| None` | Failed node when applicable |
| `error_message` | `str \| None` | Sanitized failure text |

The state contains no database connection, graph instance, Model Gateway
client, Tool executor, binary Artifact, or secret. Workflow-history updates use
an append reducer so every node contributes one immutable public event.

### 6.2 Graph Topology

```text
START
  -> task_understanding
  -> data_check
  -> image_quality_check
       -> completed -> END
       -> failed    -> END
```

- `task_understanding` calls the existing oMLX-compatible Model Gateway and
  records the Model Profile and understanding result.
- `data_check` selects and validates the first Artifact reference used by the
  V0.2 Tool.
- `image_quality_check` invokes the registered Tool and appends its structured
  result.
- A conditional edge routes an unsuccessful Tool result to `failed` and a
  successful result to `completed`.
- Terminal nodes set the public status and append a terminal Workflow event.

Model or infrastructure exceptions are not converted into false Tool results.
They leave the preceding checkpoint intact and return through the service error
path.

### 6.3 Runner Boundary

`AgentRunner` retains the current input and result domain objects but accepts a
checkpointer and an explicit `thread_id`. Its production caller supplies
`PostgresSaver`; unit tests supply `InMemorySaver`.

`run_inspection_task` accepts the business `run_id`, opens a synchronous
`PostgresSaver` context for one invocation, compiles the graph, invokes it, and
serializes the terminal state into the existing API shape.

The Checkpointer `setup()` method is never called from this path.

## 7. Persistence Design

### 7.1 Business Migration

Create `0003_langgraph_runtime.sql` to add:

- `workflow_runtime TEXT NOT NULL DEFAULT 'legacy'`
- `checkpoint_thread_id TEXT`
- a runtime check constraint allowing only supported runtime identifiers;
- a nonblank constraint for checkpoint thread IDs;
- a unique partial index on non-null `checkpoint_thread_id`.

Existing rows remain `legacy` with no thread ID. New LangGraph runs store
`workflow_runtime='langgraph'` and `checkpoint_thread_id=run_id`.

The domain record, repository mapper, API payload, frontend type, history list,
and detail view expose these two fields. Their addition is backward compatible
with existing API consumers.

### 7.2 Framework-Owned Tables

The official `PostgresSaver.setup()` command owns checkpoint schema creation and
versioning. BridgeAI migrations do not reproduce, rename, index, constrain, or
reference the internal `checkpoints`, `checkpoint_writes`,
`checkpoint_blobs`, and migration tables.

The required local order is:

1. run BridgeAI business migrations;
2. run the explicit LangGraph Checkpointer setup command;
3. start the backend;
4. invoke tasks normally.

### 7.3 Transaction Boundary

Business-run state and LangGraph checkpoints are separate commits. The system
does not claim distributed atomicity. A forced process termination may leave a
business run in `running` while checkpoints exist. That evidence is intentional
and is the basis for a later resume/reconciliation slice.

## 8. Setup and Health

Add an explicit module command that:

1. reads `BRIDGEAI_DATABASE_URL` without logging it;
2. opens `PostgresSaver.from_conn_string(...)`;
3. calls `setup()` once;
4. exits successfully when repeated.

The backend never calls this command automatically.

Health adds `langgraph_checkpointer` with these states:

- `ready`: required official tables are present and queryable;
- `not_initialized`: the business database is reachable but checkpoint tables
  are absent;
- `unavailable`: the database or checkpointer probe fails.

The existing `database`, `model_gateway`, `tool_registry`, and `workflow`
components retain their current meanings.

## 9. Error Handling

| Condition | Business Run | HTTP result |
|---|---|---|
| Graph completes | `completed`, full snapshots | 201 terminal record |
| Tool returns failure | `failed`, full snapshots | 201 failed terminal record |
| Model configuration missing | `failed`, sanitized error | Existing 503 `MODEL_GATEWAY_NOT_CONFIGURED` |
| Checkpointer absent/unavailable | `failed`, run ID retained | 503 `LANGGRAPH_CHECKPOINTER_NOT_READY` |
| Unexpected node/runtime exception | `failed`, evidence retained | 502 `TASK_EXECUTION_FAILED` |

The repository failure operation accepts optional model, Workflow, and Tool
snapshots so a failed terminal graph does not lose completed-node evidence.

Bearer credentials and PostgreSQL connection credentials continue to be
redacted from stored error messages. Checkpoint state contains no secrets. Local
configuration enables strict msgpack deserialization behavior recommended for
the PostgreSQL Checkpointer.

## 10. Dependencies

Use bounded current stable ranges:

```text
langgraph>=1.2.9,<1.3
langgraph-checkpoint-postgres>=3.1,<3.2
psycopg[binary]>=3.2
```

LangGraph remains a low-level Workflow Runtime. This slice does not introduce
LangChain agents, LangSmith, or another model abstraction.

## 11. Testing Strategy

### 11.1 Graph Unit Tests

- Build the graph with `InMemorySaver`, Fake Model Gateway, and the existing Tool
  registry contract.
- Verify named nodes execute in the confirmed order.
- Verify successful Tool routing reaches `completed`.
- Verify unsuccessful Tool routing reaches `failed`.
- Verify public Workflow history and Tool snapshots remain API compatible.
- Verify a thread produces checkpoints across graph super-steps.

### 11.2 PostgreSQL Integration Tests

- Guard all destructive setup to the exact database name
  `bridgeai_agent_test`.
- Run Checkpointer setup twice and prove it is repeatable.
- Invoke the graph with a real `PostgresSaver`.
- Query checkpoint history for `thread_id=run_id` and prove multiple snapshots
  exist.
- Execute two runs for one task and prove their threads and checkpoint histories
  are isolated.
- Verify migration and repository mapping for legacy and LangGraph runs.

### 11.3 Service and API Tests

- Verify `TaskService` passes the generated run ID to the runtime.
- Verify successful and failed graph snapshots are persisted.
- Verify stable 503 translation for missing Checkpointer initialization.
- Preserve all current task creation, listing, detail, execution, compatibility,
  and history contracts.
- Verify health states without calling `setup()`.

### 11.4 Frontend Tests

- Render `workflow_runtime=langgraph` in run history or detail.
- Render the checkpoint thread ID.
- Preserve task creation, execution, latest-run selection, and historical-run
  switching behavior.

## 12. End-to-End Acceptance

The implementation is accepted when all of the following are demonstrated:

1. BridgeAI migrations and Checkpointer setup run explicitly and repeatably.
2. Health reports database, Model Gateway, and Checkpointer readiness.
3. A created task executes through the named StateGraph nodes.
4. Two executions of one task create two independent thread IDs.
5. Each thread has multiple durable PostgreSQL checkpoints.
6. Existing model content, usage, Workflow history, and Tool snapshots render in
   the workbench.
7. Runtime metadata identifies LangGraph and the checkpoint thread.
8. Browser refresh and backend restart retain business history and checkpoints.
9. Python tests, PostgreSQL integration tests, frontend tests, production build,
   dependency checks, and whitespace checks pass.

## 13. Deferred Next Slice

The next LangGraph slice may add a recovery service and API that reconcile a
`running` business run with its latest Checkpoint, followed by interrupt-driven
human review. Those capabilities will reuse the thread mapping and checkpoint
evidence introduced here; they are not simulated in this implementation.

## 14. Primary References

- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Checkpointing reference](https://reference.langchain.com/python/langgraph/checkpoints)
- [PostgreSQL Checkpointer reference](https://reference.langchain.com/python/langgraph.store.postgres)
- [LangGraph PyPI](https://pypi.org/project/langgraph/)
- [LangGraph PostgreSQL Checkpointer PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/)
