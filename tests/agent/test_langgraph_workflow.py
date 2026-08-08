import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from agent.langgraph_state import (
    StateSerializationError,
    artifact_verifier_payload,
    image_quality_output_payload,
    initial_bridge_inspection_state,
    normalize_checkpoint_value,
)
from agent.langgraph_workflow import build_bridge_inspection_graph
from tools.sdk import (
    ToolExecutor,
    ToolHandlerError,
    ToolManifest,
    ToolRegistry,
    ToolResult,
)


def test_graph_routes_success_through_all_named_nodes():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
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
        artifact_verifier=_verified_artifact,
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
    assert result["error_code"] == "missing_required_input"
    assert result["error_message"] == "Missing required input: camera_id"
    assert [item["step_name"] for item in result["workflow_history"]][-1] == "failed"


def test_graph_persists_multiple_checkpoints_for_one_thread():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
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
    assert state["data_check_result"] == {}
    assert state["tool_results"] == []
    assert state["error_step"] is None
    assert state["error_code"] is None
    assert state["error_message"] is None


@pytest.mark.parametrize(
    "unsafe_artifact_id",
    [
        "/private/tmp/sensitive-bridge.jpg",
        "redis://artifact-user:artifact-pass@cache.example/0",
        "art_",
        "x" * 129,
    ],
)
def test_initial_state_rejects_unsafe_or_unbounded_artifact_references(
    unsafe_artifact_id,
):
    with pytest.raises(StateSerializationError, match=r"artifact_ids\[0\]"):
        initial_bridge_inspection_state(
            task_id="task_001",
            run_id="run_unsafe_initial_artifact",
            task_type="bridge_inspection",
            objective="检查桥梁无人机影像质量",
            artifact_ids=[unsafe_artifact_id],
            agent_model={"model_id": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX"},
        )


def test_graph_routes_bounded_safe_legacy_reference_to_data_check_failure():
    verified_ids = []
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=lambda artifact_id: verified_ids.append(artifact_id)
        or {
            "ok": False,
            "error_code": "ARTIFACT_NOT_FOUND",
            "error_message": "Artifact does not exist",
        },
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=InMemorySaver(),
    )

    result = graph.invoke(
        initial_bridge_inspection_state(
            task_id="task_legacy",
            run_id="run_legacy_reference",
            task_type="bridge_inspection",
            objective="检查历史桥梁影像",
            artifact_ids=["1000"],
            agent_model={"model_id": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX"},
        ),
        config={"configurable": {"thread_id": "run_legacy_reference"}},
    )

    assert verified_ids == ["1000"]
    assert result["status"] == "failed"
    assert result["error_step"] == "data_check"
    assert result["error_code"] == "ARTIFACT_NOT_FOUND"
    assert result["tool_results"] == []


def test_verified_artifact_records_still_require_generated_artifact_ids():
    with pytest.raises(
        StateSerializationError,
        match="data_check_result.artifact.artifact_id",
    ):
        artifact_verifier_payload(
            {"ok": True, "artifact": {"artifact_id": "1000"}},
        )


def test_tool_outputs_still_require_generated_artifact_ids():
    with pytest.raises(StateSerializationError, match="tool_result.output.artifact_id"):
        image_quality_output_payload({"artifact_id": "1000"})


def test_graph_routes_failed_artifact_verification_without_running_tool():
    calls = []
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=lambda _artifact_id: {
            "ok": False,
            "error_code": "ARTIFACT_NOT_FOUND",
            "error_message": "Artifact does not exist",
        },
        tool_executor=ToolExecutor(
            _registry_with_handler(lambda payload: calls.append(payload) or {})
        ),
        checkpointer=InMemorySaver(),
    )

    result = graph.invoke(
        _initial_state("run_missing"),
        config={"configurable": {"thread_id": "run_missing"}},
    )

    assert result["status"] == "failed"
    assert result["error_step"] == "data_check"
    assert result["error_code"] == "ARTIFACT_NOT_FOUND"
    assert result["error_message"] == "Artifact does not exist"
    assert result["data_check_result"] == {
        "ok": False,
        "error_code": "ARTIFACT_NOT_FOUND",
        "error_message": "Artifact does not exist",
    }
    assert result["tool_results"] == []
    assert calls == []


