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
from tools.sdk import ToolExecutor, ToolManifest, ToolRegistry


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
            artifact_verifier=_verified_artifact,
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


def _initial_state(run_id: str):
    return initial_bridge_inspection_state(
        task_id="task_001",
        run_id=run_id,
        task_type="bridge_inspection",
        objective="检查桥梁无人机影像质量",
        artifact_ids=["art_001"],
        agent_model={"model_id": "DeepSeek-V4-Flash-4bit"},
    )


def _successful_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        lambda payload: {
            "quality_status": "pass",
            "artifact_id": payload["artifact_id"],
        },
    )
    return registry


def _verified_artifact(artifact_id: str) -> dict[str, object]:
    return {"ok": True, "artifact": {"artifact_id": artifact_id, "status": "ready"}}


class _FakeModelGateway:
    def understand_task(self, request):
        return _FakeModelResult(
            {
                "ok": True,
                "model_id": "DeepSeek-V4-Flash-4bit",
                "provider": "omlx",
                "runtime": "openai-compatible",
                "content": f"任务理解完成：{request.objective}",
                "usage": {"total_tokens": 12},
                "error_message": None,
            },
        )


class _FakeModelResult:
    def __init__(self, payload):
        self._payload = payload

    def as_payload(self):
        return self._payload
