"""Serializer-safe state for the Bridge inspection LangGraph workflow."""

from __future__ import annotations

import operator
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
        "tool_results": [],
        "error_step": None,
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


def normalize_checkpoint_value(value: object, *, path: str) -> object:
    """Recursively copy checkpoint values, rejecting unsupported runtime objects."""

    if value is None or isinstance(value, str | int | float | bool):
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


def _artifact_ids(artifact_ids: list[str]) -> list[str]:
    normalized = normalize_checkpoint_value(artifact_ids, path="artifact_ids")
    if not isinstance(normalized, list) or not all(isinstance(item, str) for item in normalized):
        raise StateSerializationError("Unsupported checkpoint value at artifact_ids: expected strings")
    return normalized


def _required_string(value: str, path: str) -> str:
    if not isinstance(value, str):
        raise StateSerializationError(f"Unsupported checkpoint value at {path}: expected string")
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized_key = key.lower().replace("-", "_")
    return (
        normalized_key in {"api_key", "apikey", "token"}
        or normalized_key.endswith(_SENSITIVE_KEY_SUFFIXES)
        or any(fragment in normalized_key for fragment in _SENSITIVE_KEY_FRAGMENTS)
    )