def test_graph_completes_when_analysis_finds_low_quality():
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=ToolExecutor(
            _registry_with_output(
                {"quality_status": "fail", "artifact_id": "art_001"}
            )
        ),
        checkpointer=InMemorySaver(),
    )

    result = graph.invoke(
        _initial_state("run_low_quality"),
        config={"configurable": {"thread_id": "run_low_quality"}},
    )

    assert result["status"] == "completed"
    assert result["tool_results"][0]["ok"] is True
    assert result["tool_results"][0]["output"]["quality_status"] == "fail"


def test_graph_allowlists_verified_artifact_metadata_before_checkpointing():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=lambda artifact_id: {
            "ok": True,
            "artifact": {
                **_verified_artifact(artifact_id)["artifact"],
                "original_filename": "sensitive-bridge.jpg",
                "storage_key": "ab/art_001.jpg",
                "absolute_path": "/private/tmp/sensitive-bridge.jpg",
            },
            "connection_string": "redis://artifact-user:artifact-pass@cache.example/0",
        },
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=saver,
    )

    result = graph.invoke(
        _initial_state("run_artifact_allowlist"),
        config={"configurable": {"thread_id": "run_artifact_allowlist"}},
    )

    assert result["data_check_result"] == _verified_artifact("art_001")
    persisted = repr([item.checkpoint["channel_values"] for item in saver.list(None)])
    for prohibited in (
        "sensitive-bridge.jpg",
        "ab/art_001.jpg",
        "/private/tmp",
        "artifact-user",
        "artifact-pass",
        "cache.example",
    ):
        assert prohibited not in persisted


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("artifact_id", "/private/tmp/sensitive-bridge.jpg"),
        ("sha256", "redis://sha-user:sha-pass@cache.example/0"),
        ("mime_type", "mongodb://mime-user:mime-pass@db.example/quality"),
        ("status", "/var/artifacts/ready"),
    ],
)
def test_graph_rejects_unsafe_values_in_approved_artifact_fields(
    field,
    unsafe_value,
):
    artifact = dict(_verified_artifact("art_001")["artifact"])
    artifact[field] = unsafe_value
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=lambda _artifact_id: {"ok": True, "artifact": artifact},
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=InMemorySaver(),
    )

    with pytest.raises(StateSerializationError, match=field):
        graph.invoke(
            _initial_state(f"run_unsafe_artifact_{field}"),
            config={
                "configurable": {"thread_id": f"run_unsafe_artifact_{field}"}
            },
        )


def test_graph_redacts_prohibited_verifier_error_details():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=lambda _artifact_id: {
            "ok": False,
            "error_code": "ARTIFACT_STORAGE_UNAVAILABLE",
            "error_message": (
                "failed /private/tmp/sensitive-bridge.jpg via "
                "redis://artifact-user:artifact-pass@cache.example/0"
            ),
        },
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=saver,
    )

    result = graph.invoke(
        _initial_state("run_redacted_verifier_error"),
        config={"configurable": {"thread_id": "run_redacted_verifier_error"}},
    )

    assert result["error_message"] == "[redacted]"
    persisted = repr([item.checkpoint["channel_values"] for item in saver.list(None)])
    assert "sensitive-bridge.jpg" not in persisted
    assert "artifact-pass" not in persisted


def test_graph_replaces_unsafe_verifier_error_code_with_safe_failure_code():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=lambda _artifact_id: {
            "ok": False,
            "error_code": "redis://code-user:code-pass@cache.example/0",
            "error_message": "Artifact verification failed",
        },
        tool_executor=ToolExecutor(_registry(required=["artifact_id"])),
        checkpointer=saver,
    )

    result = graph.invoke(
        _initial_state("run_safe_verifier_error_code"),
        config={"configurable": {"thread_id": "run_safe_verifier_error_code"}},
    )

    assert result["error_code"] == "ARTIFACT_VERIFICATION_FAILED"
    persisted = repr([item.checkpoint["channel_values"] for item in saver.list(None)])
    assert "code-user" not in persisted
    assert "code-pass" not in persisted


