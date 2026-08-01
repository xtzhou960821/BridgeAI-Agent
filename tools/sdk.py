"""Minimal Tool SDK core for BridgeAI-Agent V0.2."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolManifest:
    """Describes a callable tool and its contract."""

    tool_id: str
    version: str
    name: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """Structured result emitted by every Tool execution."""

    tool_id: str
    version: str
    ok: bool
    output: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None


class ToolExecutionError(Exception):
    """Raised when a Tool cannot be executed by contract."""


class ToolHandlerError(RuntimeError):
    """A declared, safe-to-serialize failure raised by a Tool handler."""

    def __init__(self, error_code: str, error_message: str) -> None:
        super().__init__(error_message)
        self.error_code = error_code
        self.error_message = error_message


class ToolRegistry:
    """In-memory Tool registry for the first engineering skeleton."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolManifest, ToolHandler]] = {}

    def register(self, manifest: ToolManifest, handler: ToolHandler) -> None:
        self._tools[manifest.tool_id] = (manifest, handler)

    def get(self, tool_id: str) -> tuple[ToolManifest, ToolHandler]:
        try:
            return self._tools[tool_id]
        except KeyError as exc:
            raise ToolExecutionError(f"Tool is not registered: {tool_id}") from exc


class ToolExecutor:
    """Executes tools through registered manifests and handlers."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, tool_id: str, payload: dict[str, Any]) -> ToolResult:
        manifest, handler = self._registry.get(tool_id)
        missing = [
            field
            for field in manifest.input_schema.get("required", [])
            if field not in payload
        ]
        if missing:
            return ToolResult(
                tool_id=manifest.tool_id,
                version=manifest.version,
                ok=False,
                output={},
                error_code="missing_required_input",
                error_message=f"Missing required input: {', '.join(missing)}",
            )

        try:
            output = handler(payload)
        except ToolHandlerError as error:
            return ToolResult(
                tool_id=manifest.tool_id,
                version=manifest.version,
                ok=False,
                output={},
                error_code=error.error_code,
                error_message=error.error_message,
            )
        return ToolResult(
            tool_id=manifest.tool_id,
            version=manifest.version,
            ok=True,
            output=output,
        )
