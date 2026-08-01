import pytest

from tools.sdk import ToolExecutor, ToolHandlerError, ToolManifest, ToolRegistry


def test_executor_invokes_registered_tool_and_records_manifest_version():
    registry = ToolRegistry()
    manifest = ToolManifest(
        tool_id="image_quality_check",
        version="0.1.0",
        name="Image quality check",
        input_schema={"required": ["artifact_id"]},
        output_schema={"required": ["quality_status"]},
    )
    registry.register(
        manifest,
        lambda payload: {"quality_status": "pass", "artifact_id": payload["artifact_id"]},
    )

    result = ToolExecutor(registry).execute("image_quality_check", {"artifact_id": "art_001"})

    assert result.ok is True
    assert result.tool_id == "image_quality_check"
    assert result.version == "0.1.0"
    assert result.output == {"quality_status": "pass", "artifact_id": "art_001"}


def test_executor_rejects_payload_missing_required_input():
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        lambda payload: {"quality_status": "pass"},
    )

    result = ToolExecutor(registry).execute("image_quality_check", {})

    assert result.ok is False
    assert result.error_code == "missing_required_input"
    assert result.output == {}


def test_tool_executor_converts_declared_handler_error():
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        lambda _payload: _raise_tool_handler_error(),
    )

    result = ToolExecutor(registry).execute("image_quality_check", {"artifact_id": "art_1"})

    assert result.ok is False
    assert result.output == {}
    assert result.error_code == "ARTIFACT_CONTENT_MISSING"
    assert result.error_message == "图片文件缺失"


def test_tool_executor_does_not_convert_unexpected_handler_exception():
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            tool_id="image_quality_check",
            version="0.1.0",
            name="Image quality check",
            input_schema={"required": ["artifact_id"]},
            output_schema={"required": ["quality_status"]},
        ),
        lambda _payload: (_ for _ in ()).throw(ValueError("unexpected")),
    )

    with pytest.raises(ValueError, match="unexpected"):
        ToolExecutor(registry).execute("image_quality_check", {"artifact_id": "art_1"})


def _raise_tool_handler_error() -> dict[str, object]:
    raise ToolHandlerError("ARTIFACT_CONTENT_MISSING", "图片文件缺失")