def test_graph_allowlists_quality_output_and_preserves_approved_fields():
    saver = InMemorySaver()
    approved_output = {
        "artifact_id": "art_001",
        "quality_status": "warn",
        "analyzer_version": "0.1.0",
        "metrics": {
            "short_side_px": 800.0,
            "total_pixels": 1_024_000.0,
            "mean_luminance": 128.0,
            "dark_clip_ratio": 0.0,
            "bright_clip_ratio": 0.0,
            "sharpness_rms": 4.5,
        },
        "thresholds": {
            "resolution": {
                "min_short_side_px": 720,
                "min_total_pixels": 1_000_000,
            },
            "sharpness": {"fail_below": 2.0, "warn_below": 5.0},
        },
        "checks": {
            "resolution": "pass",
            "sharpness": "warn",
        },
        "reasons": ["清晰度低于 5"],
    }
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=ToolExecutor(
            _registry_with_output(
                {
                    **approved_output,
                    "original_filename": "inspection-sensitive.png",
                    "storage_key": "ab/art_001.png",
                    "absolute_path": "/var/artifacts/ab/art_001.png",
                    "connection_string": (
                        "mongodb://quality-user:quality-pass@db.example/quality"
                    ),
                }
            )
        ),
        checkpointer=saver,
    )

    result = graph.invoke(
        _initial_state("run_quality_allowlist"),
        config={"configurable": {"thread_id": "run_quality_allowlist"}},
    )

    assert result["tool_results"][0]["output"] == approved_output
    persisted = repr([item.checkpoint["channel_values"] for item in saver.list(None)])
    for prohibited in (
        "inspection-sensitive.png",
        "ab/art_001.png",
        "/var/artifacts",
        "quality-user",
        "quality-pass",
        "db.example",
    ):
        assert prohibited not in persisted


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("artifact_id", "/private/tmp/quality-sensitive.png"),
        ("quality_status", "redis://status-user:status-pass@cache.example/0"),
        ("analyzer_version", "mongodb://version-user:version-pass@db.example/quality"),
        ("checks", {"resolution": "/var/artifacts/pass"}),
    ],
)
def test_graph_rejects_unsafe_values_in_approved_quality_fields(
    field,
    unsafe_value,
):
    output = {
        "artifact_id": "art_001",
        "quality_status": "pass",
        "analyzer_version": "0.1.0",
        "checks": {"resolution": "pass"},
    }
    output[field] = unsafe_value
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=ToolExecutor(_registry_with_output(output)),
        checkpointer=InMemorySaver(),
    )

    with pytest.raises(StateSerializationError, match=field):
        graph.invoke(
            _initial_state(f"run_unsafe_quality_{field}"),
            config={
                "configurable": {"thread_id": f"run_unsafe_quality_{field}"}
            },
        )


def test_graph_redacts_bare_filename_in_approved_quality_reason():
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=ToolExecutor(
            _registry_with_output(
                {
                    "artifact_id": "art_001",
                    "quality_status": "fail",
                    "reasons": ["inspection-sensitive.png could not be analyzed"],
                }
            )
        ),
        checkpointer=InMemorySaver(),
    )

    result = graph.invoke(
        _initial_state("run_redacted_reason_filename"),
        config={"configurable": {"thread_id": "run_redacted_reason_filename"}},
    )

    assert result["tool_results"][0]["output"]["reasons"] == ["[redacted]"]


def test_graph_redacts_prohibited_tool_error_details():
    saver = InMemorySaver()

    def unsafe_handler(_payload):
        raise ToolHandlerError(
            "ARTIFACT_CONTENT_MISSING",
            "missing /var/artifacts/sensitive.png from "
            "mongodb://quality-user:quality-pass@db.example/quality",
        )

    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=ToolExecutor(_registry_with_handler(unsafe_handler)),
        checkpointer=saver,
    )

    result = graph.invoke(
        _initial_state("run_redacted_tool_error"),
        config={"configurable": {"thread_id": "run_redacted_tool_error"}},
    )

    assert result["error_message"] == "[redacted]"
    persisted = repr([item.checkpoint["channel_values"] for item in saver.list(None)])
    assert "sensitive.png" not in persisted
    assert "quality-pass" not in persisted


