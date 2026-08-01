"""Model Gateway implementations for Agent task understanding."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib import error, request

from agent.model_profile import AgentModelProfile, default_model_profile


@dataclass(frozen=True)
class TaskUnderstandingRequest:
    """Task data sent to the model during the understanding stage."""

    task_id: str
    task_type: str
    objective: str
    artifact_ids: list[str]


@dataclass(frozen=True)
class ModelGatewayResult:
    """Normalized model response returned to the Agent workflow."""

    ok: bool
    model_id: str
    provider: str
    runtime: str
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def as_payload(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "model_id": self.model_id,
            "provider": self.provider,
            "runtime": self.runtime,
            "content": self.content,
            "usage": self.usage,
            "error_message": self.error_message,
        }


class ModelGateway(Protocol):
    """Boundary used by AgentRunner to call model services."""

    def understand_task(self, task: TaskUnderstandingRequest) -> ModelGatewayResult:
        """Return a model-generated task understanding summary."""


class ModelGatewayConfigurationError(RuntimeError):
    """Raised when a non-stub model profile is missing required runtime config."""


JsonTransport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


class OpenAICompatibleModelGateway:
    """Calls an OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        profile: AgentModelProfile,
        api_key: str,
        transport: JsonTransport | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._profile = profile
        self._api_key = api_key
        self._transport = transport or _post_json
        self._timeout_seconds = timeout_seconds

    def understand_task(self, task: TaskUnderstandingRequest) -> ModelGatewayResult:
        response = self._transport(
            f"{self._profile.api_base_url.rstrip('/')}/chat/completions",
            {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self._profile.model_id,
                "messages": _task_understanding_messages(task),
                "temperature": 0,
                "max_tokens": 256,
            },
            self._timeout_seconds,
        )
        return ModelGatewayResult(
            ok=True,
            model_id=self._profile.model_id,
            provider=self._profile.provider,
            runtime=self._profile.runtime,
            content=_extract_chat_content(response),
            usage=dict(response.get("usage", {})),
        )


class StaticModelGateway:
    """Deterministic fallback for explicitly stubbed local model profiles."""

    def __init__(self, profile: AgentModelProfile) -> None:
        self._profile = profile

    def understand_task(self, task: TaskUnderstandingRequest) -> ModelGatewayResult:
        return ModelGatewayResult(
            ok=True,
            model_id=self._profile.model_id,
            provider=self._profile.provider,
            runtime=self._profile.runtime,
            content=f"任务理解：{task.objective}",
            usage={},
        )


def build_model_gateway_from_environment(
    environ: Mapping[str, str] | None = None,
    profile: AgentModelProfile | None = None,
) -> ModelGateway:
    source = os.environ if environ is None else environ
    active_profile = profile or default_model_profile(source)
    if active_profile.is_stub:
        return StaticModelGateway(active_profile)

    api_key = source.get("BRIDGEAI_AGENT_API_KEY", "").strip()
    if not api_key:
        raise ModelGatewayConfigurationError(
            "API key is required for non-stub Agent model profile.",
        )

    return OpenAICompatibleModelGateway(
        profile=active_profile,
        api_key=api_key,
        timeout_seconds=float(source.get("BRIDGEAI_AGENT_MODEL_TIMEOUT_SECONDS", "60")),
    )


def _task_understanding_messages(task: TaskUnderstandingRequest) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是 BridgeAI-Agent 的任务理解节点。"
                "请用简短中文概括任务目标、输入 Artifact 和下一步动作。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"task_id={task.task_id}\n"
                f"task_type={task.task_type}\n"
                f"objective={task.objective}\n"
                f"artifact_ids={','.join(task.artifact_ids)}"
            ),
        },
    ]


def _extract_chat_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    return str(content).strip()


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Model gateway HTTP {exc.code}: {details}") from exc
