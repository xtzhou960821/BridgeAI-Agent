"""Serializer-safe state for the Bridge inspection LangGraph workflow."""

from __future__ import annotations

import operator
import re
from typing import Annotated, TypedDict


_MODEL_METADATA_FIELDS = frozenset(
    {
        "model_id",
        "model_version",
        "alias",
        "provider",
        "runtime",
        "is_stub",
    },
)
_MODEL_RESULT_FIELDS = frozenset(
    {
        "ok",
        "model_id",
        "provider",
        "runtime",
        "content",
        "usage",
        "error_message",
    },
)
_IMAGE_QUALITY_METRIC_FIELDS = frozenset(
    {
        "short_side_px",
        "total_pixels",
        "mean_luminance",
        "dark_clip_ratio",
        "bright_clip_ratio",
        "sharpness_rms",
    }
)
_IMAGE_QUALITY_THRESHOLD_FIELDS = {
    "resolution": frozenset({"min_short_side_px", "min_total_pixels"}),
    "exposure": frozenset({"fail_low", "warn_low", "warn_high", "fail_high"}),
    "dark_clipping": frozenset({"pixel_max", "warn_ratio", "fail_ratio"}),
    "bright_clipping": frozenset({"pixel_min", "warn_ratio", "fail_ratio"}),
    "sharpness": frozenset({"fail_below", "warn_below"}),
}
_IMAGE_QUALITY_CHECK_FIELDS = frozenset(
    {"resolution", "exposure", "dark_clipping", "bright_clipping", "sharpness"}
)
_SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "private_key",
    "privatekey",
    "secret",
)
_SENSITIVE_KEY_SUFFIXES = ("_key", "_token")
_REDACTED_VALUE = "[redacted]"
_POSTGRES_URI_CREDENTIALS = re.compile(
    r"\b(postgres(?:ql)?(?:\+[a-z0-9_.-]+)?://)[^/@\s?#]+@",
    flags=re.IGNORECASE,
)
_KEYWORD_DSN_PASSWORD = re.compile(
    r"(?<![a-z0-9_])(password\s*=\s*)"
    r"(?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|(?:\\.|[^\s])+)",
    flags=re.IGNORECASE,
)
_EXTERNAL_URI = re.compile(r"\b[a-z][a-z0-9+.-]*://", flags=re.IGNORECASE)
_ABSOLUTE_PATH = re.compile(r"(?:^|\s)/(?:[^\s/]+/)+[^\s/]*")
_IMAGE_FILENAME = re.compile(r"\b[^/\s\\]+\.(?:jpe?g|png)\b", flags=re.IGNORECASE)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"\b(?:api[_-]?key|authorization|credential|password|secret|token)\s*[:=]",
    flags=re.IGNORECASE,
)
_ARTIFACT_ID = re.compile(r"art_[A-Za-z0-9_-]+\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SEMANTIC_VERSION = re.compile(
    r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?\Z"
)
_TOOL_ID = re.compile(r"[a-z][a-z0-9_]*\Z")
_ERROR_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_ARTIFACT_MIME_TYPES = frozenset({"image/jpeg", "image/png"})
_ARTIFACT_STATUSES = frozenset({"ready"})
_QUALITY_STATUSES = frozenset({"pass", "warn", "fail"})


class StateSerializationError(ValueError):
    """Raised when an external value cannot safely enter checkpoint state."""


class WorkflowHistoryItem(TypedDict):
    """One serializable workflow-step record."""

    step_name: str
    output: dict[str, object]


class BridgeInspectionState(TypedDict):
    """State persisted by the Bridge inspection graph."""

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
    data_check_result: dict[str, object]
    tool_results: list[dict[str, object]]
    error_step: str | None
    error_code: str | None
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
    """Create a state containing only checkpoint-serializer-safe values."""

    return {
        "task_id": _required_string(task_id, "task_id"),
        "run_id": _required_string(run_id, "run_id"),
        "task_type": _required_string(task_type, "task_type"),
        "objective": _required_string(objective, "objective"),
        "artifact_ids": _artifact_ids(artifact_ids),
        "status": "running",
        "current_step": None,
        "agent_model": model_metadata_payload(agent_model),
        "model_result": {},
        "workflow_history": [],
        "data_check_result": {},
        "tool_results": [],
        "error_step": None,
        "error_code": None,
        "error_message": None,
    }


def model_metadata_payload(agent_model: dict[str, object]) -> dict[str, object]:
    """Allowlist model metadata before it is persisted with a task run."""

    return _allowlisted_payload(
        agent_model,
        allowed_fields=_MODEL_METADATA_FIELDS,
        path="agent_model",
    )


def model_result_payload(model_result: dict[str, object]) -> dict[str, object]:
    """Normalize the model gateway response before it enters graph state."""

    return _allowlisted_payload(
        model_result,
        allowed_fields=_MODEL_RESULT_FIELDS,
        path="model_result",
    )