def test_graph_replaces_unsafe_tool_error_code_with_safe_failure_code():
    saver = InMemorySaver()

    def unsafe_handler(_payload):
        raise ToolHandlerError(
            "mongodb://code-user:code-pass@db.example/quality",
            "Artifact content is missing",
        )

    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=ToolExecutor(_registry_with_handler(unsafe_handler)),
        checkpointer=saver,
    )

    result = graph.invoke(
        _initial_state("run_safe_tool_error_code"),
        config={"configurable": {"thread_id": "run_safe_tool_error_code"}},
    )

    assert result["error_code"] == "TOOL_EXECUTION_FAILED"
    persisted = repr([item.checkpoint["channel_values"] for item in saver.list(None)])
    assert "code-user" not in persisted
    assert "code-pass" not in persisted


def test_graph_rejects_unsafe_tool_wrapper_strings():
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=_StaticToolExecutor(
            ToolResult(
                tool_id="/private/tmp/image_quality_check",
                version="0.1.0",
                ok=True,
                output={"artifact_id": "art_001", "quality_status": "pass"},
            )
        ),
        checkpointer=InMemorySaver(),
    )

    with pytest.raises(StateSerializationError, match="tool_result.tool_id"):
        graph.invoke(
            _initial_state("run_unsafe_tool_wrapper"),
            config={"configurable": {"thread_id": "run_unsafe_tool_wrapper"}},
        )


def test_graph_rejects_unsafe_tool_version_independently():
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=_StaticToolExecutor(
            ToolResult(
                tool_id="image_quality_check",
                version="redis://version-user:version-pass@cache.example/0",
                ok=True,
                output={"artifact_id": "art_001", "quality_status": "pass"},
            )
        ),
        checkpointer=InMemorySaver(),
    )

    with pytest.raises(StateSerializationError, match="tool_result.version"):
        graph.invoke(
            _initial_state("run_unsafe_tool_version"),
            config={"configurable": {"thread_id": "run_unsafe_tool_version"}},
        )