def artifact_verifier_payload(payload: dict[str, object]) -> dict[str, object]:
    """Allow only stable, path-free Artifact verification state."""

    normalized = _normalized_dictionary(payload, path="data_check_result")
    result: dict[str, object] = {}
    if "ok" in normalized:
        if not isinstance(normalized["ok"], bool):
            raise StateSerializationError(
                "Unsupported checkpoint value at data_check_result.ok: expected bool"
            )
        result["ok"] = normalized["ok"]
    if "error_code" in normalized:
        result["error_code"] = safe_error_code_payload(
            normalized["error_code"],
            path="data_check_result.error_code",
            default="ARTIFACT_VERIFICATION_FAILED",
        )
    if "error_message" in normalized:
        result["error_message"] = external_text_payload(
            normalized["error_message"],
            path="data_check_result.error_message",
        )
    artifact = normalized.get("artifact")
    if artifact is not None:
        if not isinstance(artifact, dict):
            raise StateSerializationError(
                "Unsupported checkpoint value at data_check_result.artifact: expected dict"
            )
        safe_artifact: dict[str, object] = {}
        if "artifact_id" in artifact:
            safe_artifact["artifact_id"] = artifact_id_payload(
                artifact["artifact_id"],
                path="data_check_result.artifact.artifact_id",
            )
        if "sha256" in artifact:
            safe_artifact["sha256"] = _format_string_payload(
                artifact["sha256"],
                path="data_check_result.artifact.sha256",
                pattern=_SHA256,
                expected="lowercase SHA-256",
            )
        if "mime_type" in artifact:
            safe_artifact["mime_type"] = _enum_string_payload(
                artifact["mime_type"],
                path="data_check_result.artifact.mime_type",
                allowed=_ARTIFACT_MIME_TYPES,
            )
        if "status" in artifact:
            safe_artifact["status"] = _enum_string_payload(
                artifact["status"],
                path="data_check_result.artifact.status",
                allowed=_ARTIFACT_STATUSES,
            )
        for key in ("size_bytes", "width_px", "height_px"):
            if key in artifact:
                value = artifact[key]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                ):
                    raise StateSerializationError(
                        "Unsupported checkpoint value at "
                        f"data_check_result.artifact.{key}: expected integer"
                    )
                safe_artifact[key] = value
        result["artifact"] = safe_artifact
    return result


def image_quality_output_payload(payload: dict[str, object]) -> dict[str, object]:
    """Allow only the versioned deterministic image-quality result schema."""

    normalized = _normalized_dictionary(payload, path="tool_result.output")
    result: dict[str, object] = {}
    if "artifact_id" in normalized:
        result["artifact_id"] = artifact_id_payload(
            normalized["artifact_id"],
            path="tool_result.output.artifact_id",
        )
    if "quality_status" in normalized:
        result["quality_status"] = _enum_string_payload(
            normalized["quality_status"],
            path="tool_result.output.quality_status",
            allowed=_QUALITY_STATUSES,
        )
    if "analyzer_version" in normalized:
        result["analyzer_version"] = version_payload(
            normalized["analyzer_version"],
            path="tool_result.output.analyzer_version",
        )
    metrics = normalized.get("metrics")
    if metrics is not None:
        result["metrics"] = _numeric_payload(
            metrics,
            allowed_fields=_IMAGE_QUALITY_METRIC_FIELDS,
            path="tool_result.output.metrics",
        )
    thresholds = normalized.get("thresholds")
    if thresholds is not None:
        if not isinstance(thresholds, dict):
            raise StateSerializationError(
                "Unsupported checkpoint value at tool_result.output.thresholds: expected dict"
            )
        result["thresholds"] = {
            category: _numeric_payload(
                thresholds[category],
                allowed_fields=fields,
                path=f"tool_result.output.thresholds.{category}",
            )
            for category, fields in _IMAGE_QUALITY_THRESHOLD_FIELDS.items()
            if category in thresholds
        }
    checks = normalized.get("checks")
    if checks is not None:
        if not isinstance(checks, dict):
            raise StateSerializationError(
                "Unsupported checkpoint value at tool_result.output.checks: expected dict"
            )
        result["checks"] = {
            key: _enum_string_payload(
                checks[key],
                path=f"tool_result.output.checks.{key}",
                allowed=_QUALITY_STATUSES,
            )
            for key in _IMAGE_QUALITY_CHECK_FIELDS
            if key in checks
        }
    reasons = normalized.get("reasons")
    if reasons is not None:
        if not isinstance(reasons, list):
            raise StateSerializationError(
                "Unsupported checkpoint value at tool_result.output.reasons: expected list"
            )
        result["reasons"] = [
            external_text_payload(
                item,
                path=f"tool_result.output.reasons[{index}]",
            )
            for index, item in enumerate(reasons)
        ]
    return result


def external_text_payload(value: object, *, path: str) -> str:
    """Redact free-form external text that contains persistence-prohibited data."""

    text = _required_payload_string(value, path)
    if (
        _EXTERNAL_URI.search(text)
        or _ABSOLUTE_PATH.search(text)
        or _IMAGE_FILENAME.search(text)
        or _SENSITIVE_ASSIGNMENT.search(text)
    ):
        return _REDACTED_VALUE
    return text