def test_initial_state_redacts_connection_credentials_before_checkpointing():
    state = initial_bridge_inspection_state(
        task_id="task_001",
        run_id="run_initial_redaction",
        task_type="bridge_inspection",
        objective=(
            "inspect postgres://uri-user:uri-sensitive@db.example/bridgeai with "
            "host=db.example user=bridgeai password=dsn-sensitive dbname=bridgeai"
        ),
        artifact_ids=["art_001"],
        agent_model={"model_id": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX"},
    )

    assert state["objective"] == (
        "inspect postgres://***@db.example/bridgeai with "
        "host=db.example user=bridgeai password=*** dbname=bridgeai"
    )


def test_checkpoint_value_redacts_key_variants_and_connection_credentials():
    value = {
        "accessToken": "access-sensitive",
        "nested": {
            "auth-token": "auth-sensitive",
            "database_url": "postgresql://db-user:db-sensitive@db.example/bridgeai",
            "connection": "postgres://uri-user:uri-sensitive@db.example/bridgeai",
            "dsn": (
                "host=db.example user=bridgeai password='dsn sensitive' "
                "dbname=bridgeai connect_timeout=5"
            ),
            "safe": [True, 7, 0.98, None, {"quality_status": "pass"}],
        },
    }

    normalized = normalize_checkpoint_value(value, path="tool_result.output")

    assert normalized == {
        "accessToken": "[redacted]",
        "nested": {
            "auth-token": "[redacted]",
            "database_url": "[redacted]",
            "connection": "postgres://***@db.example/bridgeai",
            "dsn": (
                "host=db.example user=bridgeai password=*** "
                "dbname=bridgeai connect_timeout=5"
            ),
            "safe": [True, 7, 0.98, None, {"quality_status": "pass"}],
        },
    }


def test_graph_drops_unapproved_tool_fields_and_serializes_with_strict_msgpack():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(
            additional_payload={"api_key": "model-secret"},
        ),
        artifact_verifier=_verified_artifact,
        tool_executor=ToolExecutor(
            _registry_with_output(
                {
                    "quality_status": "pass",
                    "nested": {
                        "accessToken": "tool-access-sensitive",
                        "authToken": "tool-auth-sensitive",
                        "databaseUrl": "postgresql://db-user:db-sensitive@db.example/bridgeai",
                        "connection": "postgres://uri-user:uri-sensitive@db.example/bridgeai",
                        "dsn": (
                            "host=db.example user=bridgeai password=dsn-sensitive "
                            "dbname=bridgeai"
                        ),
                        "absolute_path": "/private/tmp/tool-sensitive.jpg",
                        "connection_string": (
                            "mysql://tool-user:tool-pass@mysql.example/bridgeai"
                        ),
                        "score": 0.98,
                    },
                },
            ),
        ),
        checkpointer=saver,
    )

    result = graph.invoke(
        initial_bridge_inspection_state(
            task_id="task_001",
            run_id="run_safe_msgpack",
            task_type="bridge_inspection",
            objective="检查桥梁无人机影像质量",
            artifact_ids=["art_001"],
            agent_model={
                "model_id": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX",
                "api_key": "profile-secret",
                "metadata": {"binary": b"untrusted"},
            },
        ),
        config={"configurable": {"thread_id": "run_safe_msgpack"}},
    )

    assert result["agent_model"] == {"model_id": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX"}
    assert "api_key" not in result["model_result"]
    assert result["tool_results"][0]["output"] == {"quality_status": "pass"}
    persisted = repr([item.checkpoint["channel_values"] for item in saver.list(None)])
    for sensitive_value in (
        "tool-access-sensitive",
        "tool-auth-sensitive",
        "db-user",
        "db-sensitive",
        "uri-user",
        "uri-sensitive",
        "dsn-sensitive",
        "/private/tmp/tool-sensitive.jpg",
        "tool-user",
        "tool-pass",
        "mysql.example",
    ):
        assert sensitive_value not in persisted
    value_type, _ = JsonPlusSerializer(pickle_fallback=False).dumps_typed(result)
    assert value_type == "msgpack"


def test_graph_rejects_binary_tool_output_before_checkpointing():
    saver = InMemorySaver()
    graph = build_bridge_inspection_graph(
        model_gateway=_FakeModelGateway(),
        artifact_verifier=_verified_artifact,
        tool_executor=ToolExecutor(
            _registry_with_output(
                {"quality_status": "pass", "binary_artifact": b"untrusted"},
            ),
        ),
        checkpointer=saver,
    )

    with pytest.raises(
        StateSerializationError,
        match="tool_result.output.binary_artifact",
    ):
        graph.invoke(
            _initial_state("run_rejected_binary"),
            config={"configurable": {"thread_id": "run_rejected_binary"}},
        )


def _initial_state(run_id: str):
    return initial_bridge_inspection_state(
        task_id="task_001",
        run_id=run_id,
        task_type="bridge_inspection",
        objective="检查桥梁无人机影像质量",
        artifact_ids=["art_001"],
        agent_model={"model_id": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX"},
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


def _registry_with_output(output: dict[str, object]) -> ToolRegistry:
    return _registry_with_handler(lambda _payload: output)


def _registry_with_handler(handler) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        handler,
    )
    return registry


def _verified_artifact(artifact_id: str) -> dict[str, object]:
    return {
        "ok": True,
        "artifact": {
            "artifact_id": artifact_id,
            "sha256": "0" * 64,
            "size_bytes": 1024,
            "mime_type": "image/jpeg",
            "width_px": 1280,
            "height_px": 800,
            "status": "ready",
        },
    }


class _FakeModelGateway:
    def __init__(self, additional_payload: dict[str, object] | None = None):
        self._additional_payload = additional_payload or {}

    def understand_task(self, request):
        payload = {
            "ok": True,
            "model_id": "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX",
            "provider": "omlx",
            "runtime": "openai-compatible",
            "content": f"任务理解完成：{request.objective}",
            "usage": {"total_tokens": 12},
            "error_message": None,
        }
        payload.update(self._additional_payload)
        return _FakeModelResult(
            payload,
        )


class _FakeModelResult:
    def __init__(self, payload):
        self._payload = payload

    def as_payload(self):
        return self._payload


class _StaticToolExecutor:
    def __init__(self, result):
        self._result = result

    def execute(self, _tool_id, _payload):
        return self._result