def artifact_id_payload(value: object, *, path: str) -> str:
    """Validate the stable Artifact identifier used by persisted state."""

    return _format_string_payload(
        value,
        path=path,
        pattern=_ARTIFACT_ID,
        expected="Artifact ID",
    )


def version_payload(value: object, *, path: str) -> str:
    """Validate a serializer-safe semantic component version."""

    return _format_string_payload(
        value,
        path=path,
        pattern=_SEMANTIC_VERSION,
        expected="semantic version",
    )


def tool_id_payload(value: object, *, path: str) -> str:
    """Validate a serializer-safe snake-case Tool identifier."""

    return _format_string_payload(
        value,
        path=path,
        pattern=_TOOL_ID,
        expected="Tool ID",
    )


def safe_error_code_payload(value: object, *, path: str, default: str) -> str:
    """Normalize safe identifiers and replace arbitrary external error codes."""

    if not isinstance(value, str) or _ERROR_CODE.fullmatch(value) is None:
        return default
    return value.upper()


def normalize_checkpoint_value(value: object, *, path: str) -> object:
    """Recursively copy checkpoint values, rejecting unsupported runtime objects."""

    if isinstance(value, str):
        return _redact_connection_credentials(value)
    if value is None or isinstance(value, int | float | bool):
        return value
    if isinstance(value, list):
        return [
            normalize_checkpoint_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise StateSerializationError(f"Unsupported checkpoint key at {path}")
            item_path = f"{path}.{key}"
            normalized[key] = (
                _REDACTED_VALUE
                if _is_sensitive_key(key)
                else normalize_checkpoint_value(item, path=item_path)
            )
        return normalized
    raise StateSerializationError(
        f"Unsupported checkpoint value at {path}: {type(value).__name__}",
    )


def _allowlisted_payload(
    payload: dict[str, object],
    *,
    allowed_fields: frozenset[str],
    path: str,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise StateSerializationError(f"Unsupported checkpoint value at {path}: expected dict")
    return {
        key: normalize_checkpoint_value(payload[key], path=f"{path}.{key}")
        for key in allowed_fields
        if key in payload
    }


def _normalized_dictionary(payload: object, *, path: str) -> dict[str, object]:
    normalized = normalize_checkpoint_value(payload, path=path)
    if not isinstance(normalized, dict):
        raise StateSerializationError(
            f"Unsupported checkpoint value at {path}: expected dict"
        )
    return normalized


def _numeric_payload(
    payload: object,
    *,
    allowed_fields: frozenset[str],
    path: str,
) -> dict[str, int | float]:
    if not isinstance(payload, dict):
        raise StateSerializationError(
            f"Unsupported checkpoint value at {path}: expected dict"
        )
    result: dict[str, int | float] = {}
    for key in allowed_fields:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise StateSerializationError(
                f"Unsupported checkpoint value at {path}.{key}: expected number"
            )
        result[key] = value
    return result


def _required_payload_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise StateSerializationError(
            f"Unsupported checkpoint value at {path}: expected string"
        )
    return value


def _format_string_payload(
    value: object,
    *,
    path: str,
    pattern: re.Pattern[str],
    expected: str,
) -> str:
    text = _required_payload_string(value, path)
    if pattern.fullmatch(text) is None:
        raise StateSerializationError(
            f"Unsupported checkpoint value at {path}: expected {expected}"
        )
    return text


def _enum_string_payload(
    value: object,
    *,
    path: str,
    allowed: frozenset[str],
) -> str:
    text = _required_payload_string(value, path)
    if text not in allowed:
        raise StateSerializationError(
            f"Unsupported checkpoint value at {path}: unexpected value"
        )
    return text


def _artifact_ids(artifact_ids: list[str]) -> list[str]:
    normalized = normalize_checkpoint_value(artifact_ids, path="artifact_ids")
    if not isinstance(normalized, list) or not all(isinstance(item, str) for item in normalized):
        raise StateSerializationError("Unsupported checkpoint value at artifact_ids: expected strings")
    return [
        artifact_id_payload(item, path=f"artifact_ids[{index}]")
        for index, item in enumerate(normalized)
    ]


def _required_string(value: str, path: str) -> str:
    if not isinstance(value, str):
        raise StateSerializationError(f"Unsupported checkpoint value at {path}: expected string")
    return _redact_connection_credentials(value)


def _is_sensitive_key(key: str) -> bool:
    normalized_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    normalized_key = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized_key)
    normalized_key = re.sub(r"[^a-zA-Z0-9]+", "_", normalized_key).strip("_").lower()
    return (
        normalized_key in {"api_key", "apikey", "database_url", "token"}
        or normalized_key.endswith(_SENSITIVE_KEY_SUFFIXES)
        or any(fragment in normalized_key for fragment in _SENSITIVE_KEY_FRAGMENTS)
    )


def _redact_connection_credentials(value: str) -> str:
    value = _POSTGRES_URI_CREDENTIALS.sub(r"\1***@", value)
    return _KEYWORD_DSN_PASSWORD.sub(r"\1***", value)
